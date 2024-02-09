import os
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Union, List, Optional, Any
from warnings import warn

DPATH_RESEARCH = Path(__file__).parent.absolute()


def abates_studies_in_dataframe(
        fpath: str,
        only_drinking_water: bool = True,
        return_citation_keys: bool = True,
        ) -> pd.DataFrame:
    """Puts one of the sheets, or alternatively only the citation keys, of the
    ABATES Excel file in a dataframe.

    Args:
        fpath (str): path to the file
        only_drinking_water (bool, optional): flag if only drinking water 
            sources should be selected. Defaults to True.
        return_citation_keys (bool, optional): flag if the whole sheet, or only 
            citation keys should be returned. Defaults to True.

    Returns:
        pd.DataFrame: pandas dataframe
    """
    df = pd.read_csv(fpath, sep=';')

    if only_drinking_water:
        # drop unknown type of water application
        nans = df['Drinking water or wastewater'].isnull()
        df = df[~nans]
        dw = (
            df['Drinking water or wastewater'].apply(
                str.lower) == 'drinking water'
                )
        df = df[dw].reset_index()
    if return_citation_keys:
        return df['Reference/partner'].unique()

    return df


def abates_alldata_in_dataframe(
    fpath: str,
    only_drinking_water: bool = True,
):
    header_mapping = {
        'Citation': 'citation',
        'Purpose of study': 'study_purpose',
        'Name': 'synonym_substance',
        'CAS id': 'cas_substance',
        'Molecular weight': 'mw',
        'Molecular size (Å)': 'molecular_size',
        'H-bonds': 'has_h-bonds',
        'Functional groups': 'functional_groups',
        'pKa': 'pka',
        'Log Kow': 'log_kow',
        'Description': 'substance_category',
        'SMILES': 'smiles',
        'Source': 'source',
        'Purity percentage': 'purity_percentage',
        'Composition of product formulation': 'composition_product',
        'Type of water': 'water_type',
        'DOM/NOM/DOC content': 'nom_content',
        'unit NOM concentration': 'nom_unit',
        'Type of treatment': 'treatment_type',
        'Specification treatment': 'treatment_spec',
        'Limitations': 'limitations_of_study',
        'Scale of experiemnt': 'scale_of_experiment',
        'Spiked': 'is_spiked',
        'mixture or single': 'mixture_or_single',
        'initial concentration': 'conc_initial_substance',
        'unit initial concentration': 'unit_initial_conc',
        'end (effluent) concentration': 'conc_effluent_substance',
        'unit effluent concentration': 'unit_effluent_conc',
        'concentration/dosage': 'dosage_concentration',
        'unit dosage': 'unit_dosage',
        'H2O2': 'h2o2_concentration',
        'peroxide concentration unit': 'unit_h2o2_conc',
        'contact time': 'contact_time',
        'time unit': 'unit_of_time',
        'Number of replicas': 'amount_replicas',
        'Efficiency high': 'efficiency_high',
        'Efficiency low': 'efficiency_low',
        '?': 'unknown',
        '(Average) efficiency': 'efficiency_avg',
        'Standard deviation in efficiency': 'efficiency_std',
        'Comments': 'comments',
        'Type of reference': 'publication_type'
    }
    dataframe = pd.read_csv(fpath, sep=';')
    dataframe.rename(columns=header_mapping, inplace=True)

    if only_drinking_water:
        dataframe.dropna(subset='water_type', inplace=True, axis=0)
        surface_wtr = dataframe['water_type'].map(str.lower) == 'surface water'
        drinking_wtr = dataframe['water_type'].map(str.lower) == 'drinking water'
        dataframe = dataframe[surface_wtr | drinking_wtr]

    selection = dataframe.dropna(subset='efficiency_avg')
    unnamed_columns = [col for col in selection.columns if 'Unnamed:' in col]
    selection.drop(columns=unnamed_columns, axis=0, inplace=True)

    return selection


def drop_not_analysed_substances(
        dataframe: pd.DataFrame,
        columns: Optional[Union[list, np.array]] = None,
):
    if columns is None:
        columns = dataframe.columns
    if len(columns) == 1:
        if isinstance(columns, list):
            columns = columns[0]
    dataframe[columns].replace(
        r"not\sanal[a-zA-Z]+", None, regex=True, inplace=True)

    dataframe.dropna(subset=columns, axis=0, inplace=True)

    return dataframe


def quantitative_binning_of_efficiencies(
        dataframe: pd.DataFrame,
        efficiency_columns: List[str],
        bins: List[float],
        drop: bool = False
        ) -> pd.DataFrame:

    new_columns = ['f{col}_bin' for col in efficiency_columns]
    dataframe[new_columns] = None

    for col in efficiency_columns:
        new_col = f'{col}_bin'
        dataframe[new_col] = np.digitize(x=dataframe[col], bins=bins)

    if drop:
        dataframe.drop(columns=efficiency_columns, inplace=True)

    return dataframe


def convert_columns_to_float(
        dataframe: pd.DataFrame,
        columns: List[Any]
        ):
    for col in columns:
        try:
            dataframe[col] = dataframe[col].astype(float)
        except ValueError:
            warn(
                f'{col} has a string which cannot be converted to a '
                'float. Conversion of this column will be skipped.')

    return dataframe


def aggregate_mean_stdev(
        dataframe: pd.DataFrame,
        grouping_columns: Optional[List[Any]] = None,
        column_to_agg: Optional[str] = None) -> pd.DataFrame:
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
        grouping_columns = ['synonym_substance', 'treatment_spec']
    if column_to_agg is None:
        column_to_agg = 'efficiency_avg'

    return dataframe.groupby(grouping_columns).agg(
        {column_to_agg: [np.mean, np.std]})


if __name__ == '__main__':
    efficiency_columns = ['efficiency_avg']
    dpath_abates = os.path.join(DPATH_RESEARCH, 'data/raw/abates')
    dpath_processed = os.path.join(DPATH_RESEARCH, 'data/processed/')
    
    fpath_studies = os.path.join(
        dpath_abates, 'DSS treatment techniques - studies.csv')
    fpath_master = os.path.join(
        dpath_abates, 'DSS treatment techniques - master.csv')
    studies = abates_studies_in_dataframe(
        fpath_studies, only_drinking_water=True, return_citation_keys=False)
    cit_keys = abates_studies_in_dataframe(
        fpath_studies, only_drinking_water=True, return_citation_keys=True)

    # load the master sheet
    master = abates_alldata_in_dataframe(fpath_master, only_drinking_water=True)
    master = drop_not_analysed_substances(
        dataframe=master, columns=efficiency_columns)
    master = convert_columns_to_float(
        dataframe=master, columns=efficiency_columns)
    master = quantitative_binning_of_efficiencies(
        dataframe=master, efficiency_columns=efficiency_columns,
        bins=[0., 25., 50., 75., 100.])
    by_substance = aggregate_mean_stdev(dataframe=master)
    by_substance.to_csv(
        os.path.join(dpath_processed, 'cecs_removal_eff_mean_std.csv'),
        index_label=['synonym_substance', 'treatment_spec'],
        sep=';')
    
    # pd.read_csv(os.path.join(dpath_processed, 'cecs_removal_eff_mean_std.csv'), 
    #             header=[0, 1], index_col=[0,1], sep=';')

