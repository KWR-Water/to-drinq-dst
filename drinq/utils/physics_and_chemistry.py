import numpy as np

GRAVITY_M_PER_S2 = 9.81  # m/s^2
DENS_WATER_KG_PER_M3 = 1000  # kg/m^3
METER_PER_BAR = 10.1972  # meters of water per bar
WATER_VISCOSITY_N_S_PER_M2 = 0.0010005  # N*s/m^2


def dynamic_viscosity_water_pa_s(temperature: float) -> float:
    """Calculate the dynamic viscosity of water as a function of temperature using
    the Vogel-Fulcher-Tammann approximation.

    Args:
        temperature (float): Temperature in degrees

    Returns:
        float: Dynamic viscosity of water in Pa.s
    """
    return 2.414e-5 * 10**(247.8 / (temperature + 133.15))


def reynolds_number_pipe(
    flow_m3perh: float,
    pipe_diameter_m: float,
    water_density_kg_per_m3: float = DENS_WATER_KG_PER_M3,
    water_viscosity_n_s_per_m2: float = WATER_VISCOSITY_N_S_PER_M2,
) -> float:
    """Calculate Reynolds number for flow in a pipe.

    Args:
        flow_m3perh (float): flow rate in m3/hr
        pipe_diameter_m (float): pipe diameter in meters
        fluid_viscosity_n_s_per_m2 (float): fluid viscosity in N*s/m^2

    Returns:
        float: Reynolds number
    """
    flow_m3_per_s = flow_m3perh / 3600  # Convert flow to m3/s
    cross_sectional_area_m2 = np.pi * (pipe_diameter_m / 2) ** 2
    velocity_m_per_s = flow_m3_per_s / cross_sectional_area_m2
    kin_viscosity_m2_per_s = (
        water_viscosity_n_s_per_m2 / water_density_kg_per_m3)
    reynolds_number = (velocity_m_per_s * pipe_diameter_m
                       ) / kin_viscosity_m2_per_s
    return reynolds_number


def friction_factor_pipe(
    reynolds_number: float,
    pipe_roughness_m: float = 0.00015,  # default for steel pipe
) -> float:
    """Calculate friction factor for flow in a pipe.

    Args:
        reynolds_number (float): Reynolds number
        pipe_roughness_m (float): pipe roughness in meters

    Returns:
        float: friction factor
    """
    if reynolds_number < 2300:
        return 64 / reynolds_number
    else:
        # Colebrook-White equation approximation, Swamee-Jaine formula
        # See https://en.wikipedia.org/wiki/Darcy_friction_factor_formulae
        f = 0.25 / (np.log10(
            (5.74 / reynolds_number**0.9) + (pipe_roughness_m / 3.7)
            ))**2
        return f


def calculate_pressure_drop_pipe(
    flow_m3perh: float,
    pipe_diameter_m: float,
    pipe_length_m: float,
    water_density_kg_per_m3: float = DENS_WATER_KG_PER_M3,
    water_viscosity_n_s_per_m2: float = WATER_VISCOSITY_N_S_PER_M2,
    pipe_roughness_m: float = 0.00015,  # default for steel pipe
) -> float:
    """Calculate pressure drop in a pipe using Darcy-Weisbach equation.

    Args:
        flow_m3perh (float): flow rate in m3/hr
        pipe_diameter_m (float): pipe diameter in meters
        pipe_length_m (float): pipe length in meters
        water_density_kg_per_m3 (float): water density in kg/m^3
        water_viscosity_n_s_per_m2 (float): water viscosity in N*s/m^2
        pipe_roughness_m (float): pipe roughness in meters

    Returns:
        float: pressure drop in bar
    """
    # TODO: check with Greg the formula and units
    reynolds_number = reynolds_number_pipe(
        flow_m3perh, pipe_diameter_m,
        water_density_kg_per_m3, water_viscosity_n_s_per_m2)
    friction_factor = friction_factor_pipe(
        reynolds_number, pipe_roughness_m)
    flow_m3_per_s = flow_m3perh / 3600  # Convert flow to m3/s
    cross_sectional_area_m2 = np.pi * (pipe_diameter_m / 2) ** 2
    velocity_m_per_s = flow_m3_per_s / cross_sectional_area_m2
    pressure_drop_pa = (
        friction_factor * (pipe_length_m / pipe_diameter_m) *
        0.5 * water_density_kg_per_m3 * velocity_m_per_s**2)
    pressure_drop_bar = pressure_drop_pa / 1e5  # Convert Pa to bar
    return pressure_drop_bar