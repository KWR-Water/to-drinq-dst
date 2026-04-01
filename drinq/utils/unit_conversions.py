def lppd_to_m3phr(flow_in_liter_per_day: float):
    return flow_in_liter_per_day / 1000 / 24


def bar_to_meters_of_water(headloss_bar: float):
    return headloss_bar * 10.1972  # Convert bar to meters of water


def meters_of_water_to_bar(headloss_meters: float):
    return headloss_meters / 10.1972  # Convert meters of water to bar


def density_from_g_per_cm3_to_kg_per_m3(
    density_g_per_cm3: float
) -> float:
    """Convert density from g/cm^3 to kg/m^3.

    Args:
        density_g_per_cm3 (float): Density in g/cm^3

    Returns:
        float: Density in kg/m^3
    """
    return density_g_per_cm3 * 1000
