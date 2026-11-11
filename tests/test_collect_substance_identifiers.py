import unittest
from unittest.mock import patch
import pandas as pd

import os
import sys

try:
    import research
except ModuleNotFoundError:
    myPath = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, myPath + '/../')

from research.collect_substance_identifiers import (
    get_synonyms_and_cid, get_pcp_properties_from_cid, resolve_by_cirpy
    )


class Testget_synonyms_and_cid(unittest.TestCase):

    def test_valid_compound_name(self):
        compound_name = 'aspirin'
        expected_cid = 2244

        with (
            patch(
                'research.collect_substance_identifiers.pcp.get_synonyms',
                return_value=[{'Synonym': [compound_name]}],
            ),
            patch(
                'research.collect_substance_identifiers.pcp.get_cids',
                return_value=[expected_cid],
            ),
        ):
            result = get_synonyms_and_cid(compound_name)

        self.assertEqual(result.loc[compound_name, 'cid'], expected_cid)
        self.assertIn(
            compound_name, result.loc[compound_name, 'compound_synonyms'])

    def test_returned_dataframe_pcp_properties(self):
        cid = '12345'
        expected_columns = [
            'IsomericSMILES', 'InChI', 'InChIKey', 'MolecularFormula']
        expected_index = pd.Index([cid], name='cid')
        expected_row = {
            'IsomericSMILES': 'CC(=O)OCOC(=O)C',
            'InChI': 'InChI=1S/C5H8O4/c1-4(6)8-3-9-5(2)7/h3H2,1-2H3',
            'InChIKey': 'BPGDAMSIGCZZLK-UHFFFAOYSA-N',
            'MolecularFormula': 'C5H8O4',
        }
        expected_result = pd.DataFrame(
            [expected_row], columns=expected_columns, index=expected_index)

        with patch(
            'research.collect_substance_identifiers.pcp.get_properties',
            return_value=[expected_row],
        ):
            result = get_pcp_properties_from_cid(cid)

        self.assertIsInstance(result, pd.DataFrame)
        self.assertCountEqual(result.columns, expected_columns)
        self.assertEqual(result.index.name, expected_index.name)
        self.assertCountEqual(result.index, expected_index)
        pd.testing.assert_frame_equal(
            result, expected_result, check_names=False)

    def test_none_cid(self):
        with self.assertRaises(ValueError):
            get_pcp_properties_from_cid(None)

    def test_resolve_by_cirpy_valid_cid(self):
        compound_list = ['water', 'ethanol', 'methanol']
        # cids = [962, 702, 887]
        target_identifier = 'cas'
        expected_result = pd.DataFrame(
            {'common_name': compound_list,
             'cas': [
                 ['14314-42-2', '558440-22-5', '13670-17-2', '7732-18-5',
                  '17778-80-2'],
                 ['121182-78-3', '64-17-5', '8024-45-1', '8000-16-6',
                  '68475-56-9', '71076-86-3', '71329-38-9'],
                 ['54841-71-3', '67-56-1'],
                 ]}
             ).set_index('common_name', drop=True)

        with patch(
            'research.collect_substance_identifiers.cirpy.resolve',
            side_effect=expected_result['cas'].tolist(),
        ):
            result = resolve_by_cirpy(
                compound_list, target_identifier=target_identifier)
        pd.testing.assert_frame_equal(result, expected_result)


if __name__ == '__main__':
    unittest.main()
