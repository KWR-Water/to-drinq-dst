from typing import Dict, List, Any
import pandas as pd
from itertools import chain
from django_pandas.io import read_frame

from drinq.models import (
    Technology, Stage, TechnologyDecidingFactors, DecidingFactor, DesignTree,
    DesignTreeDecidingFactors,
)


def select_technologies_with_deciding_factor(
    filter_conditions: List[Dict[str, str]]
) -> Dict[str, str]:

    result = {}
    primary_keys_df = []
    query_set = DecidingFactor.objects.all()
    # First get the primary key values that match the conditions
    for condition in filter_conditions:
        query_set = query_set.filter(**condition)
        if query_set.exists():
            primary_keys_df.append(DecidingFactor.objects.get(**condition).pk)
        else:
            # TODO output logging message?
            pass
    if primary_keys_df:
        query_set = TechnologyDecidingFactors.objects.all()
        for pk_df in primary_keys_df:
            # Then get the technologies by filtering for the deciding factor
            # primary keys
            query_set = query_set.filter(
                deciding_factor_true=pk_df).values_list(
                'effective_technology', flat=True).distinct()
        technologies = []
        for pk in query_set:
            technologies.append({
                'name': Technology.objects.get(pk=pk).name,
                'description': Technology.objects.get(pk=pk).description
            })
        result['selected_technologies'] = technologies

    return result


def get_table_designtreedecidingfactors():
    return read_frame(DesignTreeDecidingFactors.objects.all())


def get_decidingfactor_all_ids(design_tree_id: int) -> List[int]:
    query_set = DesignTreeDecidingFactors.objects.all()
    child_dfs = query_set.filter(design_tree=design_tree_id).values_list(
        'parent_decidingfactor', 'child_decidingfactor').distinct()
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


def decision_stage_screening(
    form_data: dict,
    design_tree: int
) -> dict:

    result = {}

    # First, select the relevant questions (deciding factors)
    deciding_factors = get_decidingfactor_table(
        as_dataframe=True,
        design_tree_id=design_tree)

    # TODO: design a staged approach, where per stage different questions are
    # asked and some questions depend on other choices. Hence, per stage, also
    # a dependency on historic choices.
    # TODO: read from table decision_factor
    source_is_surfacewater, algae_high, nom_high = (
        form_data['source_is_surfacewater'],
        form_data['algae_high'],
        form_data['nom_high'],
    )
    conditions = []
    # STEP 1
    if source_is_surfacewater:
        conditions.append({'name': 'source_is_surface_water'})
    if algae_high:
        conditions.append({'name': 'algae_high'})

    result.update(select_technologies_with_deciding_factor(conditions))
    # TODO: register 1st stage in chain of technology stages

    # STEP 2 - TODO
    # conditions = []
    # if nom_high:
    #     conditions = [{'name': 'nom_high'}]

    result.update(form_data)
    return result


if __name__ == '__main__':
    design_tree = get_table_designtreedecidingfactors()
