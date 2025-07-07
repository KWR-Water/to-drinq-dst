from typing import Dict, List, Any
import pandas as pd
from itertools import chain, product
from django.db.models import QuerySet
from django_pandas.io import read_frame
from string import ascii_uppercase

from drinq.models import (
    Technology, TechnologyDecidingFactors, DecidingFactor,
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
) -> list[int | None]:
    """
    Get the technology based on the choice string.
    """
    if query_set is None:
        query_set = TechnologyDecidingFactors.objects.all()
    try:
        technology_set = query_set.filter(choice_id=choice).values_list(
            'effective_technology', flat=True)
        return tuple(technology_set, )
    except TechnologyDecidingFactors.DoesNotExist:
        return None


def get_treatment_trains(technology_tuples: List[tuple]) -> List[Technology]:
    treatment_id_sets = get_unique_combinations(technology_tuples)
    number_of_options = len(treatment_id_sets)
    treatment_options, treatment_maps = {}, {}
    if number_of_options == 0:
        return treatment_options
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


def get_unique_combinations(combination_tuple):
    # Generate all possible ordered combinations
    """    Count unique combinations of technologies based on their indices.
    """
    combinations = product(*combination_tuple)
    unique_combinations = [tu for tu in combinations]

    return unique_combinations


def get_table_decidingfactors():
    return read_frame(DecidingFactor.objects.all())


def get_decidingfactor_all_ids(design_tree_id: int) -> List[int]:
    query_set = DecidingFactor.objects.all()
    child_dfs = query_set.filter(design_tree=design_tree_id).values_list(
        'parent', 'child').distinct()
    return list(set(chain.from_iterable(child_dfs)))


def get_decidingfactor_table(
    as_dataframe: bool = False,
    design_tree_id: int | None = None
) -> List[Dict[Any, Any]]:
    if design_tree_id is not None:
        ids = get_decidingfactor_all_ids(design_tree_id=design_tree_id)
    else:
        ids = [dcf.pk for dcf in DecidingFactor.objects.all()]
    if as_dataframe:
        return read_frame(DecidingFactor.objects.filter(pk__in=ids))
    deciding_factors = []
    columns = [field.name for field in DecidingFactor._meta.fields]
    columns.remove('id')
    for id in ids:
        selected = DecidingFactor.objects.get(pk=id)
        dec_factor = {'id': id}
        for table_col in columns:
            value = getattr(selected, table_col)
            if not (isinstance(value, float) or isinstance(value, str)):
                try:
                    value = getattr(selected, table_col).pk
                except AttributeError:
                    pass
            dec_factor.update({table_col: value})
        deciding_factors.append(dec_factor)
    return deciding_factors


if __name__ == '__main__':
    pass
    # design_tree = get_table_decidingfactors()
