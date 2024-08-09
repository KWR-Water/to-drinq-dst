import unittest

from drinq.decision_tree import (
    select_technologies_with_deciding_factor, get_decidingfactor_table,
    get_table_designtreedecidingfactors)


class Testget_table_designtreedecidingfactors(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.design_tree_id = 1
        cls.dfactor_surface_water = {
            'id': 1,
            'name': 'source_is_surface_water',
            'description': 'the intake water is surface water',
            'categorical_variable': 1
            }
        cls.dtree_dfactor = cls.dfactor_surface_water.update(
            {'design_tree': 'surface_water',
             'path_length': 1
             }
        )

    def test_select_decidingfactors(self):
        design_tree_id = 1
        expected_dict = {
            'id': 1,
            'name': 'source_is_surface_water',
            'description': 'the intake water is surface water',
            'categorical_variable': 1
            }
        expected_dict_df = expected_dict.copy()
        expected_dict_df['categorical_variable'] = 'Categorical variable (pk=1): dichotomous'
        result = get_decidingfactor_table(
            design_tree_id=design_tree_id, as_dataframe=False)
        self.assertEqual(result[0], expected_dict)
        result_df = get_decidingfactor_table(
            design_tree_id=design_tree_id, as_dataframe=True)
        dict_from_df = result_df[result_df['id']==1].to_dict('records')
        self.assertEqual(result[0], expected_dict)
        self.assertEqual(dict_from_df[0], expected_dict_df)

    def test_get_table_designtreedecidingfactors(self):
        expected_result = {
                'id': 1,
                'parent_decidingfactor': 'source_is_surface_water',
                'child_decidingfactor': 'high_algae',
                'design_tree': 'surface_water',
                'path_length': 1
                }

        result = get_table_designtreedecidingfactors().to_dict('records')
        self.assertEqual(result[0], expected_result)

    def test_select_technologies_with_deciding_factor(self):
        filter_conditions = [
            {'name': 'source_is_surface_water'},
            {'name': 'algae_high'}]
        expected_result = {
            'selected_technologies':
            [
                {'name': 'Microstrainer',
                 'description':
                    'Strainer with mesh opening between 10 to 40 micrometer to remove small particles and algae'},
            ]
        }
        result = select_technologies_with_deciding_factor(filter_conditions)
        self.assertEqual(result, expected_result)

