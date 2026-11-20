from typing import Dict, List, Any
import pandas as pd
from itertools import chain, product
from django.db.models import Q, QuerySet
from django_pandas.io import read_frame
from string import ascii_uppercase

from drinq.models import (
    Technology, TechnologyDecidingFactorJunction, DecidingFactor,
    DecidingFactorChoice
)


def get_choice_description(choice: int, query_set: QuerySet | None = None):
    """
    Get the description of a choice based on its ID.
    """
    if query_set is None:
        query_set = DecidingFactorChoice.objects.all()
    try:
        choice_description = query_set.get(id=choice).text
        return choice_description
    except DecidingFactorChoice.DoesNotExist:
        return None


def get_technology_of_choice(
    choice: int, query_set: QuerySet | None = None
) -> tuple[int, ...] | None:
    """
    Get the technology based on the choice string.
    """
    if query_set is None:
        query_set = TechnologyDecidingFactorJunction.objects.all()
    try:
        technology_set = query_set.filter(choice_id=choice).values_list(
            'effective_technology', flat=True)
        if technology_set.first():
            return tuple(technology_set)
        else:
            return None
    except TechnologyDecidingFactorJunction.DoesNotExist:
        return None


def get_treatment_trains(
    technology_tuples: List[tuple[int, ...]]
) -> tuple[dict, dict]:
    treatment_id_sets = get_unique_combinations(technology_tuples)
    number_of_options = len(treatment_id_sets)
    treatment_options, treatment_maps = {}, {}
    if number_of_options == 0:
        return treatment_options, treatment_maps
    elif number_of_options >= 1:
        for opt_nr, option in enumerate(treatment_id_sets):
            treatment_options[opt_nr+1] = {
                'steps': {},
                'id': None,
                'already_named': False,
                'slug': None,
                }
            treatment_maps[opt_nr+1] = {}
            for tech_nr, technology_id in enumerate(option):
                technology = Technology.objects.get(id=technology_id)
                if technology is not None:
                    if technology.name is not None:
                        if (
                            technology.name.lower() == 'no technology'
                            or technology.name.lower() == 'dummy technology'):
                            continue
                    if tech_nr not in treatment_options[opt_nr+1]['steps']:
                        # Initialize the technology entry if it doesn't exist
                        treatment_options[opt_nr+1]['steps'] = {tech_nr+1: {}}
                    if tech_nr+1 not in treatment_maps[opt_nr+1]:
                        treatment_maps[opt_nr+1][tech_nr+1] = {}
                    treatment_maps[opt_nr+1][tech_nr+1] = {
                        'technology': technology_id}
                    treatment_options[opt_nr+1]['steps'][tech_nr+1] = {
                        'name': technology.name,
                        'description': technology.description,
                    }
    return treatment_options, treatment_maps


def _get_membrane_technology_ids(
    query_set: QuerySet | None = None,
) -> set[int]:
    """IDs of membrane-based NOM removal technologies (MF/UF)."""
    if query_set is None:
        query_set = Technology.objects.all()
    return set(
        query_set.filter(
            Q(name__icontains='microfiltration') |
            Q(name__icontains='ultrafiltration')
        ).values_list('id', flat=True)
    )


def _get_flocculation_technology_ids(
    query_set: QuerySet | None = None,
) -> set[int]:
    """IDs of flocculation technologies."""
    if query_set is None:
        query_set = Technology.objects.all()
    return set(
        query_set.filter(
            name__icontains='flocculation'
        ).values_list('id', flat=True)
    )


def _drop_flocculation_for_membrane_combination(
    combination: tuple[int, ...],
    membrane_ids: set[int],
    flocculation_ids: set[int],
) -> tuple[int, ...]:
    """Drop flocculation technologies from a combination that also
    selects a membrane technology.

    Coagulation/flocculation pretreatment is injected unconditionally
    earlier in the decision tree (before the MF/UF question is even
    asked), so it ends up paired with membrane-based NOM removal even
    though membrane filtration does not require it.
    """
    if not flocculation_ids or membrane_ids.isdisjoint(combination):
        return combination
    return tuple(
        technology_id for technology_id in combination
        if technology_id not in flocculation_ids
    )


def get_unique_combinations(combination_tuple):
    """Count unique combinations of technologies based on their indices.

    Generates all possible ordered combinations (one technology per
    stage bucket), then drops Flocculation from any combination that
    also includes a membrane (MF/UF) technology.
    """
    combinations = product(*combination_tuple)
    membrane_ids = _get_membrane_technology_ids()
    flocculation_ids = _get_flocculation_technology_ids()

    unique_combinations: list[tuple[int, ...]] = []
    seen: set[tuple[int, ...]] = set()
    for combination in combinations:
        combination = _drop_flocculation_for_membrane_combination(
            combination, membrane_ids, flocculation_ids)
        if combination not in seen:
            seen.add(combination)
            unique_combinations.append(combination)

    return unique_combinations


# def get_table_decidingfactors():
#     return read_frame(DecidingFactor.objects.all())


# def get_decidingfactor_all_ids(design_tree_id: int) -> List[int]:
#     query_set = DecidingFactor.objects.all()
#     child_dfs = query_set.filter(design_tree=design_tree_id).values_list(
#         'parent', 'child').distinct()
#     return list(set(chain.from_iterable(child_dfs)))


# def get_decidingfactor_table(
#     as_dataframe: bool = False,
#     design_tree_id: int | None = None
# ) -> List[Dict[Any, Any]]:
#     if design_tree_id is not None:
#         ids = get_decidingfactor_all_ids(design_tree_id=design_tree_id)
#     else:
#         ids = [dcf.pk for dcf in DecidingFactor.objects.all()]
#     if as_dataframe:
#         return read_frame(DecidingFactor.objects.filter(pk__in=ids))
#     deciding_factors = []
#     columns = [field.name for field in DecidingFactor._meta.fields]
#     columns.remove('id')
#     for id in ids:
#         selected = DecidingFactor.objects.get(pk=id)
#         dec_factor = {'id': id}
#         for table_col in columns:
#             value = getattr(selected, table_col)
#             if not (isinstance(value, float) or isinstance(value, str)):
#                 try:
#                     value = getattr(selected, table_col).pk
#                 except AttributeError:
#                     pass
#             dec_factor.update({table_col: value})
#         deciding_factors.append(dec_factor)
#     return deciding_factors


if __name__ == '__main__':
    pass
    # design_tree = get_table_decidingfactors()
