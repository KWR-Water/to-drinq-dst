from typing import List, Optional, Dict, Hashable, Any, Union
import pandas as pd
import pubchempy as pcp
import cirpy
from warnings import warn

from src.fetchtry import retry_multiple_attempts

COMPOUND_IDENTIFIERS: Dict[str, Dict[str, Optional[str]]] = {
    'inchi': {
        'pubchem': 'InChI',
        'cirpy': 'stdinchi'
    },
    'inchikey': {
        'pubchem': 'InChIKey',
        'cirpy': 'stdinchikey'
    },
    'canonical_smiles': {
        'pubchem': 'CanonicalSMILES',
        'cirpy': 'smiles'
    },
    'isomeric_smiles': {
        'pubchem': 'IsomericSMILES',
        'cirpy': 'smiles'
    },
    'cid': {
        'pubchem': 'cid',
        'cirpy': None},
    'cas': {
        'pubchem': None,
        'cirpy': 'cas'
    },
}


def flatten_list_if_one_entry(to_flatten: List[Any]) -> Hashable:
    """Flattens a list to a hashable type if the lenght of the list is equal 
    to one. Works recursively.

    Args:
        to_flatten (List[Hashable]): list with hashable type objects (e.g. 
            integers, floats, booleans, etc.). Returns None if the list has 
            length greater than 1.

    Raises:
        TypeError: whenever the input is not a list.

    Returns:
        Hashable: the entry of the list.
    """
    if not isinstance(to_flatten, list):
        raise TypeError('Input argument should be a list.')

    flattened = None
    stop_recursions_when_depth = 10
    if len(to_flatten) == 1:
        recursion = 0
        while isinstance(to_flatten, list):
            recursion += 1
            if len(to_flatten) == 1:
                flattened = to_flatten[0]
                if not isinstance(to_flatten, list):
                    return flattened
                to_flatten = flattened
            if recursion == stop_recursions_when_depth:
                print('stopped after 10 recursions!')
                break
    return flattened


def empty_synonyms_dataframe(
        synonym_column_name: str = 'compound_synonyms',
        cid_column_name: str = 'cid',
        index_name: str = 'common_name'
):
    return pd.DataFrame(
        columns=[cid_column_name, synonym_column_name],
        index=pd.Index([], name=index_name),
    )


def get_synonyms_wrapper(name_compound):
    result = pcp.get_synonyms(name_compound, 'name', domain='compound')
    synonyms = []

    match len(result):
        case 0:
            pass
        case 1:
            result = flatten_list_if_one_entry(result)
            synonyms = result['Synonym']
        case _:
            warn('Multiple results returned - returning empty dataframe.')
    return synonyms


def get_synonyms_and_cid(
        name_compound: str,
        synonym_column_name: str = 'compound_synonyms'
) -> pd.DataFrame:
    """Get synonym names and CID for one chemical compound.

    Args:
        name_compound (str): name of compound
        synonym_column_name (str, optional): name of the column where synonym
            names are stored. Defaults to 'compound_synonyms'.

    Returns:
        pandas.DataFrame: synonym names for the compound
    """
    synonym_list = get_synonyms_wrapper(name_compound)
    cid = pcp.get_cids(name_compound)
    if cid is not None:
        cid = flatten_list_if_one_entry(cid)
    cid_column_name = 'cid'

    synonyms = empty_synonyms_dataframe(synonym_column_name, cid_column_name)
    # synonyms.index = pd.Index([name_compound], name='common_name')
    synonyms.loc[name_compound, cid_column_name] = cid
    synonyms.loc[name_compound, synonym_column_name] = synonym_list

    return synonyms


def get_synonyms_and_cids_from_list(
        list_compounds: List[str],
        synonym_column_name: str = 'compound_synonyms'
) -> pd.DataFrame:
    """Gets a dataframe with synonym names and cids in columns, and the 
    lookup compound names in the index.

    Args:
        list_compounds (List[str]): _description_
        synonym_column_name (str, optional): _description_. Defaults to 'compound_synonyms'.

    Returns:
        pd.DataFrame: _description_
    """
    list_compounds = list(set(list_compounds))
    list_of_synonyms = empty_synonyms_dataframe(
        synonym_column_name=synonym_column_name)
    for compound in list_compounds:
        synonyms = get_synonyms_and_cid(
            compound, synonym_column_name=synonym_column_name)
        list_of_synonyms = pd.concat((list_of_synonyms, synonyms), axis=0)

    return list_of_synonyms


def get_isomeric_smiles_from_cids(
        cids: Union[List[int], pd.Series],
        smiles_col_name: str = 'isomeric_smiles'
):
    if isinstance(cids, pd.Series):
        cids = list(set(cids.to_list()))

    dict_isomeric_smiles = pcp.get_properties(
        properties='IsomericSMILES', identifier=cids)
    df_isomeric_smiles = pd.DataFrame(dict_isomeric_smiles)
    df_isomeric_smiles.rename(columns={'CID': 'cid'}, inplace=True)
    return df_isomeric_smiles


def get_pcp_properties_from_cid(
        cid: str,
        property_identifiers: Optional[Union[List[Any], str]] = None,
) -> Optional[pd.DataFrame]:
    if property_identifiers is None:
        property_identifiers = [
            'IsomericSMILES', 'InChI', 'InChIKey', 'MolecularFormula']
    columns = property_identifiers
    if isinstance(property_identifiers, str):
        columns = [property_identifiers]
    property_list = pcp.get_properties(
        properties=property_identifiers, identifier=cid)
    if property_list is None:
        return None
    return pd.DataFrame(
        data=property_list, columns=columns, index=pd.Index([cid], name='cid')
    )


def resolve_by_cirpy(
        compound_list: List[str],
        target_identifier: str,
        source_identifier: str = 'common_name'):
    """Resolves the compound properties by using CIR (National Cancer Institute
    Chemoinformatics Tools, http://cactus.nci.nih.gov/) via CIRpy.

    Args:
        list_compounds (list): list of compounds using any of
            the following identifiers: InChI, InChI key, IUPAC name, SMILES,
            CAS registry number.
        source_cmpd_identifier (str): the identifier that is
            used to resolve the target compound identifier. It should be:
            `inchi`, `inchikey`, `iupac_name`, `common_name` or `cid`. Only 
            used for naming the index.
        target_identifier (str): identifier that should be resolved by CIRpy.
            Defaults to 'cas'. Other use cases are possible, but we recommend
            using PubChem instead.

    Returns:
        pandas.DataFrame: dataframe with source and target substance
            identifiers.
    """
    col_name = target_identifier
    if target_identifier is None:
        return ValueError(
            "Compound target identifier should be specified (not None)")

    cirpy_identifier = COMPOUND_IDENTIFIERS[target_identifier]['cirpy']
    if cirpy_identifier is None:
        raise ValueError(
            f'CIRpy does not accept {cirpy_identifier} as an identifier.')

    resolved = pd.DataFrame(columns=[col_name], index=compound_list)
    resolved.index.name = source_identifier

    for _idx, _row in resolved.iterrows():
        _c = _row.name
        _result = retry_multiple_attempts(
            cirpy.resolve, num_retries=3, sleep_max_time=60,
            **{'input': _c, 'representation': cirpy_identifier})

        if cirpy_identifier == 'cas':
            if not isinstance(_result, list):
                _result = [_result]
        try:
            resolved.loc[_idx, col_name] = _result
        except ValueError:
            warn(
                'ValueError when inserting CAS result into dataframe. '
                'Inserting None.')
            resolved.loc[_idx, col_name] = None

    return resolved


def get_cas_numbers(cid: str) -> pd.DataFrame:
    pass
    return None
