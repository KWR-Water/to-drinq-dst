import unittest
import pandas as pd
import os
import sys

try:
    import research
except ModuleNotFoundError:
    myPath = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, myPath + '/../')

from research.ingest_abates_data import (
    convert_columns_to_float, abates_alldata_in_dataframe,
    abates_studies_in_dataframe, drop_not_analysed_substances, DPATH_RESEARCH,
)

DPATH_ABATES = os.path.join(DPATH_RESEARCH, 'data/raw/abates')
FPATH_MASTER = os.path.join(
    DPATH_ABATES, 'DSS treatment techniques - master.csv')
FPATH_STUDIES = os.path.join(
    DPATH_ABATES, 'DSS treatment techniques - studies.csv')


class Testabates_studies_in_dataframe(unittest.TestCase):

    def test_load_studies_citation_keys_csv_file(self):
        result = abates_studies_in_dataframe(
            FPATH_STUDIES, return_citation_keys=True)
        expected_result = [
            'Alder, et al (2010)',
            'Altmann, et al (2014)',
            'Asakura and Masuto, 2009'
            ]
        result.sort()

        self.assertEqual(len(result), 37)
        self.assertEqual(result[:3], expected_result)

    def test_abates_studies_filter_dw_sources(self):
        fpath = FPATH_STUDIES
        only_drinking_water = True
        return_citation_keys = False
        replace_greek_characters = True
        expected_dict = {
            'index': 0,
            'Reference/partner': (
                'Removal of EDCs and Pharmaceuticals in Drinking and Reuse '
                'Treatment Processes'),
            'Emerging substance': '17 beta-estradiol',
            'treatmentId': 332,
            'Drinking water or wastewater': 'Drinking water',
            'Comments': 'pH=5,5',
            'Contact/EBCT/retention time': '24',
            'Type of treatment': 'Oxidation',
            'Efficiency': '97',
            'Specification treatment': 'Chlorination',
            'Time Type': 'hrs',
            'Dosage': '6.75',
            'Unit': 'mg/L',
        }

        result = abates_studies_in_dataframe(
            fpath, only_drinking_water, return_citation_keys,
            replace_greek_characters)

        # Assert
        self.assertIsInstance(result, pd.DataFrame)
        self.assertEqual(result.iloc[0].dropna().to_dict(), expected_dict)

    def test_return_whole_studies_sheet(self):
        fpath = FPATH_STUDIES
        expected_output = pd.read_csv(fpath, sep=';')
        result = abates_studies_in_dataframe(
            fpath, return_citation_keys=False, replace_greek_characters=False)
        pd.testing.assert_frame_equal(result, expected_output)

    def test_load_master_sheet(self):
        fpath_master = FPATH_MASTER
        only_drinking_water = True

        result = abates_alldata_in_dataframe(fpath_master, only_drinking_water)

        self.assertIsInstance(result, pd.DataFrame)
        self.assertEqual(len(result), 1412)
        self.assertEqual(result.columns[0], 'citation')
        self.assertEqual(result.columns[-1], 'publication_type')

    def test_drop_not_analysed_substances(self):
        # Create a sample dataframe
        df = pd.DataFrame({'Substance': ['A', 'B', 'C', 'not analyzed'],
                           'Value': [1, 2, 3, 4]})

        # Drop substances that were not analyzed
        df = drop_not_analysed_substances(df, columns='Substance')

        # Check if 'not analyzed' substances are dropped
        self.assertNotIn('not analyzed', df['Substance'].values)

        # Check if other substances are still present
        self.assertIn('A', df['Substance'].values)
        self.assertIn('B', df['Substance'].values)
        self.assertIn('C', df['Substance'].values)

    def test_convert_columns_to_float(self):
        # Create a sample dataframe
        df = pd.DataFrame({'col1': ['1', '2', '3'], 'col2': ['4', '5', '6']})

        # Convert specified columns to float
        columns = ['col1', 'col2']
        df = convert_columns_to_float(df, columns)

        # Check if the columns are converted to float
        self.assertTrue(df['col1'].dtype == float)
        self.assertTrue(df['col2'].dtype == float)
