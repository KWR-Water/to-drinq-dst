# import unittest
import django
from django.test import TestCase
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "drinq.settings")
django.setup()

from drinq.models import Technology
from drinq.decision_tree import get_unique_combinations

# from drinq.decision_tree import (
#     get_decidingfactor_table,
#     get_table_decidingfactors)


class GetUniqueCombinationsMembraneFlocculationTests(TestCase):
    """Membrane-based NOM removal (MF/UF) does not require a separate
    flocculation step, but the decision tree injects Coagulation and
    Flocculation unconditionally before it even knows whether MF/UF
    will be chosen. get_unique_combinations() is responsible for
    dropping Flocculation from any option that also selects a
    membrane technology.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.screening = Technology.objects.create(name='Strainer')
        cls.coagulant = Technology.objects.create(
            name='Coagulant dosing with ferric chloride by dynamic mixing')
        cls.flocculation = Technology.objects.create(
            name='Flocculation with dynamic mixing')
        cls.membrane = Technology.objects.create(
            name='Polymeric microfiltration')
        cls.rapid_sand = Technology.objects.create(
            name='Rapid sand filtration, submerged, dual media, sand')

    def test_flocculation_dropped_when_membrane_present(self):
        technology_tuples = [
            (self.screening.id,),
            (self.coagulant.id,),
            (self.flocculation.id,),
            (self.membrane.id, self.rapid_sand.id),
        ]

        combinations = get_unique_combinations(technology_tuples)

        self.assertIn(
            (self.screening.id, self.coagulant.id, self.membrane.id),
            combinations)
        self.assertNotIn(
            (
                self.screening.id, self.coagulant.id,
                self.flocculation.id, self.membrane.id,
            ),
            combinations)

    def test_flocculation_kept_when_no_membrane_present(self):
        technology_tuples = [
            (self.screening.id,),
            (self.coagulant.id,),
            (self.flocculation.id,),
            (self.rapid_sand.id,),
        ]

        combinations = get_unique_combinations(technology_tuples)

        self.assertIn(
            (
                self.screening.id, self.coagulant.id,
                self.flocculation.id, self.rapid_sand.id,
            ),
            combinations)

    def test_no_duplicate_combinations_after_dropping_flocculation(self):
        technology_tuples = [
            (self.coagulant.id,),
            (self.flocculation.id,),
            (self.membrane.id,),
        ]

        combinations = get_unique_combinations(technology_tuples)

        self.assertEqual(len(combinations), len(set(combinations)))
        self.assertEqual(
            combinations, [(self.coagulant.id, self.membrane.id)])



# class Testget_table_designtreedecidingfactors(TestCase):
#     @classmethod
#     def setUpClass(cls):
#         super(Testget_table_designtreedecidingfactors, cls).setUpClass()
#         cls.design_tree_id = 1
#         cls.dfactor_surface_water = {
#             'id': 1,
#             'name': 'source_is_surface_water',
#             'description': 'the intake water is surface water',
#             'categorical_variable': 1
#             }
#         cls.dtree_dfactor = cls.dfactor_surface_water.update(
#             {'design_tree': 'surface_water',
#              'path_length': 1
#              }
#         )

#     def test_select_decidingfactors(self):
#         design_tree_id = 1
#         expected_dict = {
#             'id': 1,
#             'name': 'source_is_surface_water',
#             'description': 'the intake water is surface water',
#             'form_label': 'Has large amounts of algae',
#             'categorical_variable': 1
#             }
#         expected_dict_df = expected_dict.copy()
#         expected_dict_df['categorical_variable'] = 'Categorical variable (pk=1): dichotomous'
#         result = get_decidingfactor_table(
#             design_tree_id=design_tree_id, as_dataframe=False)
#         self.assertEqual(result[0], expected_dict)
#         result_df = get_decidingfactor_table(
#             design_tree_id=design_tree_id, as_dataframe=True)
#         dict_from_df = result_df[result_df['id'] == 1].to_dict('records')
#         self.assertEqual(result[0], expected_dict)
#         self.assertEqual(dict_from_df[0], expected_dict_df)

#     def test_get_table_designtreedecidingfactors(self):
#         expected_result_0 = {
#                 'id': 1,
#                 'parent': 'source_is_surface_water',
#                 'child': 'high_algae',
#                 'design_tree': 'surface_water',
#                 'path_length': 1
#         }
#         expected_result_2 = {
#             'id': 3,
#             'parent': 'turbidity_high',
#             'child': 'mf_uf_required',
#             'design_tree': 'surface_water',
#             'path_length': 1
#         }

#         result = get_table_decidingfactors().to_dict('records')
#         self.assertEqual(result[0], expected_result_0)
#         self.assertEqual(result[2], expected_result_2)


