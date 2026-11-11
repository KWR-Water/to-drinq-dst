import os
import pandas as pd
import numpy as np
from typing import Union, List, Optional, Any, Dict
from warnings import warn

import research.collect_substance_identifiers as collect_substances
from research.validators import cas_validation
from research import DPATH_RESEARCH

GREEK_CHARACTERS = {
    "α": "alpha",
    "β": "beta",
    "γ": "gamma",
    "δ": "delta",
    "ε": "epsilon",
    "ζ": "zeta",
    "η": "eta",
}


def abates_studies_in_dataframe(
    fpath: str,
    only_drinking_water: bool = False,
    return_citation_keys: bool = False,
    replace_greek_characters: bool = True,
) -> Union[pd.DataFrame, List[str]]:
    """Puts one of the sheets, or alternatively only the citation keys, of the
    ABATES CSV file in a dataframe.

    Args:
        fpath (str): path to the file
        only_drinking_water (bool, optional): flag if only drinking water
            sources should be selected. Defaults to True.
        return_citation_keys (bool, optional): flag if the whole sheet, or only
            citation keys should be returned. Defaults to True.

    Returns:
        pd.DataFrame: pandas dataframe
    """
    df = pd.read_csv(fpath, sep=";")

    if only_drinking_water:
        # drop unknown type of water application
        nans = df["Drinking water or wastewater"].isnull()
        df = df[~nans]
        dw = df["Drinking water or wastewater"].apply(
            str.lower) == "drinking water"
        df = df[dw].reset_index()
    if return_citation_keys:
        return list(df["Reference/partner"].unique())
    if replace_greek_characters:
        df.replace(GREEK_CHARACTERS, regex=True, inplace=True)

    return df


def abates_alldata_in_dataframe(
    fpath: str,
    only_drinking_water: bool = True,
    replace_greek_characters: bool = True,
) -> pd.DataFrame:
    header_mapping = {
        "Citation": "citation",
        "Purpose of study": "study_purpose",
        "Name": "synonym_substance",
        "CAS id": "cas_substance",
        "Molecular weight": "mw",
        "Molecular size (Å)": "molecular_size",
        "H-bonds": "has_h-bonds",
        "Functional groups": "functional_groups",
        "pKa": "pka",
        "Log Kow": "log_kow",
        "Description": "substance_category",
        "SMILES": "smiles",
        "Source": "source",
        "Purity percentage": "purity_percentage",
        "Composition of product formulation": "composition_product",
        "Type of water": "water_type",
        "DOM/NOM/DOC content": "nom_content",
        "unit NOM concentration": "nom_unit",
        "Type of treatment": "treatment_type",
        "Specification treatment": "treatment_spec",
        "Limitations": "limitations_of_study",
        "Scale of experiemnt": "scale_of_experiment",
        "Spiked": "is_spiked",
        "mixture or single": "mixture_or_single",
        "initial concentration": "conc_initial_substance",
        "unit initial concentration": "unit_initial_conc",
        "end (effluent) concentration": "conc_effluent_substance",
        "unit effluent concentration": "unit_effluent_conc",
        "concentration/dosage": "dosage_concentration",
        "unit dosage": "unit_dosage",
        "H2O2": "h2o2_concentration",
        "peroxide concentration unit": "unit_h2o2_conc",
        "contact time": "contact_time",
        "time unit": "unit_of_time",
        "Number of replicas": "amount_replicas",
        "Efficiency high": "efficiency_high",
        "Efficiency low": "efficiency_low",
        "?": "unknown",
        "(Average) efficiency": "efficiency_avg",
        "Standard deviation in efficiency": "efficiency_std",
        "Comments": "comments",
        "Type of reference": "publication_type",
    }
    dataframe = pd.read_csv(fpath, sep=";")
    dataframe.rename(columns=header_mapping, inplace=True)

    if only_drinking_water:
        dataframe.dropna(subset="water_type", inplace=True, axis=0)
        surface_wtr = dataframe["water_type"].map(str.lower) == "surface water"
        drinking_wtr = dataframe["water_type"].map(
            str.lower) == "drinking water"
        dataframe = dataframe[surface_wtr | drinking_wtr]

    if replace_greek_characters:
        dataframe.replace(GREEK_CHARACTERS, regex=True, inplace=True)

    selection = dataframe.dropna(subset="efficiency_avg")

    unnamed_columns = [col for col in selection.columns if "Unnamed:" in col]
    selection.drop(columns=unnamed_columns, axis=0, inplace=True)

    return selection


def drop_not_analysed_substances(
    dataframe: pd.DataFrame,
    columns: Optional[Union[list[str], np.ndarray, str]] = None,
) -> pd.DataFrame:
    if columns is None:
        columns = list(dataframe.columns)
    elif isinstance(columns, str):
        columns = [columns]
    else:
        columns = list(columns)

    dataframe.loc[:, columns] = dataframe.loc[:, columns].replace(
        r"not\sanal[a-zA-Z]+", pd.NA, regex=True)

    dataframe.dropna(subset=columns, axis=0, inplace=True)

    return dataframe


def quantitative_binning_of_efficiencies(
    dataframe: pd.DataFrame,
    efficiency_columns: List[str],
    bins: List[float],
    drop: bool = False,
) -> pd.DataFrame:
    new_columns = ["f{col}_bin" for col in efficiency_columns]
    dataframe[new_columns] = None

    for col in efficiency_columns:
        new_col = f"{col}_bin"
        dataframe[new_col] = np.digitize(x=dataframe[col], bins=bins)

    if drop:
        dataframe.drop(columns=efficiency_columns, inplace=True)

    return dataframe


def convert_columns_to_float(dataframe: pd.DataFrame, columns: List[Any]):
    for col in columns:
        try:
            dataframe[col] = dataframe[col].astype(float)
        except ValueError:
            warn(
                f"{col} has a string which cannot be converted to a "
                "float. Conversion of this column will be skipped."
            )

    return dataframe


def aggregate_mean_stdev(
    dataframe: pd.DataFrame,
    grouping_columns: Optional[List[Any]] = None,
    column_to_agg: Optional[str] = None,
) -> pd.DataFrame:
    """Aggregates the mean and standard deviation of values in a column of a
    dataframe.

    Args:
        dataframe (pd.DataFrame): pandas dataframe
        grouping_columns (Optional[List[Any]], optional): columns of the
            dataframe which will be grouped. Defaults to None.
        column_to_agg (Optional[str], optional): column of the dataframe which
            holds values to be aggregated. Defaults to None.

    Returns:
        pd.DataFrame: dataframe with a MultiIndex, as defined by
            `grouping_columns`.
    """

    if grouping_columns is None:
        grouping_columns = ["synonym_substance", "treatment_spec"]
    if column_to_agg is None:
        column_to_agg = "efficiency_avg"

    return dataframe.groupby(grouping_columns).agg({column_to_agg: ["mean", "std"]})


def concat_list_entries_as_rows(
    concatenated: pd.DataFrame,
    list_value: Union[str, float, int],
    list_column: str,
    identifier_column: str,
    identifier_value: Union[str, float, int],
    list_entry_dtype: Union[str, float, int],
    identifier_dtype: Union[str, float, int],
):
    """Concatenates entries of a list within a specific row and column
    (i, `list_column`) of a dataframe as separate rows of a new dataframe. The
    value in (i, `identifier_column`) of the dataframe is repeated n times,
    with n the length of the list in (i, `list_column`).

    Args:
        concatenated (pd.DataFrame): dataframe to be concatenated
        list_column (str): name of the column with list entries
        identifier_column (str): name of the identifier column
        list_entry_dtype (Union[str, float, int]): type of list elements
        value_dtype (Union[str, float, int]): dtype of value
    """
    target_columns = [list_column, identifier_column]
    target_columns.sort()
    concatenated = concatenated.loc[:, target_columns]

    new_entries = pd.DataFrame(columns=target_columns)
    new_entries.loc[0, [list_column, identifier_column]] = (
        list_value,
        identifier_value,
    )
    concatenated = pd.concat(
        (concatenated, new_entries), axis=0, ignore_index=True)

    # set the dtype for the list and identifier column
    (
        concatenated[list_column],
        concatenated[identifier_column],
    ) = (
        concatenated[list_column].astype(list_entry_dtype),
        concatenated[identifier_column].astype(identifier_dtype),
    )
    return concatenated


def longlist_cas_per_cid(
    cid_cas_dataframe: pd.DataFrame,
    cas_column_name: str = "cas",
    cid_column_or_index_name: str = "cis",
) -> pd.DataFrame:
    """Concatenates the CAS registry numbers column-wise (axis=0) such that it
    can be stored in a joint table with CIDs.

    Args:
        cid_cas_dataframe (pd.DataFrame): dataframe with a CID and a CAS column
        cas_column_name (str): name of the CAS column. CAS numbers are stored
            as a list for each CID.
        cid_column_or_index_name (str): name of the column or index for CIDs

    Raises:
        TypeError: whenever the CAS column does not have 'cas'or 'CAS' in its
            name

    Returns:
        pd.DataFrame: dataframe with CAS and CIS numbers
    """
    cas_cid_columns = ["cas", "cid"]

    # sort the column names alphabetically
    cid_cas_dataframe = cid_cas_dataframe.reindex(
        sorted(cid_cas_dataframe.columns), axis=1
    )

    # the assumption is that the cas numbers are stored in a column with `cas`
    # in its name
    if "cas" not in cas_column_name:
        warn("CAS column has possibly a non-descriptive name.")

    # if the cid column is in the index, reset the index
    if cid_cas_dataframe.index.name is not None:
        if cid_column_or_index_name in cid_cas_dataframe.index.name.lower():
            cid_cas_dataframe.reset_index(inplace=True)

    longlist_cas = pd.DataFrame(columns=cas_cid_columns)
    for row in cid_cas_dataframe.iterrows():
        cas_nrs, cid = row[1]
        for cas in cas_nrs:
            if not isinstance(cas_nrs, list):
                raise TypeError("CAS registry numbers should be in a list.")
            cas_ = cas
            if len(cas_nrs) == 1:
                cas_ = None
            else:
                if not cas_validation(cas=cas_, raise_warning=True):
                    cas_ = None
            longlist_cas = concat_list_entries_as_rows(
                concatenated=longlist_cas,
                list_value=cas_,
                list_column="cas",
                identifier_column="cid",
                identifier_value=cid,
                list_entry_dtype=str,
                identifier_dtype=int,
            )

    return longlist_cas


def make_table_cid_cas(
    cas_and_cid_dataframe: pd.DataFrame,
    cid_series: pd.Series,
    fpath_csv: Optional[str] = None,
    **csv_write_kwargs: Dict[str, str],
):
    cas_and_cid_dataframe["cid"] = cas_and_cid_dataframe.index.map(cid_series)
    cas_and_cid_dataframe["cid"] = cas_and_cid_dataframe["cid"].astype(int)
    cas_cid_table = longlist_cas_per_cid(
        cas_and_cid_dataframe.reset_index(drop=True))

    if fpath_csv is not None:
        cas_cid_table.to_csv(fpath_csv, sep=";")
    return cas_cid_table


def make_table_synonyms(
    synonym_lists_per_cid: pd.DataFrame,
    verbose: bool = True,
):
    columns = ["cid", "synonym"]
    longlist_synonyms = pd.DataFrame(columns=columns)
    for row in synonym_lists_per_cid.iterrows():
        cid, synonyms = row[1]
        for synonym in synonyms:
            if not isinstance(synonyms, list):
                raise TypeError("synonyms should be in a list.")
            synonym_ = synonym
            do_concatenate = True
            if len(synonyms) == 1:
                synonym_ = None
            else:
                if synonym_ is not None:
                    if cas_validation(cas=synonym_, raise_warning=False):
                        # filter out CAS registry numbers
                        do_concatenate = False
                    synonym_ = synonym_.lower()
            # only store a synonym if needed
            if do_concatenate:
                longlist_synonyms = concat_list_entries_as_rows(
                    concatenated=longlist_synonyms,
                    list_value=synonym_,
                    list_column="synonym",
                    identifier_column="cid",
                    identifier_value=cid,
                    list_entry_dtype=str,
                    identifier_dtype=int,
                )
                if verbose and synonym_ is not None:
                    print(f">> Concatenating {synonym_} to the table.")
    return longlist_synonyms


def make_table_compound(cids_and_common_names: Union[pd.DataFrame, pd.Series]):
    if isinstance(cids_and_common_names, pd.Series):
        cids_and_common_names.drop_duplicates(inplace=True)
        cids_and_common_names = pd.DataFrame(
            cids_and_common_names).reset_index()
    elif isinstance(cids_and_common_names, pd.DataFrame):
        cids_and_common_names.drop_duplicates(subset="cid", inplace=True)

    cid_to_common_name = cids_and_common_names[["cid", "common_name"]].set_index("cid")[
        "common_name"
    ]

    table_compound = collect_substances.get_isomeric_smiles_from_cids(
        cids=cids_and_common_names["cid"]
    )
    table_compound["common_name"] = (
        table_compound["cid"].map(cid_to_common_name).str.lower()
    )

    return table_compound


if __name__ == "__main__":
    store_to_csv = True
    store_cas_and_synonyms = False
    efficiency_columns = ["efficiency_avg"]
    dpath_abates = os.path.join(DPATH_RESEARCH, "data/raw/abates")
    dpath_processed = os.path.join(DPATH_RESEARCH, "data/processed/")

    fpath_studies = os.path.join(
        dpath_abates, "DSS treatment techniques - studies.csv")
    fpath_master = os.path.join(
        dpath_abates, "DSS treatment techniques - master.csv")
    studies = abates_studies_in_dataframe(
        fpath_studies, only_drinking_water=True, return_citation_keys=False
    )
    cit_keys = abates_studies_in_dataframe(
        fpath_studies, only_drinking_water=True, return_citation_keys=True
    )

    # load the master sheet
    print("Loading CSV sheets and processing")
    master = abates_alldata_in_dataframe(
        fpath_master, only_drinking_water=True, replace_greek_characters=True
    )
    master = drop_not_analysed_substances(
        dataframe=master, columns=efficiency_columns)
    master = convert_columns_to_float(
        dataframe=master, columns=efficiency_columns)
    master = quantitative_binning_of_efficiencies(
        dataframe=master,
        efficiency_columns=efficiency_columns,
        bins=[0.0, 25.0, 50.0, 75.0, 100.0],
    )

    substances = master["synonym_substance"].unique()
    by_substance = aggregate_mean_stdev(dataframe=master)
    print("Done.")

    print("Collecting compound synonym names, CIDs and CAS registry numbers.")
    print("This can take a while...")
    synonyms_per_cid = collect_substances.get_synonyms_and_cids_from_list(
        substances)
    print("Done.")
    cids, synonyms = (
        synonyms_per_cid["cid"],
        synonyms_per_cid[["cid", "compound_synonyms"]],
    )
    cid_not_null = ~cids.isnull()
    synonyms = synonyms[cid_not_null].reset_index(drop=True)
    common_names_and_cids = cids[cid_not_null]

    table_compound = make_table_compound(
        cids_and_common_names=common_names_and_cids,
    )

    if store_cas_and_synonyms:
        table_synonyms_cid = make_table_synonyms(
            synonym_lists_per_cid=synonyms.rename(
                columns={"compound_synonyms": "synonym"}
            )
        )
        # collect cas_numbers
        cas_nrs = collect_substances.resolve_by_cirpy(
            list(synonyms_per_cid[cid_not_null].index), target_identifier="cas"
        )
        table_cas_cid = make_table_cid_cas(
            cas_and_cid_dataframe=cas_nrs, cid_series=cids
        )

    # cas_nrs = collect_substances.get_cas_numbers(cids)
    # store to CSV files
    compounds_empty_cid = cids[cids.isnull()].index
    for count_, compound in enumerate(compounds_empty_cid):
        by_substance.drop(compound, level="synonym_substance", inplace=True)
        print(f"No CID known for {compound}: removing row from dataframe.")
    print(f"{count_ + 1} compounds dropped since the CID is not known.")

    if store_to_csv:
        # table_cas_cid.to_csv(
        # os.path.join(dpath_processed, 'table_cas_cid.csv'), sep=';')
        # table_synonyms_cid.to_csv(
        # os.path.join(dpath_processed, 'table_synonyms_cid.csv'), sep=';')
        table_compound.to_csv(
            os.path.join(dpath_processed, "table_compound.csv"), sep=";"
        )
        # by_substance.to_csv(
        # os.path.join(dpath_processed, 'cecs_removal_eff_mean_std.csv'),
        # index_label=['synonym_substance', 'treatment_spec'],
        # sep=';')
