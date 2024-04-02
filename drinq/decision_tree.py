from drinq.models import (
    Technology, Stage, TechnologyDecidingFactors, DecidingFactor,
    )


def decision_stage_screening(form_data: dict):

    source_is_surfacewater, algae_high, nom_high = (
        form_data['source_is_surfacewater'],
        form_data['algae_high'],
        form_data['nom_high'],
        )
    if source_is_surfacewater:
        # include coarse strainer
        try:
            d_f = DecidingFactor.objects.get(name='source_is_surface_water')
            d_f_pk = d_f.pk
        except DecidingFactor.DoesNotExist:
            # TODO output logging message?
            pass
        selected_technologies = TechnologyDecidingFactors.objects.filter(
            TechnologyDecidingFactors.deciding_factor_true == d_f_pk
        ).all()  # TODO: select effective technologies

    if algae_high:
        selected_technologies = None
    return selected_technologies
