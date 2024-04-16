from typing import Dict, List
from drinq.models import (
    Technology, Stage, TechnologyDecidingFactors, DecidingFactor,
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


def decision_stage_screening(form_data: dict) -> dict:

    result = {}
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
