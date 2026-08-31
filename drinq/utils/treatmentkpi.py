import numpy as np
import math
from abc import ABC, abstractmethod
from dataclasses import dataclass
from drinq.utils.unit_conversions import (
    lppd_to_m3phr, bar_to_meters_of_water, meters_of_water_to_bar)
from drinq.utils.physics_and_chemistry import (
    DENS_WATER_KG_PER_M3,
    WATER_VISCOSITY_N_S_PER_M2,
    GRAVITY_M_PER_S2,
    METER_PER_BAR,
    friction_factor_pipe,
    reynolds_number_pipe,
    calculate_pressure_drop_pipe
)
import json


# NOTE: The keys of these mappings SHOULD BE in sync with
# the database table!
TECH_KPI_MAPPINGS = {
    'footprint area': 'footprint_area__m2',
    'footprint area for chemicals': 'footprint_area_for_chemicals__m2',
    'daily energy consumption': 'daily_energy_consumption__kwh',
    'daily mass of chemicals': 'daily_mass_of_chemicals__kg',
    'chemical solution concentration': 'chemical_solution_concentration__mg_per_l',  # noqa: E501
    'head loss': 'hydraulic_headloss__bar',
    'power': 'power__kw',
    'CO2 equivalent emissions': 'co2_emissions__kg_co2_eq_per_m3',
}

INPUT_WQPARAMETER_KEY = 'input_parameter'
TARGET_WQPARAMETER_KEY = 'target_parameter'


# IMPORTANT PROPERTIES FOR COST CALCULATIONS
# - volume (m3)
# - filter area (m2)
# - membrane area (m2)
# - dosing flow rate (1e-3 m3/hr) []
# - area (m2) [Strainer, Microstrainer, Chain-scraped sedimentation tank, Lamella clarifier, DAF, PAC, Pellet softening, sludge blanket filtr]  # noqa: E501

"""
NOTE: We import all the parameter names from a json file. This file SHOULD BE 
kept in sync with the database table "technologyproperty"!
"""
with open("drinq/utils/treatmentpropertyname.json", "r") as file:
    TPN = json.load(file)
with open("drinq/utils/treatmentplantpropertyname.json", "r") as file:
    TPPN = json.load(file)

NOMINAL_FLOW_RATE_NAME = TPPN['nominal_flow_rate']
EMISSION_FACTOR_ELEC_NAME = 'emission factor (electricity)'
NR_OF_LANES_NAME = 'number of lanes'


def match_tech_kpi(kpi_fullname: str) -> str:
    """Match user-provided KPI name to available KPIs.

    Args:
        kpi_name (str): The name of the KPI to match. This name should
        correspond to the KPIs defined in table "technologykpi".
    """
    KPI_reverse_mappings = {v: k for k, v in TECH_KPI_MAPPINGS.items()}
    if kpi_fullname.lower() in KPI_reverse_mappings.keys():
        return KPI_reverse_mappings[kpi_fullname.lower()]
    raise ValueError(f"KPI '{kpi_fullname}' not found in available KPIs.")


def get_value_from_dictionary_lower_str(
    dictionary: dict[str, str],
    value: str,
) -> str:
    """Get value from dictionary with case-insensitive key matching.

    Args:
        dictionary (dict): Dictionary to search.
        key (str): Key to search for.
    Returns:
        value: Value associated with the matched key.
    """
    if value.lower() not in dictionary.keys():
        raise ValueError(f"Value '{value}' does not exist.")
    return dictionary[value.lower()]


@dataclass
class TreatmentDataclassMixin:
    """Dataclass mixin for treatment KPIs.

    Args:
        parameters (dict): Dictionary of technology parameters.
        design_parameters (dict): Dictionary of plant design parameters.
        plant_kpis (dict): Dictionary of plant performance indicators.
        digest_parameter_list (list[str], optional): List of parameter names 
            which are digested for cost or other calculations. Defaults to None.
    """
    parameters: dict[str, float | int | str]
    design_parameters: dict[str, float | int | str]
    plant_kpis: dict[str, float | int | str]
    wq_parameters: dict[str, dict[str, float | int | str]] | None = None
    chem_parameters: list[str] | None = None
    digest_parameter_list: list[str] | None = None

    def __post_init__(self):
        self.parameters = self.parameters
        self.wq_parameters = self.wq_parameters
        self.design_parameters = self.design_parameters
        self.plant_kpis = self.plant_kpis
        self.chem_parameters = self.chem_parameters
        if self.digest_parameter_list is not None and len(self.digest_parameter_list) == 0:
            self.digest_parameter_list = None
        self.digest_parameter_list = self.digest_parameter_list


class TreatmentKPI(ABC, TreatmentDataclassMixin):
    """Abstract base class for treatment KPIs."""


    @abstractmethod
    def get_kpi(self, kpi_name: str) -> float | dict[str, float]:
        """Get the value of the specified KPI."""
        raise NotImplementedError("Subclasses should implement this method")

    @abstractmethod
    def __repr__(self):
        """Return a string representation of the current treatment KPI."""
        return f"{self.__class__.__name__}()"

    @abstractmethod
    def get_kpi_dict(self) -> dict:
        raise NotImplementedError("Subclasses should implement this method")

    @property
    @abstractmethod
    def footprint_area__m2(self) -> float:
        """Abstract property for footprint area (m2)."""
        pass

    @property
    @abstractmethod
    def footprint_area_for_chemicals__m2(self) -> float:
        """Abstract property for chemical storage area (m2)."""
        pass

    @property
    def daily_energy_consumption__kwh(self) -> float:
        """Default: daily energy consumption based on continuous operation."""
        return self.power__kw * 24

    @property
    @abstractmethod
    def daily_mass_of_chemicals__kg(self) -> dict[str, float]:
        """Abstract property for daily mass of chemicals (kg)."""
        pass

    def chemical_names(self) -> list[str]:
        if not self.chem_parameters:
            return []
        return [name for name in self.chem_parameters if isinstance(name, str)]

    def _single_chemical_value(self, value: float) -> dict[str, float]:
        names = self.chemical_names()
        if not names:
            return {}
        return {names[0]: value}

    def _resolve_per_chemical_factors(
        self,
        factor: float | dict[str, float] | None,
        default_value: float = 0.0,
    ) -> dict[str, float]:
        names = self.chemical_names()
        if not names:
            return {}
        if isinstance(factor, dict):
            if len(names) == 1 and names[0] not in factor and factor:
                return {names[0]: next(iter(factor.values()))}
            return {
                name: float(factor.get(name, default_value))
                for name in names
            }
        value = default_value if factor is None else float(factor)
        return {name: value for name in names}

    def sum_per_chemical(self, values_by_chemical: dict[str, float]) -> float:
        return float(sum(values_by_chemical.values()))

    def chemical_costs__eur_per_day(
        self,
        chemical_prices: float | dict[str, float] | None,
    ) -> float:
        masses = self.daily_mass_of_chemicals__kg
        if not masses:
            return 0.0
        if isinstance(chemical_prices, dict):
            if len(masses) == 1 and next(iter(masses)) not in chemical_prices and chemical_prices:
                unit_price = float(next(iter(chemical_prices.values())))
                return self.sum_per_chemical(masses) * unit_price
            return sum(
                float(mass) * float(chemical_prices.get(name, 0.0))
                for name, mass in masses.items()
            )
        unit_price = 0.0 if chemical_prices is None else float(chemical_prices)
        return self.sum_per_chemical(masses) * unit_price

    @property
    @abstractmethod
    def chemical_solution_concentration__mg_per_l(self) -> float:
        """Abstract property for chemical solution concentration (mg/L)."""
        pass

    @property
    @abstractmethod
    def hydraulic_headloss__bar(self) -> float:
        """Abstract property for hydraulic headloss (bar)."""
        pass

    @property
    @abstractmethod
    def power__kw(self) -> float:
        """Abstract property for power (kW)."""
        pass

    @property
    @abstractmethod
    def co2_emissions__kg_co2_eq_per_m3(self) -> float:
        """Abstract property for CO2 emissions (kg CO2 eq/m3)."""
        pass


def calculate_flow_per_lane(
    lanes: int,
    flow_m3perh: float,
) -> float:
    if flow_m3perh is None:
        raise ValueError("Flow (m3/hr) must be provided.")
    return flow_m3perh / lanes


def calculate_flow_per_unit(
    units: int,
    flow_per_lane: float
) -> float:
    return flow_per_lane / units


def calculate_unit_volume_m3(
    flow_per_lane_m3h: float,
    units_per_lane: int,
    retention_time_min: float,
) -> float:
    return flow_per_lane_m3h * retention_time_min / 60 / units_per_lane


def calculate_unit_area_tank(
    unit_volume_m3: float,
    unit_height_m: float,
) -> float:
    """Calculate unit area of tank in m2.

    Args:
        unit_volume_m3 (float): volume of the tank in m3
        unit_height_m (float): height of the tank in m
    """
    if unit_height_m <= 0:
        raise ValueError("Tank height must be greater than zero.")
    return unit_volume_m3 / unit_height_m


def calculate_dosing_mass__perday_perunit(
    concentration_mgL: float,
    flow_per_lane_m3hr: float,
    units_per_lane: int,
) -> float:
    """Calculate dosing mass in kg/day per unit.

    Args:
        concentration_mgL (float): concentration in mg/L
        flow_per_lane_m3hr (float): flow per lane in m3/hr
        units_per_lane (int): number of units per lane
    """
    if units_per_lane <= 0:
        raise ValueError("Units per lane must be greater than zero.")
    # 24 hr/day * g/m3 * m3/hr / 1e3 g/kg --> kg/day (1 mg/L = 1 g/m3)
    return 24 * concentration_mgL * flow_per_lane_m3hr / 1e3 / units_per_lane


def calculate_dosing_volume__m3perday_perunit(
    concentration_mgL: float,
    flow_per_lane_m3hr: float,
    units_per_lane: int,
    solution_concentration_w_w_percent: float,
) -> float:
    """Calculate dosing volume in m3/day per unit.

    Args:
        concentration_mgL (float): concentration in mg/L
        flow_per_lane_m3hr (float): flow per lane in m3/hr
        units_per_lane (int): number of units per lane
        solution_concentration_w_w_percent (float): solution concentration in w/w%
    
    Returns:
        float: dosing volume in m3/day per unit
    """
    if solution_concentration_w_w_percent <= 0:
        raise ValueError("Solution concentration must be greater than zero.")
    mass_dosing_kgday_perunit = calculate_dosing_mass__perday_perunit(
        concentration_mgL=concentration_mgL,
        flow_per_lane_m3hr=flow_per_lane_m3hr,
        units_per_lane=units_per_lane,
    )
    # volume = mass / (concentration * density)
    # assuming density of water 1000 kg/m3
    return mass_dosing_kgday_perunit / (
        (solution_concentration_w_w_percent / 100) * DENS_WATER_KG_PER_M3)


def calculate_dosing_flow_rate__m3perhr(
    volume_dosing_m3perday_perunit: float,
    units_per_lane: int,
    lanes: int,
) -> float:
    """Calculate dosing flow rate in m3/hr.

    Args:
        volume_dosing_m3perday_perunit (float): dosing volume in 
            m3/day/unit
        units_per_lane (int): number of units per lane
        lanes (int): number of lanes
    Returns:
        float: dosing flow rate in m3/hr
    """
    return volume_dosing_m3perday_perunit * units_per_lane * lanes / 24


def calculate_chemical_storage_area__m2(
    daily_volume_m3perday: float,
    storage_time_days: float,
    tank_height_m: float,
    space_factor: float = 1.0,
) -> float:
    """Calculate chemical storage area in m2.

    Args:
        daily_volume_m3perday (float): daily volume in m3/day
        storage_time_days (float): storage time in days
        tank_height_m (float): tank height in m
        space_factor (float): factor to account for additional space
            requirements.

    Returns:
        float: chemical storage area in m2
    """
    if tank_height_m <= 0:
        raise ValueError("Tank height must be greater than zero.")    
    return space_factor * (
        daily_volume_m3perday * storage_time_days) / tank_height_m


def calculate_chlorine_concentration_mgL(
    residual_chlorine_mgL: float,
    dosing_solution_concentration_w_w: float,
) -> float:
    """Calculate chlorine dosing concentration in mg/L.

    Args:
        residual_chlorine_mgL (float): target residual chlorine concentration 
            in mg/L
        dosing_solution_concentration_w_w (float): chlorine solution 
            concentration in w/w%
    """
    if dosing_solution_concentration_w_w <= 0:
        raise ValueError(
            "Dosing solution concentration must be greater than zero."
        )
    return residual_chlorine_mgL * 6 / dosing_solution_concentration_w_w


def calculate_ammonia_concentration_mgL(
        target_chlorine_mgL: float,
        chlorine_to_ammonia_ratio: float = 5,) -> float:
    """Calculate ammonia dosing concentration in mg/L.
    Args:
        target_chlorine_mgL (float): target chlorine concentration in mg/L  
        chlorine_to_ammonia_ratio (float): chlorine to ammonia mass ratio
    """
    if chlorine_to_ammonia_ratio <= 0:
        raise ValueError(
            "Chlorine to ammonia ratio must be greater than zero."
        )
    return target_chlorine_mgL / chlorine_to_ammonia_ratio


def calculate_footprint_area_strainer_screens__m2(
        flow_m3hr: float,
        screen_velocity_mpersec: float,
        area_factor: float = 1.1,
) -> float:
    # Original formula from Greg:
    # effective_area_m2 = (
    #     self.nominal_flow_m3perh * 0.000012) / self.screen_velocity_mpersec
    # TODO: check with Greg the 0.000012 and the 1.1 factor
    flow_m3persec = flow_m3hr / 3600
    effective_area_water_m2 = flow_m3persec / screen_velocity_mpersec
    return area_factor * effective_area_water_m2


def calculate_hydraulic_headloss_strainer_screens__bar(
        headloss_coefficient: float,
        screen_velocity_mpersec: float,
) -> float:
    # TODO: check with Greg the formula
    headloss_bar = headloss_coefficient * (
        screen_velocity_mpersec ** 2) / (2 * 9.81 * METER_PER_BAR)
    return headloss_bar

def calculate_membrane_vessel_area__m2(
        nominal_flow_m3perh: float,
        membrane_area_m2: float,
        membranes_per_vessel: int,
        membrane_flux: float,  
        vessel_footprint_m2: float) -> float:
    
    if membrane_flux <= 0:
        raise ValueError(f"membrane_flux must be > 0; got {membrane_flux}.")
    if membrane_area_m2 <= 0:
        raise ValueError(f"membrane_area_m2 must be > 0; got {membrane_area_m2}.")
    if membranes_per_vessel <= 0:
        raise ValueError(f"membranes_per_vessel must be > 0; got {membranes_per_vessel}.")
        
    number_of_membranes = math.ceil(
        (nominal_flow_m3perh * 1000) / (membrane_flux * membrane_area_m2)
    )
    number_of_vessels = math.ceil(number_of_membranes / membranes_per_vessel)
    area_per_unit_m2 = number_of_vessels * vessel_footprint_m2

    return area_per_unit_m2


def calculate_headloss_over_filtration_media(
    water_viscosity: float,
    water_density_kg_per_m3: float,
    porosity: float,
    grain_size: float,
    hydraulic_loading_rate_m3m2h: float,
    filter_bed_height_m: float
) -> float:
    """Calculates head loss over a filter bed during normal operation"""
    headloss_medium = (
        180 * water_viscosity / (9.81 * water_density_kg_per_m3)
    ) * (
        (1 - porosity) ** 2 / porosity ** 3
    ) * (
        (hydraulic_loading_rate_m3m2h / 3600) * filter_bed_height_m
    ) / (grain_size / 1000) ** 2
    return headloss_medium


def calculate_water_demand_m3hr_for_population(
    population_persons: int,
    avg_consumption_lppd: float,  # consumption as in liter per person per day
):
    """Calculates demand from population persons and (average/min/max) 
    consumption .

    Args:
        population_persons (int): number of persons
        consumption_lppd (float): consumption in liter per person per day

    Returns:
        float: water demand from population
    """
    return population_persons * lppd_to_m3phr(avg_consumption_lppd)


def calculate_hydraulic_headloss_rapid_sand_filters_m(
    water_density_kg_per_m3: float,
    water_viscosity: float,
    sand_porosity: float,
    sand_media_grain_size: float,
    anthracite_porosity: float,
    anthracite_media_grain_size: float,
    hydraulic_loading_rate_m3m2h: float,
    sand_bed_height_m: float,
    anthracite_bed_height_m: float,
    tank_height: float,
) -> float:
    headloss_anthr = 0
    headloss_sand = calculate_headloss_over_filtration_media(
        water_viscosity=water_viscosity,
        water_density_kg_per_m3=water_density_kg_per_m3,
        porosity=sand_porosity,
        grain_size=sand_media_grain_size,
        hydraulic_loading_rate_m3m2h=hydraulic_loading_rate_m3m2h,
        filter_bed_height_m=sand_bed_height_m)
    if anthracite_bed_height_m > 0:
        headloss_anthr = calculate_headloss_over_filtration_media(
            water_viscosity=water_viscosity,
            water_density_kg_per_m3=water_density_kg_per_m3,
            porosity=anthracite_porosity,
            grain_size=anthracite_media_grain_size,
            hydraulic_loading_rate_m3m2h=hydraulic_loading_rate_m3m2h,
            filter_bed_height_m=anthracite_bed_height_m)
    headloss_m = headloss_sand + headloss_anthr + tank_height
    return meters_of_water_to_bar(headloss_m)

def calculate_backwash_headloss_filter(
    density_filter_media_kg_per_m3: float,
    water_density_kg_per_m3: float,
    porosity: float,
    filter_bed_height_m: float,
) -> float:
    if density_filter_media_kg_per_m3 <= 0:
        return 0
    bw_headloss = (
        (density_filter_media_kg_per_m3 - water_density_kg_per_m3)
        / water_density_kg_per_m3
        * (1 - porosity * 1.1)
        * filter_bed_height_m
    )
    return bw_headloss


def calculate_backwash_headloss_m(
    water_density_kg_per_m3: float,
    sand_porosity: float | None,
    anthracite_porosity: float | None,
    sand_density_kg_per_m3: float | None,
    anthracite_density_kg_per_m3: float | None,
    sand_bed_height_m: float | None,
    anthracite_bed_height_m: float | None,
    tank_height: float,
) -> float:
    h_sand = calculate_backwash_headloss_filter(
        density_filter_media_kg_per_m3=sand_density_kg_per_m3,
        water_density_kg_per_m3=water_density_kg_per_m3,
        porosity=sand_porosity,
        filter_bed_height_m=sand_bed_height_m
    )
    h_anthracite = calculate_backwash_headloss_filter(
        density_filter_media_kg_per_m3=anthracite_density_kg_per_m3, # noqa: E501
        water_density_kg_per_m3=water_density_kg_per_m3,
        porosity=anthracite_porosity,
        filter_bed_height_m=anthracite_bed_height_m
    )
    return 1.1 * (
        h_sand + h_anthracite + tank_height)  # 10% safety factor.


def pressurisedvesselcalc_m_m2(
    flow_per_unit_m3hr: float,
) -> tuple[int | None, int | None]:
    V = flow_per_unit_m3hr/3600
    heights = np.array([
        1.22, 1.22, 1.22, 1.5, 1.5, 1.5, 1.5, 1.8, 2.0, 2.0, 2.0, 2.5
    ])
    diameters_mm = np.array([
        500, 600, 800, 900, 1000, 1200, 1400, 1600, 1800, 2500, 2800, 3200
    ])
    filtration_flows = np.array([
        (0.001, 3), (3, 5), (5, 8), (8, 10), (10, 12), (12, 17), (17, 24),
        (24, 30), (30, 47), (47, 68), (68, 92), (92, 120)
    ])
    lower_bounds = filtration_flows[:, 0]
    upper_bounds = filtration_flows[:, 1]
    mask = (lower_bounds < V) & (upper_bounds >= V)
    if not np.any(mask):
        print("No suitable vessel found for the given flow rate.")
        return None, None
    idx = np.argmax(mask)  # first match
    H = heights[idx]
    D = diameters_mm[idx]
    Dm = D / 1000  # diameter in meters
    unit_depth_m = int(np.ceil(1.1 * H))
    unit_area_m2 = int(np.ceil(np.pi * (Dm ** 2) / 4))
    return unit_depth_m, unit_area_m2


def movingbedvesselcalc_m_m2(
    flow_per_unit_m3hr: float,
) -> tuple[int | None, int | None, int | None]:
    V = flow_per_unit_m3hr
    heights = np.array([3.9, 4.7, 5.20, 5.7, 5.55, 6.05, 6.55, 5.5, 6.0])
    diameters_m = np.array([1.4, 2.0, 2.0, 2.0, 2.5, 2.5, 2.5, 2.8, 2.8])
    filtration_flows = np.array([
        (0.001, 6), (6, 14.8), (14.8, 16.4), (16.4, 17.9), (17.9, 27.3),
        (27.3, 29.7), (29.7, 32.2), (32.2, 33.9), (33.9, 37)
    ])
    installed_powers = np.array([3.0, 5.5, 5.5, 5.5, 9.2, 9.2, 9.2, 11, 11])
    lower_bounds = filtration_flows[:, 0]
    upper_bounds = filtration_flows[:, 1]
    mask = (lower_bounds < V) & (upper_bounds >= V)
    if not np.any(mask):
        print("No suitable vessel found for the given flow rate.")
        return None, None, None
    idx = np.argmax(mask)  # first match
    H = heights[idx]
    D = diameters_m[idx]
    power_of_unit = installed_powers[idx]
    unit_depth_m = int(np.ceil(1.1 * H))
    unit_area_m2 = int(np.ceil(np.pi * (D ** 2) / 4))
    unit_kwatt = int(np.ceil(power_of_unit))
    return unit_depth_m, unit_area_m2, unit_kwatt


def inlinepipesize(
    flow_per_unit_m3hr: float,
) -> tuple[float | None, float | None, int | None]:
    V = flow_per_unit_m3hr * 0.1 # assuming around 6 minutes retention time
    motorpower_kw = np.array([
        0.35, 0.55, 0.75, 1, 1.5, 2.25, 2.25, 2.25, 3.7, 7.5, 15, 22
    ])
    length_m = np.array([
        0.3, 0.35, 0.4, 0.5, 0.6, 0.65, 0.7, 0.8, 0.85, 0.9, 1.2, 1.25
    ])
    diameters_mm = np.array([
        110, 170, 220, 270, 360, 410, 460, 510, 510, 610, 710, 910
    ])
    volume_range_m3 = np.array([
            (0.001, 0.03), (0.03, 0.08), (0.08, 0.15), (0.15, 0.29),
            (0.29, 0.61), (0.61, 0.86), (0.86, 1.16), (1.16, 1.63),
            (1.63, 1.74), (1.74, 2.63), (2.63, 4.75), (4.75, 8.13)
    ])
    lower_bounds = volume_range_m3[:, 0]
    upper_bounds = volume_range_m3[:, 1]
    mask = (lower_bounds < V) & (upper_bounds >= V)
    if not np.any(mask):
        print("No suitable vessel found for the given flow rate.")
        return None, None, None
    idx = np.argmax(mask)  # first match
    L = length_m[idx]
    D = diameters_mm[idx]
    Dm = D / 1000  # diameter in meters
    unit_length_m = int(np.ceil(1.1 * Dm))
    unit_area_m2 = int(D*L)
    powermixing_kw = motorpower_kw[idx]
    return unit_area_m2, powermixing_kw, unit_length_m


def reactor_dimensions(
    flow_per_unit_m3hr: float,
    upflow_velocity_target_mphr: float,
    h_static_m: float,
    porosity_static: float,
    porosity_expanded: float
) -> tuple[float, float, float]:
    # TODO/fix missing args (h_static_m, eps_...)
    """Calculates diameter and height based on fluidization physics."""
    area_req = flow_per_unit_m3hr / upflow_velocity_target_mphr
    diameter = np.sqrt((4 * area_req) / np.pi)
        
    # Richardson-Zaki approach for bed expansion
    h_expanded = h_static_m * ((1 - porosity_static) / (1 - porosity_expanded))
    total_height = h_expanded * 1.5  # 50% freeboard
    return diameter, total_height, area_req


def daily_mass_balance__kg(
    nominal_flow_m3perh: float,
    delta_c: float,
    chemical_mass_fraction: float,
) -> tuple[float, float, float, float]:
    """Calculates chemicals in and pellets out per day."""

    hardness_removed_kg = (delta_c * nominal_flow_m3perh * 24) / 1000.0
    lime_req_kgperday = hardness_removed_kg * chemical_mass_fraction
    seed_req_kg = hardness_removed_kg * 0.10  # 10% seed ratio
    pellets_out_kg = hardness_removed_kg + seed_req_kg    
    return hardness_removed_kg, lime_req_kgperday, seed_req_kg, pellets_out_kg


class CoagulationDynamicMixing(TreatmentKPI):
    """KPI calculations for a Coagulation with Dynamic Mixing treatment unit."""
    tank_height: float
    chem_tank_height: float
    lanes: int
    nominal_flow_m3perh: float
    units_per_lane: int
    conc_chem_mgL: float
    solution_wwperc: float
    density_chemical_kgm3: float
    retention_time_min: float
    storage_time_days: float
    efficiency_mixer: float
    mixer_velocity_grad: float
    water_viscosity: float
    flow_per_lane: float
    unit_volume_m3: float
    unit_area_m2: float
    tanks_area_m2: float
    volume_chemical_day: float
    chemicals_area_m2: float
    chemical_emission_factor: float
    emission_factor_electricity: float
    dosing_flow_rate_liter: float
    doc_in_mgl: float
    tss_in_mgl: float
    pH_in: float
    temp: float
    
    def __post_init__(self):
        super().__post_init__()
        parameters = self.parameters
        design_parameters = self.design_parameters
        plant_kpis = self.plant_kpis
        wq_parameters = self.wq_parameters

        self.tank_height = parameters[TPN['tank_height']]
        self.chem_tank_height = parameters[TPN['tank_height_chemical_storage']]
        self.lanes = design_parameters.get('number of lanes', None)
        self.nominal_flow_m3perh = plant_kpis.get(
            NOMINAL_FLOW_RATE_NAME, None)  # noqa: E501
        self.units_per_lane = parameters[TPN['units_per_lane']]
        self.chemical_emission_factor = parameters[TPN['chemical_emission_factor']]
        self.emission_factor_electricity = design_parameters.get(
            EMISSION_FACTOR_ELEC_NAME, None)
        self.conc_chem_mgL = parameters[
            TPN['target_concentration_of_dosing_chemical']]
        self.solution_wwperc = parameters[
            TPN['chemical_dosing_solution_concentration_w_per_wpercent']]
        self.density_chemical_kgm3 = parameters[
            TPN['mass_density_of_chemical']] * 1000  # g/cm3 to kg/m3
        self.retention_time_min = parameters[
            TPN['retention_time_min']]
        self.storage_time_days = parameters[
            TPN['storage_time_of_chemicals_days']]
        self.efficiency_mixer = parameters[TPN['power_efficiency_of_mixers']]/100   # noqa: E501
        self.mixer_velocity_grad = parameters[TPN['mixer_velocity_gradient']]
        self.tss_in_mgl = wq_parameters[
            'total suspended solids'][INPUT_WQPARAMETER_KEY]
        self.tss_out_mgl = wq_parameters[
            'total suspended solids'][TARGET_WQPARAMETER_KEY]  
        self.doc_in_mgl = wq_parameters[
            'dissolved organic carbon'][INPUT_WQPARAMETER_KEY]  
        self.doc_out_mgl = wq_parameters[
            'dissolved organic carbon'][TARGET_WQPARAMETER_KEY]  
        self.pH_in = wq_parameters[
            'pH'][INPUT_WQPARAMETER_KEY]  # mgl/l
        self.temp = wq_parameters[
            'temperature'][INPUT_WQPARAMETER_KEY] 
        self.elec_cond = wq_parameters[
            'electrical conductivity'][INPUT_WQPARAMETER_KEY]  # mgl/l
        self.water_viscosity = design_parameters.get(
            'dynamic viscosity', WATER_VISCOSITY_N_S_PER_M2)
        self.flow_per_lane = calculate_flow_per_lane(
            self.lanes, self.nominal_flow_m3perh)
        self.unit_volume_m3 = calculate_unit_volume_m3(
            flow_per_lane_m3h=self.flow_per_lane,
            units_per_lane=self.units_per_lane,
            retention_time_min=self.retention_time_min)
        self.unit_area_m2 = calculate_unit_area_tank(
            unit_volume_m3=self.unit_volume_m3,
            unit_height_m=self.tank_height)
        self.tanks_area_m2 = (
            self.unit_area_m2 * self.units_per_lane * self.lanes)
        self.volume_chemical_day = calculate_dosing_volume__m3perday_perunit(
            concentration_mgL=self.conc_chem_mgL,
            flow_per_lane_m3hr=self.flow_per_lane,
            units_per_lane=self.units_per_lane,
            solution_concentration_w_w_percent=self.solution_wwperc,
        ) * self.lanes * self.units_per_lane  # m3/day
        self.chemicals_area_m2 = calculate_chemical_storage_area__m2(
            daily_volume_m3perday=self.volume_chemical_day,
            storage_time_days=self.storage_time_days,
            tank_height_m=self.chem_tank_height,
        )
        for tech_property in self.digest_parameter_list:
            if tech_property == 'nominal dosing flow rate':
                self.dosing_flow_rate_liter = 1000 * self.volume_chemical_day / 24
                self.parameters[tech_property] = self.dosing_flow_rate_liter 

        for tech_property in self.digest_parameter_list:
            if tech_property == 'volume':
                self.volume_m3 = self.tanks_area_m2 * self.tank_height
                self.parameters[tech_property] = self.volume_m3  # overwrite area

    def __repr__(self):
        return f"CoagulationDynamicMixing(tank height (m)={self.tank_height}, " \
                f"retention time (min)={self.retention_time_min}, " \
                f"nominal flow (m3/hr)={self.nominal_flow_m3perh})"

    def get_kpi(self, kpi: str) -> float:
        """Get the value for a KPI"""
        function_name = TECH_KPI_MAPPINGS.get(kpi, None)
        if function_name is not None:
            return getattr(self, function_name)
        else:
            raise ValueError(
                f"KPI '{kpi}' not implemented for {self.__class__.__name__}.")

    def get_kpi_dict(self, kpi_list=None):
        if kpi_list:
            return {kpi: self.get_kpi(kpi=kpi) for kpi in kpi_list}
        return {kpi: self.get_kpi(kpi=kpi) for kpi in TECH_KPI_MAPPINGS.keys()}

    @property
    def footprint_area__m2(self) -> float:
        return np.ceil(self.tanks_area_m2 + self.chemicals_area_m2)

    @property
    def footprint_area_for_chemicals__m2(self) -> float:
        masses = self.daily_mass_of_chemicals__kg
        if not masses:
            return 0.0
        concentrations = self._resolve_per_chemical_factors(
            factor=self.solution_wwperc,
            default_value=self.solution_wwperc,
        )
        areas = {}
        for chem_name, mass_kg_per_day in masses.items():
            concentration = concentrations.get(chem_name, self.solution_wwperc)
            if concentration <= 0:
                continue
            volume_chemical_day = mass_kg_per_day / (
                (concentration / 100) * DENS_WATER_KG_PER_M3
            )
            areas[chem_name] = calculate_chemical_storage_area__m2(
                daily_volume_m3perday=volume_chemical_day,
                storage_time_days=self.storage_time_days,
                tank_height_m=self.chem_tank_height,
            )
        return self.sum_per_chemical(areas)

    @property
    def daily_mass_of_chemicals__kg(self) -> dict[str, float]:
        dosing_per_lane = calculate_dosing_mass__perday_perunit(
            concentration_mgL=self.conc_chem_mgL,  # noqa: E501
            flow_per_lane_m3hr=self.flow_per_lane,
            units_per_lane=self.units_per_lane,
        )
        return self._single_chemical_value(dosing_per_lane * self.lanes * self.units_per_lane)

    @property
    def chemical_solution_concentration__mg_per_l(self) -> float:
        return self.conc_chem_mgL

    @property
    def hydraulic_headloss__bar(self) -> float:
        total_headloss = (0.001 * self.tanks_area_m2) + self.tank_height
        return meters_of_water_to_bar(total_headloss)

    @property
    def power__kw(self) -> float:
        seconds_per_day = 86400
        dosing_head_m = self.chem_tank_height + 2.0
        flow_chemical_m3_s = self.volume_chemical_day / seconds_per_day
        power_kw_unit = (
            (
                (1/self.efficiency_mixer) * self.mixer_velocity_grad**2
             ) * WATER_VISCOSITY_N_S_PER_M2 * self.unit_volume_m3) / 1000

        power_pump_kw = (
            self.density_chemical_kgm3 * GRAVITY_M_PER_S2 *
            flow_chemical_m3_s * dosing_head_m) / (
                self.efficiency_mixer * 1000)
        return (
            power_kw_unit * self.units_per_lane * self.lanes
            ) + power_pump_kw

    @property
    def co2_emissions__kg_co2_eq_per_m3(self) -> float:
        if self.emission_factor_electricity is None:
            raise ValueError("Emission factor for electricity is not set.")
        co2_emissions = (
            self.daily_energy_consumption__kwh *
            self.emission_factor_electricity)
        masses = self.daily_mass_of_chemicals__kg
        emission_factors = self._resolve_per_chemical_factors(
            factor=self.chemical_emission_factor,
            default_value=float(self.chemical_emission_factor),
        )
        chemical_co2_emissions = sum(
            masses.get(chem_name, 0.0) * emission_factors.get(chem_name, 0.0)
            for chem_name in masses
        )
        return (co2_emissions + chemical_co2_emissions
                ) / self.nominal_flow_m3perh / 24


class CoagulationInlineMixing(TreatmentKPI):
    """KPI calculations for a Coagulation with Inline Mixing treatment unit."""
    tank_height: float
    chem_tank_height: float
    lanes: int
    nominal_flow_m3perh: float
    units_per_lane: int
    conc_chem_mgL: float
    solution_wwperc: float
    density_chemical_kgm3: float
    retention_time_min: float
    storage_time_days: float
    efficiency_mixer: float
    mixer_velocity_grad: float
    water_viscosity: float
    flow_per_lane: float
    unit_volume_m3: float
    unit_area_m2: float
    tanks_area_m2: float
    volume_chemical_day: float
    chemicals_area_m2: float
    chemical_emission_factor: float
    emission_factor_electricity: float

    def __post_init__(self):
        super().__post_init__()
        parameters = self.parameters
        design_parameters = self.design_parameters
        plant_kpis = self.plant_kpis

        self.chem_tank_height = parameters[TPN['tank_height_chemical_storage']]
        self.lanes = design_parameters.get('number of lanes', None)
        self.nominal_flow_m3perh = plant_kpis.get(
            NOMINAL_FLOW_RATE_NAME, None)  # noqa: E501
        self.units_per_lane = parameters[TPN['units_per_lane']]
        self.chemical_emission_factor = parameters[TPN['chemical_emission_factor']]
        self.emission_factor_electricity = design_parameters.get(
            EMISSION_FACTOR_ELEC_NAME, None)
        self.conc_chem_mgL = parameters[
            TPN['target_concentration_of_dosing_chemical']]
        self.solution_wwperc = parameters[
            TPN['chemical_dosing_solution_concentration_w_per_wpercent']]
        self.density_chemical_kgm3 = parameters[
            TPN['mass_density_of_chemical']] * 1000  # g/cm3 to kg/m3
        self.storage_time_days = parameters[
            TPN['storage_time_of_chemicals_days']]
        self.flow_per_lane_m3perh = calculate_flow_per_lane(
            self.lanes, self.nominal_flow_m3perh)
        self.flow_per_unit_m3hr = self.flow_per_lane_m3perh / self.units_per_lane
        (self.unit_area_m2,self.power_kw_unit,self.unit_length) = inlinepipesize(
                flow_per_unit_m3hr=self.flow_per_unit_m3hr) 
        self.tanks_area_m2 = (
            self.unit_area_m2 * self.units_per_lane * self.lanes)
        self.volume_chemical_day = calculate_dosing_volume__m3perday_perunit(
            concentration_mgL=self.conc_chem_mgL,
            flow_per_lane_m3hr=self.flow_per_lane_m3perh,
            units_per_lane=self.units_per_lane,
            solution_concentration_w_w_percent=self.solution_wwperc,
        ) * self.lanes * self.units_per_lane
        self.chemicals_area_m2 = calculate_chemical_storage_area__m2(
            daily_volume_m3perday=self.volume_chemical_day,
            storage_time_days=self.storage_time_days,
            tank_height_m=self.chem_tank_height,
        )
        for tech_property in self.digest_parameter_list:
            if tech_property == 'nominal dosing flow rate':
                self.dosing_flow_rate_liter = 1000 * self.volume_chemical_day / 24
                self.parameters[tech_property] = self.dosing_flow_rate_liter 

    def __repr__(self):
        return f"nominal flow (m3/hr)={self.nominal_flow_m3perh})"

    def get_kpi(self, kpi: str) -> float:
        """Get the value for a KPI"""
        function_name = TECH_KPI_MAPPINGS.get(kpi, None)
        if function_name is not None:
            return getattr(self, function_name)
        else:
            raise ValueError(
                f"KPI '{kpi}' not implemented for {self.__class__.__name__}.")

    def get_kpi_dict(self, kpi_list=None):
        if kpi_list:
            return {kpi: self.get_kpi(kpi=kpi) for kpi in kpi_list}
        return {kpi: self.get_kpi(kpi=kpi) for kpi in TECH_KPI_MAPPINGS.keys()}

    @property
    def footprint_area__m2(self) -> float:
        return np.ceil(self.tanks_area_m2 + self.chemicals_area_m2)

    @property
    def footprint_area_for_chemicals__m2(self) -> float:
        masses = self.daily_mass_of_chemicals__kg
        if not masses:
            return 0.0
        concentrations = self._resolve_per_chemical_factors(
            factor=self.solution_wwperc,
            default_value=self.solution_wwperc,
        )
        areas = {}
        for chem_name, mass_kg_per_day in masses.items():
            concentration = concentrations.get(chem_name, self.solution_wwperc)
            if concentration <= 0:
                continue
            volume_chemical_day = mass_kg_per_day / (
                (concentration / 100) * DENS_WATER_KG_PER_M3
            )
            areas[chem_name] = calculate_chemical_storage_area__m2(
                daily_volume_m3perday=volume_chemical_day,
                storage_time_days=self.storage_time_days,
                tank_height_m=self.chem_tank_height,
            )
        return self.sum_per_chemical(areas)

    @property
    def daily_mass_of_chemicals__kg(self) -> dict[str, float]:
        dosing_per_lane = calculate_dosing_mass__perday_perunit(
            concentration_mgL=self.conc_chem_mgL,  # noqa: E501
            flow_per_lane_m3hr=self.flow_per_lane_m3perh,
            units_per_lane=1,
        )
        return self._single_chemical_value(
             dosing_per_lane  * self.lanes)

    @property
    def chemical_solution_concentration__mg_per_l(self) -> float:
        return self.conc_chem_mgL

    @property
    def hydraulic_headloss__bar(self) -> float:
        total_headloss = (0.001 * self.unit_length) + self.unit_length
        return meters_of_water_to_bar(total_headloss) 

    @property
    def power__kw(self) -> float:
        seconds_per_day = 60 * 60 * 24
        power_pump_kw = (
            self.density_chemical_kgm3 * GRAVITY_M_PER_S2 *
            self.volume_chemical_day * 5) / (
                seconds_per_day * 0.8) / 1000
        return self.power_kw_unit * self.units_per_lane * self.lanes + power_pump_kw

    @property
    def co2_emissions__kg_co2_eq_per_m3(self) -> float:
        if self.emission_factor_electricity is None:
            raise ValueError("Emission factor for electricity is not set.")
        co2_emissions = (
            self.daily_energy_consumption__kwh *
            self.emission_factor_electricity)
        masses = self.daily_mass_of_chemicals__kg
        emission_factors = self._resolve_per_chemical_factors(
            factor=self.chemical_emission_factor,
            default_value=float(self.chemical_emission_factor),
        )
        chemical_co2_emissions = sum(
            masses.get(chem_name, 0.0) * emission_factors.get(chem_name, 0.0)
            for chem_name in masses
        )
        return (co2_emissions + chemical_co2_emissions
                ) / self.nominal_flow_m3perh / 24


class CascadeMixerCoagulationDosing(TreatmentKPI):
    """KPI calculations for a Cascade treatment unit."""
    weir_height: float
    tank_height: float
    units_per_lane: int
    weir_coefficient: float
    headloss_coefficient: float
    chem_dosing_solution_concentration_w_w: float
    power_for_dosing_kw: float
    target_chemical_concentration_mgL: float
    power_efficiency_mixer: float
    emission_factor_electricity: float
    chemical_emission_factor: float
    chemical_tank_height: float
    volume_chemicals_m3:float

    def __post_init__(self):
        super().__post_init__()
        parameters = self.parameters
        design_parameters = self.design_parameters
        plant_kpis = self.plant_kpis

        self.lanes = design_parameters.get('number of lanes', None)
        self.nominal_flow_m3perh = plant_kpis.get(
            NOMINAL_FLOW_RATE_NAME, None)  # noqa: E501
        self.units_per_lane = parameters[TPN['units_per_lane']]
        self.emission_factor_electricity = design_parameters.get(
            EMISSION_FACTOR_ELEC_NAME, None)
        self.chemical_emission_factor = parameters[
            TPN['chemical_emission_factor']]
        self.weir_height = parameters[TPN['weir_height']]
        self.tank_height = parameters[TPN['tank_height']]
        self.weir_coefficient = parameters[TPN['weir_coefficient']]
        self.headloss_coefficient = parameters[TPN['head_loss_coefficient']]
        self.chem_dosing_solution_concentration_w_w = (
            parameters[
                TPN['chemical_dosing_solution_concentration_w_per_wpercent']
                ])
        self.target_chemical_concentration_mgL = (
            parameters[TPN['target_concentration_of_dosing_chemical']])
        self.power_efficiency_mixer = parameters[TPN['power_efficiency_of_mixers']] / 100  # noqa
        self.water_viscosity = design_parameters.get(
            'dynamic viscosity', WATER_VISCOSITY_N_S_PER_M2)
        self.nominal_flow_m3perh = plant_kpis.get(
            NOMINAL_FLOW_RATE_NAME, None)
        self.flow_per_lane_m3perh = calculate_flow_per_lane(
            self.lanes, self.nominal_flow_m3perh)
        self.retention_time_min = parameters[
            TPN['retention_time_min']]
        self.number_of_cascade_stages = parameters[
            TPN['number_of_cascade_stages']]
        self.storage_time_days = parameters[
            TPN['storage_time_of_chemicals_days']]
        self.chemical_tank_height = parameters[
            TPN['tank_height_chemical_storage']]
        self.unit_volume_m3 = calculate_unit_volume_m3(
            flow_per_lane_m3h=self.flow_per_lane_m3perh,
            units_per_lane=self.units_per_lane,
            retention_time_min=self.retention_time_min)
        self.casc_lane_width_m = np.sqrt(self.unit_volume_m3 / (
            self.tank_height) / 3)  # assuming 1/3 of area per lane
        self.volume_chemicals_m3 = calculate_dosing_volume__m3perday_perunit(  # noqa: E501
            concentration_mgL=self.target_chemical_concentration_mgL,
            flow_per_lane_m3hr=self.flow_per_lane_m3perh,
            units_per_lane=self.units_per_lane,
            solution_concentration_w_w_percent=(
                self.chem_dosing_solution_concentration_w_w),
        ) * self.lanes *self.units_per_lane # m3/day
        for tech_property in self.digest_parameter_list:
            if tech_property == 'nominal dosing flow rate':
                self.dosing_flow_rate_liter = 1000 * self.volume_chemicals_m3 / 24
                self.parameters[tech_property] = self.dosing_flow_rate_liter 

    def __repr__(self):
        return f"CascadeMixerCoagulationDosing(tank height (m)={self.chemical_tank_height}, " \
                f"retention time (min)={self.retention_time_min}, " \
                f"nominal flow (m3/hr)={self.nominal_flow_m3perh})"

    def get_kpi(self, kpi: str) -> float:
        """Get the value for a KPI"""
        function_name = TECH_KPI_MAPPINGS.get(kpi, None)
        if function_name is not None:
            return getattr(self, function_name)
        else:
            raise ValueError(
                f"KPI '{kpi}' not implemented for {self.__class__.__name__}.")

    def get_kpi_dict(self, kpi_list=None):
        if kpi_list:
            return {kpi: self.get_kpi(kpi=kpi) for kpi in kpi_list}
        return {kpi: self.get_kpi(kpi=kpi) for kpi in TECH_KPI_MAPPINGS.keys()}

    @property
    def footprint_area__m2(self) -> float:
        cascade_area_m2 = (self.unit_volume_m3 / self.tank_height
                           ) * self.lanes * self.units_per_lane
        chemicals_area_m2 = self.footprint_area_for_chemicals__m2
        return np.ceil(cascade_area_m2 + chemicals_area_m2)

    @property
    def footprint_area_for_chemicals__m2(self) -> float:
        chemicals_area_m2 = calculate_chemical_storage_area__m2(
            daily_volume_m3perday=self.volume_chemicals_m3,
            storage_time_days=self.storage_time_days,
            tank_height_m=self.chemical_tank_height,
        )
        return chemicals_area_m2


    @property
    def daily_mass_of_chemicals__kg(self) -> dict[str, float]:
        dosing_per_lane = calculate_dosing_mass__perday_perunit(
            concentration_mgL=self.target_chemical_concentration_mgL,  # noqa: E501
            flow_per_lane_m3hr=self.flow_per_lane_m3perh,
            units_per_lane=self.units_per_lane,
        )
        return self._single_chemical_value(dosing_per_lane * self.lanes * self.units_per_lane)
    
    @property
    def chemical_solution_concentration__mg_per_l(self) -> float:
        return self.target_chemical_concentration_mgL  

    @property
    def hydraulic_headloss__bar(self) -> float:
        # TODO: verify formula with Greg
        flow_per_cascade_stage_m3persec = self.flow_per_lane_m3perh / 3600
        cascade_flowing_area_m2 = (self.casc_lane_width_m * self.weir_height)
        headloss_weir = self.headloss_coefficient * (
            (flow_per_cascade_stage_m3persec / cascade_flowing_area_m2) ** 2
            ) / (2 * GRAVITY_M_PER_S2)
        headloss_cascade = headloss_weir * self.number_of_cascade_stages
        total_headloss = self.tank_height + headloss_cascade
        return meters_of_water_to_bar(total_headloss)

    @property
    def power__kw(self) -> float:
        headloss_m = bar_to_meters_of_water(self.hydraulic_headloss__bar)
        flow_m3_per_s = (self.flow_per_lane_m3perh / 3600) * self.lanes
        power_watts = (
            DENS_WATER_KG_PER_M3 * GRAVITY_M_PER_S2 * headloss_m *
            flow_m3_per_s)
        power_kw = power_watts / 1000  # Convert watts to kW

        density_chemical_kgm3 = 2.49 * 1000
        seconds_per_day = 24 * 3600
        dosing_head_m = self.chemical_tank_height + 2.0
        flow_chemical_m3_s = self.volume_chemicals_m3 / seconds_per_day
        power_pump_kw = (
            density_chemical_kgm3 * GRAVITY_M_PER_S2 *
            flow_chemical_m3_s * dosing_head_m) / (
                self.power_efficiency_mixer * 1000)
        return power_kw + power_pump_kw


    @property
    def co2_emissions__kg_co2_eq_per_m3(self) -> float:
        if self.emission_factor_electricity is None:
            raise ValueError("Emission factor for electricity is not set.")
        co2_emissions = (
            self.daily_energy_consumption__kwh *
            self.emission_factor_electricity)
        masses = self.daily_mass_of_chemicals__kg
        emission_factors = self._resolve_per_chemical_factors(
            factor=self.chemical_emission_factor,
            default_value=float(self.chemical_emission_factor),
        )
        chemical_co2_emissions = sum(
            masses.get(chem_name, 0.0) * emission_factors.get(chem_name, 0.0)
            for chem_name in masses
        )
        return (co2_emissions + chemical_co2_emissions
                ) / self.nominal_flow_m3perh / 24


class FlocculationDynamicMixing(TreatmentKPI):
    """KPI calculations for a Flocculation with Dynamic Mixing treatment unit."""
    tank_height: float
    lanes: int
    nominal_flow_m3perh: float
    retention_time_min: float
    storage_time_days: float
    efficiency_mixer: float
    mixer_velocity_grad: float
    flow_per_unit_m3hr: float
    water_viscosity: float
    flow_per_lane: float
    unit_volume_m3: float
    unit_area_m2: float
    tanks_area_m2: float   
    emission_factor_electricity: float
    volume_m3: float
    floc_length: float

    def __post_init__(self):
        super().__post_init__()
        parameters = self.parameters
        design_parameters = self.design_parameters
        plant_kpis = self.plant_kpis

        self.lanes = design_parameters.get('number of lanes', None)
        self.nominal_flow_m3perh = plant_kpis.get(
            NOMINAL_FLOW_RATE_NAME, None)  # noqa: E501
        self.units_per_lane = parameters[TPN['units_per_lane']]
        self.emission_factor_electricity = design_parameters.get(
            EMISSION_FACTOR_ELEC_NAME, None)
        self.tank_height = parameters[TPN['tank_height']]
        self.retention_time_min = parameters[
            TPN['retention_time_min']]
        self.efficiency_mixer = parameters[TPN['power_efficiency_of_mixers']] / 100  # noqa: E501
        self.mixer_velocity_grad = parameters[TPN['mixer_velocity_gradient']]
        self.water_viscosity = design_parameters.get(
            'dynamic viscosity', WATER_VISCOSITY_N_S_PER_M2)
        self.flow_per_lane = calculate_flow_per_lane(
            self.lanes, self.nominal_flow_m3perh)
        self.flow_per_unit_m3hr = self.flow_per_lane / self.units_per_lane
        self.unit_volume_m3 = calculate_unit_volume_m3(
            flow_per_lane_m3h=self.flow_per_lane,
            units_per_lane=self.units_per_lane,
            retention_time_min=self.retention_time_min)
        self.unit_area_m2 = calculate_unit_area_tank(
            unit_volume_m3=self.unit_volume_m3,
            unit_height_m=self.tank_height)
        self.tanks_area_m2 = self.unit_area_m2 * self.units_per_lane * self.lanes
        for tech_property in self.digest_parameter_list:
            if tech_property == 'unit length':
                 self.floc_length = np.ceil (3 * np.sqrt(self.unit_area_m2 / 3)) # flocculation length
                 self.parameters[tech_property] = self.floc_length  
        for tech_property in self.digest_parameter_list:
            if tech_property == 'volume':
                 self.volume_m3 = self.tanks_area_m2 * self.tank_height
                 self.parameters[tech_property] = self.volume_m3 

    def __repr__(self):
        return f"FlocculationDynamicMixing(tank height (m)={self.tank_height}, " \
                f"retention time (min)={self.retention_time_min}, " \
                f"nominal flow (m3/hr)={self.nominal_flow_m3perh})"

    def get_kpi(self, kpi: str) -> float:
        """Get the value for a KPI"""
        function_name = TECH_KPI_MAPPINGS.get(kpi, None)
        if function_name is not None:
            return getattr(self, function_name)
        else:
            raise ValueError(
                f"KPI '{kpi}' not implemented for {self.__class__.__name__}.")

    def get_kpi_dict(self, kpi_list=None):
        if kpi_list:
            return {kpi: self.get_kpi(kpi=kpi) for kpi in kpi_list}
        return {kpi: self.get_kpi(kpi=kpi) for kpi in TECH_KPI_MAPPINGS.keys()}

    @property
    def footprint_area__m2(self) -> float:
        return np.ceil(1.1 * self.tanks_area_m2)

    @property
    def footprint_area_for_chemicals__m2(self) -> float:
        return 0

    @property
    def daily_mass_of_chemicals__kg(self) -> dict[str, float]:
        return {}

    @property
    def chemical_costs__eur_per_day(self) -> float:
        return 0

    @property
    def chemical_solution_concentration__mg_per_l(self) -> float:
        return 0

    @property
    def hydraulic_headloss__bar(self) -> float:
        return meters_of_water_to_bar(0.001 * self.floc_length + self.tank_height)

    @property
    def power__kw(self) -> float:
        power_kw_unit = (
            (
                (1/self.efficiency_mixer) * self.mixer_velocity_grad**2
             ) * self.water_viscosity * self.unit_volume_m3) / 1000
        return power_kw_unit * self.units_per_lane * self.lanes

    @property
    def co2_emissions__kg_co2_eq_per_m3(self) -> float:
        if self.emission_factor_electricity is None:
            raise ValueError("Emission factor for electricity is not set.")
        co2_emissions = (
            self.daily_energy_consumption__kwh *
            self.emission_factor_electricity)
        specific_co2_emissions = co2_emissions / self.nominal_flow_m3perh / 24  # kg CO2 eq per m3
        return specific_co2_emissions

class MicroStrainer(TreatmentKPI):
    """KPI calculations for a strainer or microstrainer treatment unit."""
    open_area_factor: float
    nominal_flow_m3perh: float
    screen_velocity_mpersec: float
    lanes: int
    flow_per_lane_m3perh: float
    headloss_coefficient: float
    area: float  # equal to footprint area, used for cost calculations
    emission_factor_electricity: float

    def __post_init__(self):
        super().__post_init__()
        parameters = self.parameters
        design_parameters = self.design_parameters
        plant_kpis = self.plant_kpis

        self.lanes = design_parameters.get(NR_OF_LANES_NAME, None)
        self.emission_factor_electricity = design_parameters.get(
            EMISSION_FACTOR_ELEC_NAME, None)
        self.nominal_flow_m3perh = plant_kpis.get(
            NOMINAL_FLOW_RATE_NAME, None)
        self.screen_velocity_mpersec = parameters[TPN['velocity_bar_screen']]
        self.flow_per_lane_m3perh = calculate_flow_per_lane(
            self.lanes, self.nominal_flow_m3perh)
        self.headloss_coefficient = parameters[TPN['head_loss_coefficient']]
        self.open_area_factor = parameters[TPN['open_area_factor']]
        self.area = 0.0  # Initialize area, will be calculated later
        for tech_property in self.digest_parameter_list:
            if tech_property == 'area':
                self.area = self.footprint_area__m2
                self.parameters[tech_property] = self.area  # overwrite area

    def __repr__(self):
        return f"Micro strainer(nominal flow (m3/hr)={self.nominal_flow_m3perh})"

    def get_kpi(self, kpi: str) -> float:
        """Get the value for a KPI"""
        kpi_attr = TECH_KPI_MAPPINGS.get(kpi, None)
        if kpi_attr is not None:
            return getattr(self, kpi_attr)
        else:
            raise ValueError(
                f"KPI '{kpi}' not implemented for {self.__class__.__name__}.")

    def get_kpi_dict(self, kpi_list=None):
        if kpi_list:
            return {kpi: self.get_kpi(kpi=kpi) for kpi in kpi_list}
        return {kpi: self.get_kpi(kpi=kpi) for kpi in TECH_KPI_MAPPINGS.keys()}

    @property
    def footprint_area__m2(self) -> float:
        effective_area = calculate_footprint_area_strainer_screens__m2(
            flow_m3hr=self.nominal_flow_m3perh,
            screen_velocity_mpersec=self.screen_velocity_mpersec,
        )
        fp_area = effective_area / self.open_area_factor
        self.area = fp_area  # Store area for cost calculations
        return fp_area

    @property
    def footprint_area_for_chemicals__m2(self) -> float:
        return 0.0  # No chemicals used in Strainer

    @property
    def hydraulic_headloss__bar(self) -> float:
        return calculate_hydraulic_headloss_strainer_screens__bar(
            headloss_coefficient=self.headloss_coefficient,
            screen_velocity_mpersec=self.screen_velocity_mpersec)

    @property
    def power__kw(self) -> float:
        # TODO: check the formula with Greg
        headloss_m = bar_to_meters_of_water(self.hydraulic_headloss__bar)
        flow_per_lane_m3persec = self.flow_per_lane_m3perh / 3600
        power_watts = (
            DENS_WATER_KG_PER_M3 * GRAVITY_M_PER_S2 * headloss_m *
            flow_per_lane_m3persec * self.lanes)
        return power_watts / 1000  # Convert watts to kW


    @property
    def daily_mass_of_chemicals__kg(self) -> dict[str, float]:
        return {}  # No chemicals used in Micro strainer
    
    @property
    def chemical_solution_concentration__mg_per_l(self) -> float:
        return 0.0  # No chemicals used in Micro strainer

    @property
    def co2_emissions__kg_co2_eq_per_m3(self) -> float:
        if self.emission_factor_electricity is None:
            raise ValueError("Emission factor for electricity is not set.")
        co2_emissions = (
            self.daily_energy_consumption__kwh *
            self.emission_factor_electricity)
        specific_co2_emissions = co2_emissions / self.nominal_flow_m3perh / 24  # kg CO2 eq per m3
        return specific_co2_emissions


class Strainer(TreatmentKPI):
    """KPI calculations for a strainer or microstrainer treatment unit."""
    bar_spacing: float
    bar_width: float
    blockage_factor: float
    open_area_friction: float
    nominal_flow_m3perh: float
    screen_velocity_mpersec: float
    lanes: int
    flow_per_lane_m3perh: float
    headloss_coefficient: float
    emission_factor_electricity: float

    def __post_init__(self):
        super().__post_init__()
        parameters = self.parameters
        design_parameters = self.design_parameters
        plant_kpis = self.plant_kpis

        self.lanes = design_parameters.get(NR_OF_LANES_NAME, None)
        self.emission_factor_electricity = design_parameters.get(
            EMISSION_FACTOR_ELEC_NAME, None)
        self.bar_spacing = parameters[TPN['bar_spacing']]
        self.bar_width = parameters[TPN['bar_width']]
        self.blockage_factor = parameters[TPN['blockage_factor']]
        self.open_area_friction = (
            self.bar_spacing/(self.bar_spacing + self.bar_width)
                ) * (1 - self.blockage_factor)
        self.nominal_flow_m3perh = plant_kpis.get(
            NOMINAL_FLOW_RATE_NAME, None)
        self.screen_velocity_mpersec = parameters[TPN['velocity_bar_screen']]
        self.flow_per_lane_m3perh = calculate_flow_per_lane(
            self.lanes, self.nominal_flow_m3perh)
        self.headloss_coefficient = parameters[TPN['head_loss_coefficient']]
        self.area = 0.0  # Initialize area, will be calculated later
        for tech_property in self.digest_parameter_list:
            if tech_property == 'area':
                self.area = self.footprint_area__m2
                self.parameters[tech_property] = self.area  # overwrite area

    def __repr__(self):
        return f"Strainer(bar spacing (m)={self.bar_spacing}, " \
                f"bar width (m)={self.bar_width}, " \
                f"nominal flow (m3/hr)={self.nominal_flow_m3perh})"

    def get_kpi(self, kpi: str) -> float:
        """Get the value for a KPI"""
        function_name = TECH_KPI_MAPPINGS.get(kpi, None)
        if function_name is not None:
            return getattr(self, function_name)
        else:
            raise ValueError(
                f"KPI '{kpi}' not implemented for {self.__class__.__name__}.")

    def get_kpi_dict(self, kpi_list=None):
        if kpi_list:
            return {kpi: self.get_kpi(kpi=kpi) for kpi in kpi_list}
        return {kpi: self.get_kpi(kpi=kpi) for kpi in TECH_KPI_MAPPINGS.keys()}

    @property
    def footprint_area__m2(self) -> float:
        effective_area = calculate_footprint_area_strainer_screens__m2(
        flow_m3hr=self.nominal_flow_m3perh,
        screen_velocity_mpersec=self.screen_velocity_mpersec,
        )
        return effective_area / self.open_area_friction

    @property
    def footprint_area_for_chemicals__m2(self) -> float:
        return 0.0  # No chemicals used in Strainer

    @property
    def hydraulic_headloss__bar(self) -> float:
        return calculate_hydraulic_headloss_strainer_screens__bar(
            headloss_coefficient=self.headloss_coefficient,
            screen_velocity_mpersec=self.screen_velocity_mpersec)

    @property
    def power__kw(self) -> float:
        # TODO: check the formula with Greg
        headloss_m = bar_to_meters_of_water(self.hydraulic_headloss__bar)
        flow_per_lane_m3persec = self.flow_per_lane_m3perh / 3600
        power_watts = (
            DENS_WATER_KG_PER_M3 * GRAVITY_M_PER_S2 * headloss_m *
            flow_per_lane_m3persec * self.lanes)
        return power_watts / 1000  # Convert watts to kW

    @property
    def daily_mass_of_chemicals__kg(self) -> dict[str, float]:
        return {}  # No chemicals used in Strainer

    @property
    def chemical_solution_concentration__mg_per_l(self) -> float:
        return 0.0  # No chemicals used in Strainer

    @property
    def co2_emissions__kg_co2_eq_per_m3(self) -> float:
        if self.emission_factor_electricity is None:
            raise ValueError(
                f"Emission factor for electricity is not set for {self.__class__.__name__}.")
        co2_emissions = (
            self.daily_energy_consumption__kwh *
            self.emission_factor_electricity)
        specific_co2_emissions = co2_emissions / self.nominal_flow_m3perh / 24  # kg CO2 eq per m3
        return specific_co2_emissions


class ChainScrapedSedimentation(TreatmentKPI):
    """KPI calculations for a Chain Scraped Sedimentation treatment unit."""
    lanes: int
    units_per_lane: int
    nominal_flow_m3perh: float
    flow_m3persec: float
    flow_per_lane_m3perh: float
    retention_time_min: float
    scraper_power_coeff_kw_m2: float
    total_suspended_solids: float
    overflow_rate_m3_per_m2_per_h: float
    emission_factor_electricity: float
    area_m2: float

    def __post_init__(self):
        super().__post_init__()
        parameters = self.parameters
        design_parameters = self.design_parameters
        plant_kpis = self.plant_kpis
        wq_parameters = self.wq_parameters
        self.lanes = design_parameters.get(NR_OF_LANES_NAME, None)
        self.units_per_lane = parameters[TPN['units_per_lane']]
        self.emission_factor_electricity = design_parameters.get(EMISSION_FACTOR_ELEC_NAME, None)
        self.nominal_flow_m3perh = plant_kpis.get(
            NOMINAL_FLOW_RATE_NAME, None)
        self.flow_m3persec = self.nominal_flow_m3perh / 3600
        self.flow_per_lane_m3perh = calculate_flow_per_lane(
            self.lanes, self.nominal_flow_m3perh)
        self.retention_time_min = parameters[TPN['retention_time_min']]
        self.scraper_power_coeff_kw_m2 = parameters[
            TPN['scraper_power_coefficient']]
        self.total_suspended_solids = wq_parameters ['total suspended solids'][INPUT_WQPARAMETER_KEY]
        self.overflow_rate_m3_per_m2_per_h = parameters[
            TPN['surface_overflow_rate']]
        self.unit_area_m2 = (self.flow_per_lane_m3perh /self.units_per_lane /
                             self.overflow_rate_m3_per_m2_per_h)
        self.unit_volume_m3 = (
            self.nominal_flow_m3perh * self.retention_time_min / 60) / (
                self.lanes * self.units_per_lane)
        self.tank_height_m = self.unit_volume_m3 / self.unit_area_m2
        for tech_property in self.digest_parameter_list:
            if tech_property == 'area':
                self.area_m2 = self.footprint_area__m2
                self.parameters[tech_property] = self.area_m2  # overwrite area

    def __repr__(self):
        return f"ChainScrapedSedimentation (retention time (min)={self.retention_time_min}, " \
               f"nominal flow (m3/hr)={self.nominal_flow_m3perh})"

    def get_kpi(self, kpi: str) -> float:
        """Get the value for a KPI"""
        function_name = TECH_KPI_MAPPINGS.get(kpi, None)
        if function_name is not None:
            return getattr(self, function_name)
        else:
            raise ValueError(
                f"KPI '{kpi}' not implemented for {self.__class__.__name__}.")

    def get_kpi_dict(self, kpi_list=None):
        if kpi_list:
            return {kpi: self.get_kpi(kpi=kpi) for kpi in kpi_list}
        return {kpi: self.get_kpi(kpi=kpi) for kpi in TECH_KPI_MAPPINGS.keys()}

    @property
    def footprint_area__m2(self) -> float:
        return np.ceil(self.unit_area_m2 * self.units_per_lane * self.lanes)

    @property
    def footprint_area_for_chemicals__m2(self) -> float:
        return 0.0  # No chemicals used in Chain Scraped Sedimentation

    @property
    def daily_mass_of_chemicals__kg(self) -> dict[str, float]:
        return {}  # No chemicals used in Chain Scraped Sedimentation
    
    @property
    def chemical_solution_concentration__mg_per_l(self) -> float:
        return 0.0  # No chemicals used in Chain Scraped Sedimentation

    @property
    def hydraulic_headloss__bar(self) -> float:
        headloss_m_constant = 0.5  # constant headloss in meters
        number_of_units = self.units_per_lane * self.lanes
        headloss_m = headloss_m_constant + 0.05 * (
            self.flow_m3persec / number_of_units / self.unit_area_m2) ** 2 / (
                2 * GRAVITY_M_PER_S2
            )  # TODO: verify formula with Greg
        return meters_of_water_to_bar(headloss_m)

    @property
    def power__kw(self) -> float:
        number_of_units = self.units_per_lane * self.lanes
        scraper_power_per_unit_kw = (
            self.scraper_power_coeff_kw_m2 * self.unit_area_m2)
        total_power_kw = scraper_power_per_unit_kw * number_of_units
        return np.ceil(total_power_kw)


    @property
    def co2_emissions__kg_co2_eq_per_m3(self) -> float:
        if self.emission_factor_electricity is None:
            raise ValueError("Emission factor for electricity is not set.")
        co2_emissions = (
            self.daily_energy_consumption__kwh *
            self.emission_factor_electricity)
        specific_co2_emissions = co2_emissions / self.nominal_flow_m3perh / 24  # kg CO2 eq per m3
        return specific_co2_emissions


class ChlorineDisinfection(TreatmentKPI):
    """KPI calculations for a Chlorine Disinfection treatment unit."""
    tank_height_m: float
    chemicals_tank_height_m: float
    lanes: int
    units_per_lane: int
    nominal_flow_m3perh: float
    flow_per_lane_m3perh: float
    storage_time_days: float
    power_of_dosing_kw: float
    retention_time_min: float
    target_residual_chlorine_mgL: float
    chlorine_dosing_mgL: float
    chlorine_solution_w_w: float
    chlorine_concentration_mgL: float
    emission_factor_electricity: float
    chemical_emission_factor: float
    baffling_factor: float
    ecoli_initial: float
    tthms_initial: float
    haas_initial: float
    volume_m3: float

    def __post_init__(self):
        super().__post_init__()
        parameters = self.parameters
        design_parameters = self.design_parameters
        plant_kpis = self.plant_kpis
        wq_parameters = self.wq_parameters

        self.units_per_lane = parameters[TPN['units_per_lane']]
        self.lanes = design_parameters.get(NR_OF_LANES_NAME, None)
        self.chemical_emission_factor = parameters[TPN['chemical_emission_factor']]
        self.emission_factor_electricity = design_parameters.get(
            EMISSION_FACTOR_ELEC_NAME, None)
        self.tank_height_m = parameters[
            TPN['tank_height']]
        self.chemicals_tank_height_m = parameters[
            TPN['tank_height_chemical_storage']]
        self.storage_time_days = parameters[
            TPN['storage_time_of_chemicals_days']]
        self.nominal_flow_m3perh = plant_kpis.get(
            NOMINAL_FLOW_RATE_NAME, None)
        self.flow_per_lane_m3perh = calculate_flow_per_lane(
            self.lanes, self.nominal_flow_m3perh)
        self.retention_time_min = parameters[
            TPN['retention_time_min']]
        self.target_residual_chlorine_mgL = parameters[
            TPN['target_residual_concentration_mg_per_l']]  # noqa: E501
        self.chlorine_dosing_mgL = parameters[
            TPN['target_concentration_of_dosing_chemical']]  # noqa: E501
        self.chlorine_solution_w_w = parameters[
            TPN['chemical_dosing_solution_concentration_w_per_wpercent']]  # noqa: E501
        self.ecoli_initial = wq_parameters['E. coli'][
            INPUT_WQPARAMETER_KEY]
        self.tthms_initial = wq_parameters['trihalomethanes'][
            INPUT_WQPARAMETER_KEY]
        self.haas_initial = wq_parameters['haloacetic acids'][
            INPUT_WQPARAMETER_KEY]
        self.tthms_final = wq_parameters['trihalomethanes'][
            TARGET_WQPARAMETER_KEY]
        self.haas_final = wq_parameters['haloacetic acids'][
            TARGET_WQPARAMETER_KEY]
        self.baffling_factor = parameters[
            TPN['baffling_factor']]  # noqa: E501
        self.chlorine_concentration_mgL = calculate_chlorine_concentration_mgL(  # noqa: E501
            residual_chlorine_mgL=self.target_residual_chlorine_mgL,
            dosing_solution_concentration_w_w=self.chlorine_solution_w_w
        )
        self.unit_volume_m3 = calculate_unit_volume_m3(
            flow_per_lane_m3h=self.flow_per_lane_m3perh,
            units_per_lane=self.units_per_lane,
            retention_time_min=self.retention_time_min)
        for tech_property in self.digest_parameter_list:
            if tech_property == 'volume':
                self.volume_m3 = self.unit_volume_m3 * self.units_per_lane * self.lanes
                self.parameters[tech_property] = self.volume_m3  # overwrite area

    def __repr__(self):
        return f"ChlorineDisinfection(tank height (m)={self.tank_height_m}, " \
                f"chemical tank height (m)={self.chemicals_tank_height_m}, " \
                f"retention time (min)={self.retention_time_min}, " \
                f"nominal flow (m3/hr)={self.nominal_flow_m3perh})"

    def get_kpi(self, kpi: str) -> float:
        """Get the value for a KPI"""
        function_name = TECH_KPI_MAPPINGS.get(kpi, None)
        if function_name is not None:
            return getattr(self, function_name)
        else:
            raise ValueError(
                f"KPI '{kpi}' not implemented for {self.__class__.__name__}.")

    def get_kpi_dict(self, kpi_list=None):
        if kpi_list:
            return {kpi: self.get_kpi(kpi=kpi) for kpi in kpi_list}
        return {kpi: self.get_kpi(kpi=kpi) for kpi in TECH_KPI_MAPPINGS.keys()}

    @property
    def footprint_area__m2(self) -> float:
        unit_area_m2 = calculate_unit_area_tank(
            unit_volume_m3=self.unit_volume_m3,
            unit_height_m=self.tank_height_m)
        chemicals_area_m2 = self.footprint_area_for_chemicals__m2
        return np.ceil(unit_area_m2 * self.lanes * self.units_per_lane + chemicals_area_m2)

    @property
    def footprint_area_for_chemicals__m2(self) -> float:
        masses = self.daily_mass_of_chemicals__kg
        if not masses:
            return 0.0
        concentrations = self._resolve_per_chemical_factors(
            factor=self.chlorine_solution_w_w,
            default_value=self.chlorine_solution_w_w,
        )
        areas = {}
        for chem_name, mass_kg_per_day in masses.items():
            concentration = concentrations.get(chem_name, self.chlorine_solution_w_w)
            if concentration <= 0:
                continue
            volume_chemical_day_m3 = mass_kg_per_day / ((concentration / 100) * 1000)
            areas[chem_name] = (
                volume_chemical_day_m3 * self.storage_time_days
            ) / self.chemicals_tank_height_m
        return self.sum_per_chemical(areas)

    @property
    def daily_mass_of_chemicals__kg(self) -> dict[str, float]:
        dosing_per_lane = calculate_dosing_mass__perday_perunit(
            concentration_mgL=self.chlorine_concentration_mgL,
            flow_per_lane_m3hr=self.flow_per_lane_m3perh,
            units_per_lane=1,
        )
        return self._single_chemical_value(dosing_per_lane * self.lanes)

    @property
    def chemical_solution_concentration__mg_per_l(self) -> float:
        return self.chlorine_concentration_mgL

    @property
    def hydraulic_headloss__bar(self) -> float:
        return 0.2  # Assumed constant headloss for chlorine disinfection

    @property
    def power__kw(self) -> float:
        dosing_per_lane = calculate_dosing_mass__perday_perunit(
            concentration_mgL=self.chlorine_concentration_mgL,
            flow_per_lane_m3hr=self.flow_per_lane_m3perh,
            units_per_lane=1,
        )
        volume_chlorine_m3day = dosing_per_lane * self.lanes
        chlorine_dosing_flow_m3s = volume_chlorine_m3day / (24 * 3600)
        power_chlorine_kw = (
            chlorine_dosing_flow_m3s * 9.81 * 1190* (self.chemicals_tank_height_m +1)) / (0.7 * 1000)
        return  power_chlorine_kw

    @property
    def co2_emissions__kg_co2_eq_per_m3(self) -> float:
        if self.emission_factor_electricity is None:
            raise ValueError("Emission factor for electricity is not set.")
        co2_emissions = (
            self.daily_energy_consumption__kwh *
            self.emission_factor_electricity)
        masses = self.daily_mass_of_chemicals__kg
        emission_factors = self._resolve_per_chemical_factors(
            factor=self.chemical_emission_factor,
            default_value=float(self.chemical_emission_factor),
        )
        chemical_co2_emissions = sum(
            masses.get(chem_name, 0.0) * emission_factors.get(chem_name, 0.0)
            for chem_name in masses
        )
        return (co2_emissions + chemical_co2_emissions
                ) / self.nominal_flow_m3perh / 24


class ChloramineDisinfection(TreatmentKPI):
    """KPI calculations for a Chloramine Disinfection treatment unit."""
    tank_height_m: float
    chemicals_tank_height_m: float
    lanes: int
    units_per_lane: int
    nominal_flow_m3perh: float
    flow_per_lane_m3perh: float
    storage_time_days: float
    power_of_dosing_kw: float
    retention_time_min: float
    target_residual_chlorine_mgL: float
    chlorine_dosing_mgL: float
    chlorine_solution_w_w: float
    chlorine_concentration_mgL: float
    chlorine_disinfection: ChlorineDisinfection
    ammonia_dosing_mgperltr: float
    ammonia_concentration_mgperltr: float
    chemical_emission_factor: float
    emission_factor_electricity: float
    volume_m3: float

    def __post_init__(self):
        super().__post_init__()
        parameters = self.parameters
        design_parameters = self.design_parameters
        plant_kpis = self.plant_kpis
        wq_parameters = self.wq_parameters

        self.chlorine_disinfection = ChlorineDisinfection(
            parameters=parameters,
            design_parameters=design_parameters,
            plant_kpis=plant_kpis,
            wq_parameters=wq_parameters,
            chem_parameters=self.chem_parameters,
            digest_parameter_list=self.digest_parameter_list,
        )
        self.chlorine_to_ammonia_ratio = 5.0
        self.ammonia_concentration_mgL = calculate_ammonia_concentration_mgL(
            target_chlorine_mgL=self.chlorine_disinfection.chlorine_dosing_mgL,
            chlorine_to_ammonia_ratio=self.chlorine_to_ammonia_ratio,
        )
        self.chemical_emission_factor = parameters[
            TPN['chemical_emission_factor']]
        self.emission_factor_electricity = design_parameters.get(
            EMISSION_FACTOR_ELEC_NAME, None)        
        self.lanes = design_parameters.get('number of lanes', None)
        self.nominal_flow_m3perh = plant_kpis.get(NOMINAL_FLOW_RATE_NAME, None)
        self.flow_per_lane_m3perh = calculate_flow_per_lane(
            self.lanes, self.nominal_flow_m3perh)
        self.retention_time_min = parameters[TPN['retention_time_min']]
        self.units_per_lane = parameters[TPN['units_per_lane']]
        self.number_of_units = self.units_per_lane * self.lanes
        self.storage_time_days = parameters[
            TPN['storage_time_of_chemicals_days']]
        self.tank_height_m = parameters[TPN['tank_height']]
        self.chemicals_tank_height_m = parameters[
            TPN['tank_height_chemical_storage']
        ]
        chlorine_mass = self.sum_per_chemical(
            self.chlorine_disinfection.daily_mass_of_chemicals__kg
        )
        ammonia_mass = calculate_dosing_mass__perday_perunit(
            concentration_mgL=self.ammonia_concentration_mgL,
            flow_per_lane_m3hr=self.flow_per_lane_m3perh,
            units_per_lane=self.units_per_lane,
        ) * self.units_per_lane * self.lanes
        self.volume_chlorine_m3day = chlorine_mass / (1000 * 1.19)
        self.volume_ammonia_m3day = ammonia_mass / (1000 * 0.68)
        self.unit_volume_m3 = calculate_unit_volume_m3(
            flow_per_lane_m3h=self.flow_per_lane_m3perh,
            units_per_lane=self.units_per_lane,
            retention_time_min=self.retention_time_min)
        for tech_property in self.digest_parameter_list:
            if tech_property == 'volume':
                self.volume_m3 = self.unit_volume_m3 * self.units_per_lane * self.lanes
                self.parameters[tech_property] = self.volume_m3 
    
    def __repr__(self):
        return f"ChloramineDisinfection(tank height (m)={self.tank_height_m}, " \
                f"chemical tank height (m)={self.chemicals_tank_height_m}, " \
                f"retention time (min)={self.retention_time_min}, " \
                f"nominal flow (m3/hr)={self.nominal_flow_m3perh})"

    def get_kpi(self, kpi: str) -> float:
        """Get the value for a KPI"""
        function_name = TECH_KPI_MAPPINGS.get(kpi, None)
        if function_name is not None:
            return getattr(self, function_name)
        else:
            raise ValueError(
                f"KPI '{kpi}' not implemented for {self.__class__.__name__}.")

    def get_kpi_dict(self, kpi_list=None):
        if kpi_list:
            return {kpi: self.get_kpi(kpi=kpi) for kpi in kpi_list}
        return {kpi: self.get_kpi(kpi=kpi) for kpi in TECH_KPI_MAPPINGS.keys()}

    @property
    def footprint_area__m2(self) -> float:
        unit_volume_m3 = calculate_unit_volume_m3(
            flow_per_lane_m3h=self.flow_per_lane_m3perh,
            units_per_lane=self.units_per_lane,
            retention_time_min=self.retention_time_min)
        unit_area_m2 = calculate_unit_area_tank(
            unit_volume_m3=self.unit_volume_m3,
            unit_height_m=self.tank_height_m)
        chemicals_area_m2 = self.footprint_area_for_chemicals__m2
        return np.ceil(unit_area_m2 * self.number_of_units + chemicals_area_m2)

    @property
    def footprint_area_for_chemicals__m2(self) -> float:
        volume_chemicals_m3day = (
            self.volume_chlorine_m3day + self.volume_ammonia_m3day)
        chemicals_area = (
            volume_chemicals_m3day * self.storage_time_days
            ) / self.chemicals_tank_height_m

        return chemicals_area
    
    @property
    def daily_mass_of_chemicals__kg(self) -> dict[str, float]:
        mass_chlorine_kgday = self.sum_per_chemical(
            self.chlorine_disinfection.daily_mass_of_chemicals__kg
        )
        mass_ammonia_kgday = calculate_dosing_mass__perday_perunit(
            concentration_mgL=self.ammonia_concentration_mgL,
            flow_per_lane_m3hr=self.flow_per_lane_m3perh,
            units_per_lane=self.units_per_lane,
        )* self.units_per_lane * self.lanes
        return self._single_chemical_value(mass_chlorine_kgday + mass_ammonia_kgday)

    @property
    def chemical_solution_concentration__mg_per_l(self) -> float:
        return self.ammonia_concentration_mgL

    @property
    def hydraulic_headloss__bar(self) -> float:
        return self.chlorine_disinfection.hydraulic_headloss__bar

    @property
    def power__kw(self) -> float:
        # TODO: verify formulas with Greg: 1190 kg/m3 for chlorine, 680 kg/m3 for ammonia?
        chlorine_dosing_flow_m3s = self.volume_chlorine_m3day / (24 * 3600)
        ammonia_dosing_flow_m3s = self.volume_ammonia_m3day / (24 * 3600)
        power_chlorine_kw = (
            chlorine_dosing_flow_m3s * 9.81 * 1190 * (self.chemicals_tank_height_m +1)) / (0.7 * 1000)
        power_ammonia_kw = (
            ammonia_dosing_flow_m3s * 9.81 * 680 * (self.chemicals_tank_height_m +1)) / (0.7 * 1000)  # storage at -33 Â°C, efficiency 70%?
        return power_chlorine_kw + power_ammonia_kw

    @property
    def co2_emissions__kg_co2_eq_per_m3(self) -> float:
        if self.emission_factor_electricity is None:
            raise ValueError("Emission factor for electricity is not set.")
        co2_emissions = (
            self.daily_energy_consumption__kwh *
            self.emission_factor_electricity)
        masses = self.daily_mass_of_chemicals__kg
        emission_factors = self._resolve_per_chemical_factors(
            factor=self.chemical_emission_factor,
            default_value=float(self.chemical_emission_factor),
        )
        chemical_co2_emissions = sum(
            masses.get(chem_name, 0.0) * emission_factors.get(chem_name, 0.0)
            for chem_name in masses
        )
        return (co2_emissions + chemical_co2_emissions
                ) / self.nominal_flow_m3perh / 24


class MembraneFiltration(TreatmentKPI):
    """KPI calculations for a Membrane Filtration treatment unit."""
    units_per_lane: float
    lanes: int
    units_per_lane: int
    flow_per_lane_m3perh: float
    flow_per_unit_m3perh: float
    nominal_flow_m3perh: float
    recovery_rate: float
    power_efficiency_pump: float
    operating_pressure_bar: float
    membrane_flux: float
    membrane_area_m2: float
    membranes_per_vessel:float
    vessel_footprint_m2: float
    area_per_unit_m2: float
    area_m2: float
    emission_factor_electricity: float

    def __post_init__(self):
        super().__post_init__()
        parameters = self.parameters
        design_parameters = self.design_parameters
        plant_kpis = self.plant_kpis
        # wq_parameters = self.wq_parameters

        self.lanes = design_parameters.get('number of lanes', None)
        self.units_per_lane = parameters[TPN['units_per_lane']]
        if self.units_per_lane <= 1:
            raise ValueError(
                "units_per_lane must be > 1 to reserve a unit for backwash; "
                f"got {self.units_per_lane}."
            )
        self.number_of_units = self.units_per_lane * self.lanes
        self.nominal_flow_m3perh = plant_kpis.get(
            NOMINAL_FLOW_RATE_NAME, None)
        self.flow_per_lane_m3perh = calculate_flow_per_lane(
            self.lanes, self.nominal_flow_m3perh)
        self.flow_per_unit_m3perh = (
            self.flow_per_lane_m3perh / (self.units_per_lane - 1)) 
        self.recovery_rate = parameters[TPN['membrane_recovery_rate']] / 100
        self.power_efficiency_pump = parameters[
            TPN['power_efficiency_of_pumps']] / 100  # noqa: E501
        self.operating_pressure_bar = parameters[TPN['pressure_head']] 
        self.membrane_flux = parameters[TPN['membrane_flux']]
        self.membrane_area_m2 = parameters[TPN['operating_membrane_area']]                       
        self.membranes_per_vessel = parameters[TPN['membranes_per_vessel']]
        self.vessel_footprint_m2 = parameters[TPN['vessel_footprint']]
        self.area_per_unit_m2 = calculate_membrane_vessel_area__m2(
             nominal_flow_m3perh = self.flow_per_unit_m3perh,
             membrane_area_m2=self.membrane_area_m2,
             membranes_per_vessel = self.membranes_per_vessel,
             membrane_flux = self.membrane_flux,
             vessel_footprint_m2=self.vessel_footprint_m2
            )
        for tech_property in self.digest_parameter_list:
            if tech_property == 'membrane area':
                self.area_m2 = self.area_per_unit_m2 * self.units_per_lane * self.lanes
                self.parameters[tech_property] = self.area_m2 

    def __repr__(self):
        return f"MembraneFiltration(nominal flow (m3/hr)={self.nominal_flow_m3perh}, " \
               f"operating pressure (bar)={self.operating_pressure_bar}, " \
               f"recovery rate (%)={self.recovery_rate * 100})"
                
    def get_kpi(self, kpi: str) -> float:
        """Get the value for a KPI"""
        function_name = TECH_KPI_MAPPINGS.get(kpi, None)
        if function_name is not None:
            return getattr(self, function_name)
        else:
            raise ValueError(
                f"KPI '{kpi}' not implemented for {self.__class__.__name__}.")

    def get_kpi_dict(self, kpi_list=None):
        if kpi_list:
            return {kpi: self.get_kpi(kpi=kpi) for kpi in kpi_list}
        return {kpi: self.get_kpi(kpi=kpi) for kpi in TECH_KPI_MAPPINGS.keys()}

    @property
    def footprint_area__m2(self) -> float:
        # including 20% extra space for piping and access
        return np.ceil(1.2 * self.area_per_unit_m2 * self.number_of_units)

    @property
    def footprint_area_for_chemicals__m2(self) -> float:
        return 0.0  # No chemicals used in Membrane Filtration

    @property
    def daily_mass_of_chemicals__kg(self) -> dict[str, float]:
        return {}  # No chemicals used in Membrane Filtration

    @property
    def chemical_solution_concentration__mg_per_l(self) -> float:
        return 0.0  # No chemicals used in Membrane Filtration

    @property
    def hydraulic_headloss__bar(self) -> float:
        return self.operating_pressure_bar + 0.5  # including fouling headloss

    @property
    def power__kw(self) -> float:
        flow_m3_per_s = self.nominal_flow_m3perh / 3600
        head_m = bar_to_meters_of_water(self.hydraulic_headloss__bar)
        power_watts = (
            DENS_WATER_KG_PER_M3 * GRAVITY_M_PER_S2 * head_m * flow_m3_per_s
        )
        return power_watts / (1000 * self.power_efficiency_pump)  # to kW


    @property
    def co2_emissions__kg_co2_eq_per_m3(self) -> float:
        if self.emission_factor_electricity is None:
            raise ValueError("Emission factor for electricity is not set.")
        co2_emissions = (
            self.daily_energy_consumption__kwh *
            self.emission_factor_electricity)
        specific_co2_emissions = co2_emissions / self.nominal_flow_m3perh / 24  # kg CO2 eq per m3
        return specific_co2_emissions


class IntakePump(TreatmentKPI):
    """KPI calculations for an Intake Pump."""
    pipe_length_m: float
    pipe_roughness: float
    lanes: int
    units_per_lane: int
    nominal_flow_m3perh: float
    flow_per_lane_m3perh: float
    motor_efficiency: float
    pipe_roughness: float
    retention_time_min: float
    power_efficiency: float
    emission_factor_electricity: float

    def __post_init__(self):
        super().__post_init__()
        parameters = self.parameters
        design_parameters = self.design_parameters
        plant_kpis = self.plant_kpis
        # wq_parameters = self.wq_parameters
        
        self.lanes = design_parameters.get('number of lanes', None)
        self.nominal_flow_m3perh = plant_kpis.get(
            NOMINAL_FLOW_RATE_NAME, None)
        self.units_per_lane = parameters[TPN['units_per_lane']]
        self.pipe_diameter_m = parameters[TPN['pipe_diameter_m']]
        self.pipe_length_m = parameters[TPN['pipe_length_m']]
        self.pipe_roughness = parameters[TPN['pipe_roughness']]
        self.power_efficiency = parameters[TPN['power_efficiency']] / 100
        self.motor_efficiency = parameters[TPN['motor_efficiency']] / 100
        self.level_difference_m = parameters[TPN['level_difference_m']]
        self.emission_factor_electricity = design_parameters.get(
            EMISSION_FACTOR_ELEC_NAME, None)

    def __repr__(self):
        return f"IntakePump(lanes={self.lanes}, nominal flow (m3/hr)={self.nominal_flow_m3perh}, " \
            f"pipe diameter (m)={self.pipe_diameter_m}, pipe length (m)={self.pipe_length_m}, "\
            f"pipe roughness={self.pipe_roughness}, " \
            f"level difference (m)={self.level_difference_m})"

    def get_kpi(self, kpi: str) -> float:
        """Get the value for a KPI"""
        function_name = TECH_KPI_MAPPINGS.get(kpi, None)
        if function_name is not None:
            return getattr(self, function_name)
        else:
            raise ValueError(
                f"KPI '{kpi}' not implemented for {self.__class__.__name__}.")

    def get_kpi_dict(self, kpi_list=None):
        if kpi_list:
            return {kpi: self.get_kpi(kpi=kpi) for kpi in kpi_list}        
        return {kpi: self.get_kpi(kpi=kpi) for kpi in TECH_KPI_MAPPINGS.keys()}

    @property
    def footprint_area__m2(self) -> float:
        # TODO: add formula with Greg
        return 5.0  # Assumed constant footprint area for intake pump

    @property
    def footprint_area_for_chemicals__m2(self) -> float:
        return 0.0  # No chemicals used in Intake Pump

    @property
    def daily_mass_of_chemicals__kg(self) -> dict[str, float]:
        return 0.0  # No chemicals used in Intake Pump

    @property
    def chemical_solution_concentration__mg_per_l(self) -> float:
        return 0.0  # No chemicals used in Intake Pump

    @property
    def hydraulic_headloss__bar(self) -> float:
        # Calculate headloss due to friction in the pipe
        # TODO: verify formula with Greg.
        reynolds_number = reynolds_number_pipe(
            flow_m3perh=self.nominal_flow_m3perh,
            pipe_diameter_m=self.pipe_diameter_m,
        )
        friction_factor = friction_factor_pipe(
            reynolds_number_pipe=reynolds_number,
            pipe_roughness=self.pipe_roughness,
            pipe_diameter_m=self.pipe_diameter_m,
        )
        headloss_bar = calculate_pressure_drop_pipe(
            flow_m3perh=self.nominal_flow_m3perh,
            pipe_diameter_m=self.pipe_diameter_m,
            pipe_length_m=self.pipe_length_m,
            friction_factor=friction_factor,
        )
        headloss_bar += meters_of_water_to_bar(self.level_difference_m)
        return 1.15 * headloss_bar  # 15% safety factor??

    @property
    def power__kw(self) -> float:
        flow_m3_per_s = self.nominal_flow_m3perh / 3600
        total_dynamic_head_m = bar_to_meters_of_water(
            self.hydraulic_headloss__bar)
        # In Greg's notes, there is an additional factor of  0.000012?
        power_watts = (
            DENS_WATER_KG_PER_M3 * GRAVITY_M_PER_S2 *
            total_dynamic_head_m * flow_m3_per_s
        )
        total_efficiency = self.power_efficiency * self.motor_efficiency
        return power_watts / (1000 * total_efficiency)  # to kW


    @property
    def co2_emissions__kg_co2_eq_per_m3(self) -> float:
        if self.emission_factor_electricity is None:
            raise ValueError("Emission factor for electricity is not set.")
        co2_emissions = (
            self.daily_energy_consumption__kwh *
            self.emission_factor_electricity)
        specific_co2_emissions = co2_emissions / self.nominal_flow_m3perh / 24  # kg CO2 eq per m3
        return specific_co2_emissions


class CleanWaterStorageTank(TreatmentKPI):
    """KPI calculations for a Clean Water Storage Tank treatment unit."""
    lanes: int
    tank_height_m: float
    retention_time_hrs: float
    units_per_lane: int
    number_of_units: int
    nominal_flow_m3perh: float
    unit_volume_m3: float
    unit_area_m2: float
    emission_factor_electricity: float

    def __post_init__(self):
        super().__post_init__()
        parameters = self.parameters
        design_parameters = self.design_parameters
        plant_kpis = self.plant_kpis
        # wq_parameters = self.wq_parameters

        self.nominal_flow_m3perh = plant_kpis.get(
            NOMINAL_FLOW_RATE_NAME, None)
        self.lanes = design_parameters.get('number of lanes', None)
        self.tank_height_m = parameters[TPN['tank_height']]
        self.retention_time_hrs = parameters[TPN['retention_time_hr']]
        self.units_per_lane = parameters[TPN['units_per_lane']]
        self.emission_factor_electricity = design_parameters.get(
            EMISSION_FACTOR_ELEC_NAME, None)
        self.number_of_units = self.units_per_lane * self.lanes
        self.unit_volume_m3 = (
            self.retention_time_hrs * self.nominal_flow_m3perh) / (
            self.number_of_units)
        self.unit_area_m2 = calculate_unit_area_tank(
            unit_volume_m3=self.unit_volume_m3,
            unit_height_m=self.tank_height_m)
        for tech_property in self.digest_parameter_list:
            if tech_property == 'volume':
                self.volume_m3 = self.unit_volume_m3 * self.units_per_lane * self.lanes
                self.parameters[tech_property] = self.volume_m3 

    def __repr__(self):
        return f"CleanWaterStorageTank(tank height (m)={self.tank_height_m}, " \
               f"retention time (hrs)={self.retention_time_hrs}, " \
                f"nominal flow (m3/hr)={self.nominal_flow_m3perh})"
        
    def get_kpi(self, kpi: str) -> float:
        """Get the value for a KPI"""
        function_name = TECH_KPI_MAPPINGS.get(kpi, None)
        if function_name is not None:
            return getattr(self, function_name)
        else:
            raise ValueError(
                f"KPI '{kpi}' not implemented for {self.__class__.__name__}.")

    def get_kpi_dict(self, kpi_list=None):
        if kpi_list:
            return {kpi: self.get_kpi(kpi=kpi) for kpi in kpi_list}
        return {kpi: self.get_kpi(kpi=kpi) for kpi in TECH_KPI_MAPPINGS.keys()}

    @property
    def footprint_area__m2(self) -> float:
        return np.ceil(self.unit_area_m2 * self.units_per_lane * self.lanes)

    @property
    def footprint_area_for_chemicals__m2(self) -> float:
        return 0.0  # No chemicals used in Clean Water Storage Tank

    @property
    def daily_mass_of_chemicals__kg(self) -> dict[str, float]:
        return {}  # No chemicals used in Clean Water Storage Tank

    @property
    def chemical_solution_concentration__mg_per_l(self) -> float:
        return 0.0  # No chemicals used in Clean Water Storage Tank

    @property
    def hydraulic_headloss__bar(self) -> float:
        return 0.1  # TODO: modify with Greg

    @property
    def power__kw(self) -> float:
        return 0.0  # No power used in Clean Water Storage Tank

    @property
    def daily_energy_consumption__kwh(self) -> float:
        return 0.0  # No power used in Clean Water Storage Tank

    @property
    def co2_emissions__kg_co2_eq_per_m3(self) -> float:
        if self.emission_factor_electricity is None:
            raise ValueError("Emission factor for electricity is not set.")
        co2_emissions = (
            self.daily_energy_consumption__kwh *
            self.emission_factor_electricity)
        specific_co2_emissions = co2_emissions / self.nominal_flow_m3perh / 24  # kg CO2 eq per m3
        return specific_co2_emissions


class RapidSandSingleMediumFiltration(TreatmentKPI):
    """KPI calculations for a Rapid Sand Filtration treatment unit."""
    tank_height: float
    lanes: int
    nominal_flow_m3perh: float
    units_per_lane: int
    sand_porosity: float
    sand_density_kg_per_m3: float
    antracite_porosity: float
    antracite_density_kg_per_m3: float
    sand_bed_height_m: float
    antracite_bed_height_m: float
    filter_bed_height_m: float
    sand_media_grain_size: float
    antracite_media_grain_size: float
    hydraulic_loading_rate_m3m2h: float
    backwash_hydraulic_loading_rate_m3m2h: float
    backwash_duration_min: int
    backwash_tank_height_m: float
    backwash_flow_rate_m3_per_m2_per_h: float
    efficiency_backwash_pumps: float
    water_density_kg_per_m3: float
    water_viscosity: float
    nominal_flow_m3perh: float
    flow_per_lane_m3perh: float
    unit_volume_m3: float
    unit_area_m2: float
    unit_height_m: float
    tanks_area_m2: float
    filter_area_m2: float
    backwash_pump_flow_m3_per_h: float
    backwash_pump_head_m: float
    backwash_pump_area_m2: float
    backwash_water_area_m2: float
    backwash_area_m2: float
    backwash_pump_head_m: float
    emission_factor_electricity: float

    def __post_init__(self):
        super().__post_init__()
        parameters = self.parameters
        design_parameters = self.design_parameters
        plant_kpis = self.plant_kpis
        wq_parameters = self.wq_parameters

        self.nominal_flow_m3perh = plant_kpis.get(
            NOMINAL_FLOW_RATE_NAME, None)
        self.lanes = design_parameters.get('number of lanes', None)
        self.emission_factor_electricity = design_parameters.get(
            EMISSION_FACTOR_ELEC_NAME, None)
        self.flow_per_lane_m3perh = calculate_flow_per_lane(
            self.lanes, self.nominal_flow_m3perh)
        self.units_per_lane = parameters[TPN['units_per_lane']]
        self.hydraulic_loading_rate_m3m2h = parameters[
            TPN['filtration_rate']]
        self.sand_porosity = parameters[
            TPN['sand_porosity']]
        self.sand_density_kg_per_m3 = parameters[
            TPN['sand_density']] * 1000
        self.sand_media_grain_size = parameters[
            TPN['sand_media_grain_size']]
        self.backwash_duration_min = parameters[
            TPN['backwash_duration']]
        self.backwash_tank_height_m = parameters[
            TPN['backwash_tank_height']]
        self.backwash_hydraulic_loading_rate_m3m2h = parameters[
            TPN['backwash_filtration_rate']]
        self.efficiency_pumps = parameters[
            TPN['power_efficiency_of_pumps']] / 100  # to fraction
        self.unit_area_m2 = (
            self.flow_per_lane_m3perh /
            self.hydraulic_loading_rate_m3m2h
            ) / self.units_per_lane
        self.sand_bed_height_m = parameters[
            TPN['sand_filter_bed_height']]
        self.anthracite_bed_height_m = 0  # no anthracite media on single filtration - noqa: E501
        self.unit_height_m = (
            self.sand_bed_height_m + self.anthracite_bed_height_m + 1)
        self.unit_volume_m3 = self.unit_area_m2 * self.unit_height_m
        self.tss_in_mgl = wq_parameters[
            'total suspended solids'][INPUT_WQPARAMETER_KEY]  # 150 mgl/l
        self.tss_out_mgl = wq_parameters[
            'total suspended solids'][TARGET_WQPARAMETER_KEY]  # 50 mgl/l
        # pumping power required per lane, assuming pumping from the bottom of
        # the tank to the top of the tank (worst case scenario)
        #self.power_lane_kw = (
        #    DENS_WATER_KG_PER_M3 * GRAVITY_M_PER_S2 *
        #    self.flow_per_lane_m3perh * self.unit_height_m) / (
        #        self.efficiency_pumps * 3600 * 1000)
        self.water_viscosity = WATER_VISCOSITY_N_S_PER_M2  # TODO: hardcoded value, modify with Greg
        self.tanks_area_m2 = (
            self.unit_area_m2 * self.units_per_lane * self.lanes)
        self.backwash_pump_flow_m3_per_h = (
            np.ceil(
                self.unit_area_m2 * self.backwash_hydraulic_loading_rate_m3m2h))
        self.backwash_pump_head_m = np.ceil(
            calculate_backwash_headloss_m(
                water_density_kg_per_m3=DENS_WATER_KG_PER_M3,
                sand_porosity=self.sand_porosity,
                anthracite_porosity=None,
                sand_density_kg_per_m3=self.sand_density_kg_per_m3,
                anthracite_density_kg_per_m3=0,
                sand_bed_height_m=self.sand_bed_height_m,
                anthracite_bed_height_m=0,
                tank_height=self.unit_height_m))
        self.backwash_water_area_m2 = (
            self.backwash_pump_flow_m3_per_h * self.backwash_duration_min
            / (60 * self.backwash_tank_height_m))
        self.backwash_pump_area_m2 = (
            2 * (3 * self.backwash_pump_flow_m3_per_h / 3600))  # rule of thumb of Apump=3*Qpump (in m/s)
        self.backwash_area_m2 = (
            self.backwash_pump_area_m2 + self.backwash_water_area_m2)
        for tech_property in self.digest_parameter_list:
            if tech_property == 'filter area':
                self.filter_area_m2 = self.tanks_area_m2
                self.parameters[tech_property] = self.filter_area_m2  # overwrite filter area

    def __repr__(self):
        return f"Rapid Sand filtration, single medium"
            
    def get_kpi(self, kpi: str) -> float:
        """Get the value for a KPI"""
        function_name = TECH_KPI_MAPPINGS.get(kpi, None)
        if function_name is not None:
            return getattr(self, function_name)
        else:
            raise ValueError(
                f"KPI '{kpi}' not implemented for {self.__class__.__name__}.")

    def get_kpi_dict(self, kpi_list=None):
        if kpi_list:
            return {kpi: self.get_kpi(kpi=kpi) for kpi in kpi_list}
        return {kpi: self.get_kpi(kpi=kpi) for kpi in TECH_KPI_MAPPINGS.keys()}

    @property
    def footprint_area__m2(self) -> float:
        return np.ceil(self.tanks_area_m2 + self.backwash_area_m2)

    @property
    def footprint_area_for_chemicals__m2(self) -> float:
        return 0.0  # No chemicals used in Rapid Sand Filtration

    @property
    def daily_mass_of_chemicals__kg(self) -> dict[str, float]:
        return {}  # No chemicals used in Rapid Sand Filtration
    
    @property
    def chemical_solution_concentration__mg_per_l(self) -> float:
        return 0.0  # No chemicals used in Rapid Sand Filtration

    @property
    def hydraulic_headloss__bar(self) -> float:
        return calculate_hydraulic_headloss_rapid_sand_filters_m(
            water_density_kg_per_m3=DENS_WATER_KG_PER_M3,
            water_viscosity=self.water_viscosity,
            sand_porosity=self.sand_porosity,
            sand_media_grain_size=self.sand_media_grain_size,
            anthracite_porosity=self.sand_porosity,
            anthracite_media_grain_size=0,  # dummy number
            hydraulic_loading_rate_m3m2h=self.hydraulic_loading_rate_m3m2h,
            sand_bed_height_m=self.sand_bed_height_m,
            anthracite_bed_height_m=0,  # calculated as zero as anthracite depth = 0m
            tank_height=self.unit_height_m)
            
    @property
    def power__kw(self) -> float:
        backwash_power_watts = (
            DENS_WATER_KG_PER_M3 * GRAVITY_M_PER_S2 *
            self.backwash_pump_head_m * self.backwash_pump_flow_m3_per_h/3600
        )
        backwash_power_kw = backwash_power_watts / (self.efficiency_pumps * 1000)
        return backwash_power_kw
    
    @property
    def daily_energy_consumption__kwh(self) -> float:
        total_amount_units = self.units_per_lane * self.lanes
        # Assuming one full backwash (all units one time) per day 
        backwash_frequency = 1 / 7
        return self.power__kw * (
            self.backwash_duration_min / 60) * total_amount_units * backwash_frequency
    
    @property
    def co2_emissions__kg_co2_eq_per_m3(self) -> float:
        if self.emission_factor_electricity is None:
            raise ValueError("Emission factor for electricity is not set.")
        co2_emissions = (
            self.daily_energy_consumption__kwh *
            self.emission_factor_electricity)
        specific_co2_emissions = co2_emissions / self.nominal_flow_m3perh / 24  # kg CO2 eq per m3
        return specific_co2_emissions


class RapidSandDoubleMediumFiltration(TreatmentKPI):
    """KPI calculations for a Rapid Sand Filtration treatment unit."""
    tank_height: float
    lanes: int
    nominal_flow_m3perh: float
    units_per_lane: int
    sand_porosity: float
    sand_density_kg_per_m3: float
    antracite_porosity: float
    antracite_density_kg_per_m3: float
    sand_bed_height_m: float
    antracite_bed_depth_m: float        
    filter_bed_depth_m: float
    sand_media_grain_size: float
    antracite_media_grain_size: float
    hydraulic_loading_rate_m3m2h: int
    backwash_duration_min: int
    backwash_tank_height_m: float
    backwash_flow_rate_m3_per_m2_per_h: float
    efficiency_pump: float
    water_density_kg_per_m3: float
    water_viscosity: float
    flow_per_lane_m3perh: float
    unit_volume_m3: float
    unit_area_m2: float
    unit_height_m: float
    tanks_area_m2: float
    backwash_pump_flow_m3_per_h: float
    backwash_pump_head_m: float
    backwash_pump_area_m2: float
    backwash_water_area_m2: float
    backwash_area_m2: float
    backwash_pump_head_m: float
    emission_factor_electricity: float
    filter_area_m2: float

    def __post_init__(self):
        super().__post_init__()
        parameters = self.parameters
        design_parameters = self.design_parameters
        plant_kpis = self.plant_kpis
        wq_parameters = self.wq_parameters

        self.nominal_flow_m3perh = plant_kpis.get(
            NOMINAL_FLOW_RATE_NAME, None)  # noqa: E501
        self.lanes = design_parameters.get('number of lanes', None)
        self.emission_factor_electricity = design_parameters.get(
            EMISSION_FACTOR_ELEC_NAME, None)           
        self.flow_per_lane_m3perh = calculate_flow_per_lane(
            self.lanes, self.nominal_flow_m3perh)
        self.units_per_lane = parameters[TPN['units_per_lane']]
        self.hydraulic_loading_rate_m3m2h = parameters[
            TPN['filtration_rate']]
        self.sand_porosity = parameters[
            TPN['sand_porosity']]
        self.sand_density_kg_per_m3 = parameters[
            TPN['sand_density']] * 1000
        self.sand_media_grain_size = parameters[
            TPN['sand_media_grain_size']]
        self.anthracite_porosity = parameters[
            TPN['anthracite_porosity']] 
        self.anthracite_density_kg_per_m3 = parameters[
            TPN['anthracite_density']] * 1000
        self.anthracite_media_grain_size = parameters[
            TPN['anthracite_media_grain_size']]
        self.backwash_duration_min = parameters[
            TPN['backwash_duration']]
        self.backwash_tank_height_m = parameters[
            TPN['backwash_tank_height']] 
        self.backwash_hydraulic_loading_rate_m3m2h = parameters[
            TPN['backwash_filtration_rate']]
        self.efficiency_pumps = parameters[
            TPN['power_efficiency_of_pumps']] / 100  # to fraction
        self.unit_area_m2 = (
            self.flow_per_lane_m3perh /
            self.hydraulic_loading_rate_m3m2h)/ self.units_per_lane
        self.tanks_area_m2 = (
            self.unit_area_m2 * self.units_per_lane * self.lanes)
        self.sand_bed_height_m = parameters[
            TPN['sand_filter_bed_height']]
        self.anthracite_bed_height_m = parameters[
            TPN['anthracite_filter_bed_height']]
        self.tss_in_mgl = wq_parameters[
            'total suspended solids'][INPUT_WQPARAMETER_KEY]  # 150 mgl/l
        self.tss_out_mgl = wq_parameters[
            'total suspended solids'][TARGET_WQPARAMETER_KEY]  # 50 mgl/l
        self.water_viscosity = WATER_VISCOSITY_N_S_PER_M2  
        self.unit_height_m = (
            self.sand_bed_height_m +
            self.anthracite_bed_height_m + 1)  # additional height: 1m
        self.unit_volume_m3 = self.unit_area_m2 * self.unit_height_m
        #self.power_lane_kw = (
        #    DENS_WATER_KG_PER_M3 * GRAVITY_M_PER_S2 *
        #    self.flow_per_lane_m3perh * self.unit_height_m
        #    ) / (self.efficiency_pumps * 3600 * 1000)  # pumping power per lane
        self.backwash_pump_flow_m3_per_h = (
            np.ceil(self.unit_area_m2 * self.backwash_hydraulic_loading_rate_m3m2h)  # noqa: E501
            )
        self.backwash_pump_head_m = np.ceil(
            calculate_backwash_headloss_m(
                water_density_kg_per_m3=DENS_WATER_KG_PER_M3,
                sand_porosity=self.sand_porosity,
                anthracite_porosity=self.anthracite_porosity,
                sand_density_kg_per_m3=self.sand_density_kg_per_m3,
                anthracite_density_kg_per_m3=self.anthracite_density_kg_per_m3,
                sand_bed_height_m=self.sand_bed_height_m,
                anthracite_bed_height_m=self.anthracite_bed_height_m,
                tank_height=self.unit_height_m)
                )
        self.backwash_water_area_m2 = (
            self.backwash_pump_flow_m3_per_h * self.backwash_duration_min
            /(60 * self.backwash_tank_height_m))
        # rule of thumb Apump=3*Qpump (in m/s):
        self.backwash_pump_area_m2 = (
            2*(3 * self.backwash_pump_flow_m3_per_h/3600))
        self.backwash_area_m2 = (
            self.backwash_pump_area_m2 + self.backwash_water_area_m2)
        for tech_property in self.digest_parameter_list:
            if tech_property == 'filter area':
                self.filter_area_m2 = self.tanks_area_m2
                self.parameters[tech_property] = self.filter_area_m2  # overwrite filter area

    def __repr__(self):
        return f"Backwash nominal flow (m3/hr)={self.backwash_pump_flow_m3_per_h}, " \
                f"Backwash nominal head (m)={self.backwash_pump_head_m}), " \
               f"Vessel Height (m)={self.unit_height_m}, " \
                f"Vessel Area (m2)={self.unit_area_m2}) "               
            
    def get_kpi(self, kpi: str) -> float:
        """Get the value for a KPI"""
        function_name = TECH_KPI_MAPPINGS.get(kpi, None)
        if function_name is not None:
            return getattr(self, function_name)
        else:
            raise ValueError(
                f"KPI '{kpi}' not implemented for {self.__class__.__name__}.")

    def get_kpi_dict(self, kpi_list=None):
        if kpi_list:
            return {kpi: self.get_kpi(kpi=kpi) for kpi in kpi_list}
        return {kpi: self.get_kpi(kpi=kpi) for kpi in TECH_KPI_MAPPINGS.keys()}

    @property
    def footprint_area__m2(self) -> float:
        return np.ceil(1.1 * (self.tanks_area_m2 + self.backwash_area_m2))

    @property
    def footprint_area_for_chemicals__m2(self) -> float:
        return 0.0  # No chemicals used in Rapid Sand Filtration

    @property
    def daily_mass_of_chemicals__kg(self) -> dict[str, float]:
        return {}  # No chemicals used in Rapid Sand Filtration
    
    @property
    def chemical_solution_concentration__mg_per_l(self) -> float:
        return 0.0  # No chemicals used in Rapid Sand Filtration

    @property
    def hydraulic_headloss__bar(self) -> float:
        return calculate_hydraulic_headloss_rapid_sand_filters_m(
            water_density_kg_per_m3=DENS_WATER_KG_PER_M3,
            water_viscosity=self.water_viscosity,
            sand_porosity=self.sand_porosity,
            sand_media_grain_size=self.sand_media_grain_size,
            anthracite_porosity=self.sand_porosity,
            anthracite_media_grain_size=self.anthracite_media_grain_size,
            hydraulic_loading_rate_m3m2h=self.hydraulic_loading_rate_m3m2h,
            sand_bed_height_m=self.sand_bed_height_m,
            anthracite_bed_height_m=self.anthracite_bed_height_m,
            tank_height=self.unit_height_m)
        
    @property
    def power__kw(self) -> float:
        backwash_power_watts = (
            DENS_WATER_KG_PER_M3 * GRAVITY_M_PER_S2 *
            self.backwash_pump_head_m * self.backwash_pump_flow_m3_per_h/3600
        )
        backwash_power_kw = backwash_power_watts / (
            self.efficiency_pumps * 1000)
        return backwash_power_kw

    @property
    def daily_energy_consumption__kwh(self) -> float:
        total_amount_units = self.units_per_lane * self.lanes
        # Assuming one full backwash (all units one time) per day 
        backwash_frequency = 1 / 7
        return self.power__kw * (
            self.backwash_duration_min / 60) * total_amount_units * backwash_frequency

    @property
    def co2_emissions__kg_co2_eq_per_m3(self) -> float:
        if self.emission_factor_electricity is None:
            raise ValueError("Emission factor for electricity is not set.")
        co2_emissions = (
            self.daily_energy_consumption__kwh *
            self.emission_factor_electricity)
        specific_co2_emissions = co2_emissions / self.nominal_flow_m3perh / 24  # kg CO2 eq per m3
        return specific_co2_emissions


class RapidSandPressurizedVesselFiltration(TreatmentKPI):
    """KPI calculations for a Rapid Sand Filtration treatment unit."""
    tank_height: float
    lanes: int
    nominal_flow_m3perh: float
    units_per_lane: int
    nominal_flow_m3perh: float
    flow_per_unit_m3hr: float
    filter_bed_pressure_head_m: float
    power_lane_kw: float
    efficiency_pump: float
    backwash_duration_min: int
    backwash_tank_height_m: float
    backwash_flow_rate_m3_per_m2_per_h: float
    efficiency_backwash_pump: float
    flow_per_lane_m3perh: float
    unit_volume_m3: float
    unit_area_m2: float
    unit_depth_m: float
    tanks_area_m2: float
    backwash_pump_flow_m3_per_h: float
    backwash_pump_head_m: float
    backwash_pump_area_m2: float
    backwash_water_area_m2: float
    backwash_area_m2: float
    backwash_pump_head_m: float
    emission_factor_electricity: float
    
    def __post_init__(self):
        super().__post_init__()
        parameters = self.parameters
        design_parameters = self.design_parameters
        plant_kpis = self.plant_kpis
        # wq_parameters = self.wq_parameters
    
        self.nominal_flow_m3perh = plant_kpis.get(
            NOMINAL_FLOW_RATE_NAME, None)  # noqa: E501
        self.lanes = design_parameters.get('number of lanes', None)
        self.emission_factor_electricity = design_parameters.get(
            EMISSION_FACTOR_ELEC_NAME, None)
        self.flow_per_lane_m3perh = calculate_flow_per_lane(
            self.lanes, self.nominal_flow_m3perh)
        self.units_per_lane = parameters[TPN['units_per_lane']]
        self.units_per_lane = self.units_per_lane + 1
        self.flow_per_unit_m3hr = self.flow_per_lane_m3perh/(
            self.units_per_lane - 1)  #Always 1 pressurized filter stand-by
        self.unit_depth_m, self.unit_area_m2 = pressurisedvesselcalc_m_m2(
            flow_per_unit_m3hr=self.flow_per_unit_m3hr)
        self.tanks_area_m2 = (
            self.unit_area_m2 * self.units_per_lane * self.lanes)
        self.filter_bed_pressure_head_m = 3 + self.unit_depth_m  # average design value for losses
        self.backwash_duration_min = parameters[
            TPN['backwash_duration']]
        self.backwash_tank_height_m = parameters[
            TPN['backwash_tank_height']] 
        self.backwash_flow_rate__m3_per_m2_per_h = parameters[
            TPN['backwash_filtration_rate']]
        self.efficiency_pump = parameters[
            TPN['power_efficiency_of_pumps']]/100
        self.unit_volume_m3 = self.unit_area_m2 * self.unit_depth_m
        self.power_lane_kw = (
            DENS_WATER_KG_PER_M3 * GRAVITY_M_PER_S2 * self.flow_per_lane_m3perh * 
            self.unit_depth_m) / (self.efficiency_pump * 3600 * 1000)  # pumping power required per lane
        self.backwash_pump_flow_m3_per_h = (
            np.ceil(self.unit_area_m2 * self.backwash_flow_rate__m3_per_m2_per_h)  # noqa: E501
            )
        self.backwash_pump_head_m = 1.5 * self.unit_depth_m         
        self.backwash_water_area_m2 = (
            self.backwash_pump_flow_m3_per_h * self.backwash_duration_min
            /(60 * self.backwash_tank_height_m))
        self.backwash_pump_area_m2 = (
            2 * (3 * self.backwash_pump_flow_m3_per_h/3600))    # rule of thumb of Apump=3*Qpump (in m/s)
        self.backwash_area_m2 = (
            self.backwash_pump_area_m2 + self.backwash_water_area_m2)
        for tech_property in self.digest_parameter_list:
            if tech_property == 'filter area':
                self.filter_area_m2 = self.tanks_area_m2
                self.parameters[tech_property] = self.filter_area_m2

    def __repr__(self):
        return f"Backwash nominal flow (m3/hr)={self.backwash_pump_flow_m3_per_h}, " \
                f"Backwash nominal head (m)={self.backwash_pump_head_m}), " \
               f"Pressurized Vessel Height (m)={self.unit_depth_m}, " \
                f"Pressurized Vessel Area (m2)={self.unit_area_m2}) "               
            
    def get_kpi(self, kpi: str) -> float:
        """Get the value for a KPI"""
        function_name = TECH_KPI_MAPPINGS.get(kpi, None)
        if function_name is not None:
            return getattr(self, function_name)
        else:
            raise ValueError(
                f"KPI '{kpi}' not implemented for {self.__class__.__name__}.")

    def get_kpi_dict(self, kpi_list=None):
        if kpi_list:
            return {kpi: self.get_kpi(kpi=kpi) for kpi in kpi_list}
        return {kpi: self.get_kpi(kpi=kpi) for kpi in TECH_KPI_MAPPINGS.keys()}

    @property
    def footprint_area__m2(self) -> float:
        return np.ceil(1.1 * (self.tanks_area_m2 + self.backwash_area_m2))

    @property
    def footprint_area_for_chemicals__m2(self) -> float:
        return 0.0  # No chemicals used in Rapid Sand Filtration

    @property
    def daily_mass_of_chemicals__kg(self) -> dict[str, float]:
        return {}  # No chemicals used in Rapid Sand Filtration
    
    @property
    def chemical_solution_concentration__mg_per_l(self) -> float:
        return 0.0  # No chemicals used in Rapid Sand Filtration

    @property
    def hydraulic_headloss__bar(self) -> float:
        return meters_of_water_to_bar(self.filter_bed_pressure_head_m)

    @property
    def power__kw(self) -> float:
        backwash_power_watts = (
            DENS_WATER_KG_PER_M3 * GRAVITY_M_PER_S2 *
            self.backwash_pump_head_m * self.backwash_pump_flow_m3_per_h/3600
        )
        total_efficiency = self.efficiency_pump
        backwash_power_kw = backwash_power_watts / (total_efficiency * 1000)
        power_kw = (self.lanes * self.power_lane_kw) + backwash_power_kw # projected over hours and days. 
        return power_kw

    @property
    def daily_energy_consumption__kwh(self) -> float:
        norm_oper = self.lanes * self.power_lane_kw *24 
        backwash_kW=self.power__kw-(self.lanes * self.power_lane_kw)
        backwash_oper = backwash_kW * (self.backwash_duration_min / 60) * self.units_per_lane * self.lanes * (1/7)
        return norm_oper +  backwash_oper # Assuming one full backwash (all units one time) per day

    @property
    def co2_emissions__kg_co2_eq_per_m3(self) -> float:
        if self.emission_factor_electricity is None:
            raise ValueError("Emission factor for electricity is not set.")
        co2_emissions = (
            self.daily_energy_consumption__kwh *
            self.emission_factor_electricity)
        specific_co2_emissions = co2_emissions / self.nominal_flow_m3perh / 24  # kg CO2 eq per m3
        return specific_co2_emissions

class RapidSandMovingBedFiltration(TreatmentKPI):
    """KPI calculations for a Rapid Sand Filtration treatment unit."""
    tank_height: float
    lanes: int
    nominal_flow_m3perh: float
    units_per_lane: int
    flow_per_unit_m3hr: float
    filter_bed_pressure_head_m: float
    power_lane_kw: float
    flow_per_lane_m3perh: float
    unit_volume_m3: float
    unit_area_m2: float
    unit_height_m: float
    unit_kw :float
    tanks_area_m2: float
    emission_factor_electricity: float
    
    def __post_init__(self):
        super().__post_init__()
        parameters = self.parameters
        design_parameters = self.design_parameters
        plant_kpis = self.plant_kpis
        # wq_parameters = self.wq_parameters

        self.nominal_flow_m3perh = plant_kpis.get(
            NOMINAL_FLOW_RATE_NAME, None)  # noqa: E501
        self.lanes = design_parameters.get('number of lanes', None)
        self.emission_factor_electricity = design_parameters.get(
            EMISSION_FACTOR_ELEC_NAME, None)
        self.flow_per_lane_m3perh = calculate_flow_per_lane(
            self.lanes, self.nominal_flow_m3perh)
        self.units_per_lane = parameters[TPN['units_per_lane']]
        self.flow_per_unit_m3hr = self.flow_per_lane_m3perh/(
            self.units_per_lane - 1)  #Always 1 pressurized filter stand-by
        (
            self.unit_height_m,
            self.unit_area_m2,
            self.unit_power_kw) = movingbedvesselcalc_m_m2(
            flow_per_unit_m3hr=self.flow_per_unit_m3hr)
        self.tanks_area_m2 = (
            self.unit_area_m2 * self.units_per_lane * self.lanes)        
        self.filter_bed_pressure_head_m = 3 + self.unit_height_m  # average design value for losses

    def __repr__(self):
        return f"Moving bed filtration height (m)={self.unit_height_m}, " \
               f"Moving bed filtration area (m2)={self.unit_area_m2}, " \
               f"Moving bed filtration installed power (kW)={self.unit_power_kw}, " 
              
            
    def get_kpi(self, kpi: str) -> float:
        """Get the value for a KPI"""
        function_name = TECH_KPI_MAPPINGS.get(kpi, None)
        if function_name is not None:
            return getattr(self, function_name)
        else:
            raise ValueError(
                f"KPI '{kpi}' not implemented for {self.__class__.__name__}.")

    def get_kpi_dict(self, kpi_list=None):
        if kpi_list:
            return {kpi: self.get_kpi(kpi=kpi) for kpi in kpi_list}
        return {kpi: self.get_kpi(kpi=kpi) for kpi in TECH_KPI_MAPPINGS.keys()}

    @property
    def footprint_area__m2(self) -> float:
        return np.ceil(1.1 * (self.tanks_area_m2))

    @property
    def footprint_area_for_chemicals__m2(self) -> float:
        return 0.0  # No chemicals used in Rapid Sand Filtration

    @property
    def daily_mass_of_chemicals__kg(self) -> dict[str, float]:
        return {}  # No chemicals used in Rapid Sand Filtration
    
    @property
    def chemical_solution_concentration__mg_per_l(self) -> float:
        return 0.0  # No chemicals used in Rapid Sand Filtration

    @property
    def hydraulic_headloss__bar(self) -> float:
        return calculate_hydraulic_headloss_rapid_sand_filters_m(
            water_density_kg_per_m3=DENS_WATER_KG_PER_M3,
            water_viscosity=self.water_viscosity,
            sand_porosity=self.sand_porosity,
            sand_media_grain_size=self.sand_media_grain_size,
            anthracite_porosity=self.sand_porosity,
            anthracite_media_grain_size=self.anthracite_media_grain_size,
            hydraulic_loading_rate_m3m2h=self.hydraulic_loading_rate_m3m2h,
            sand_bed_depth_m=self.sand_bed_height_m,
            anthracite_bed_depth_m=self.anthracite_bed_height_m,
            tank_height=self.unit_height_m)
            
    @property
    def power__kw(self) -> float:
        power_kw = self.lanes * self.power_lane_kw  # projected over hours and days. 
        return power_kw


    @property
    def co2_emissions__kg_co2_eq_per_m3(self) -> float:
        if self.emission_factor_electricity is None:
            raise ValueError("Emission factor for electricity is not set.")
        co2_emissions = (
            self.daily_energy_consumption__kwh *
            self.emission_factor_electricity)
        specific_co2_emissions = co2_emissions / self.nominal_flow_m3perh / 24  # kg CO2 eq per m3
        return specific_co2_emissions


class GranularActivatedCarbonFiltration(TreatmentKPI):
    """KPI calculations for a Granular Activated Carbon (GAC) treatment unit."""
    lanes: int
    nominal_flow_m3perh: float
    units_per_lane: int
    empty_bed_contact_time: int
    hydraulic_loading_rate_m3m2h: int
    gac_porosity: float
    particle_diameter: float
    filter_bed_depth_m: float
    flow_per_lane_m3perh: float
    superficial_velocity: float
    flow_per_unit_m3hr: float
    unit_volume_m3: float
    unit_area_m2: float
    unit_height_m: float
    tanks_area_m2: float
    emission_factor_electricity: float
    volume_m3: float
    gac_density_kg_per_m3: float
    gac_regeneration_energy_kWhperm3: float 
    regeneration_interval_days: float
    chemical_emission_factor: float
    
    def __post_init__(self):
        super().__post_init__()
        parameters = self.parameters
        design_parameters = self.design_parameters
        plant_kpis = self.plant_kpis
        wq_parameters = self.wq_parameters

        self.nominal_flow_m3perh = plant_kpis.get(
            NOMINAL_FLOW_RATE_NAME, None)  # noqa: E501
        self.lanes = design_parameters.get('number of lanes', None)
        self.emission_factor_electricity = design_parameters.get(
            EMISSION_FACTOR_ELEC_NAME, None)
        self.flow_per_lane_m3perh = calculate_flow_per_lane(
            self.lanes, self.nominal_flow_m3perh)
        self.units_per_lane = parameters[TPN['units_per_lane']]
        self.hydraulic_loading_rate_m3m2h = parameters[
            TPN['filtration_rate']]
        self.gac_porosity = parameters[
            TPN['gac_porosity']]
        self.empty_bed_contact_time = parameters[
            TPN['empty_bed_contact_time']]
        self.particle_diameter = parameters[
            TPN['grain_diameter']]
        self.gac_density_kg_per_m3 = parameters[
            TPN['mass_density_of_chemical']] * 1000
        self.chemical_emission_factor = parameters[
            TPN['chemical_emission_factor']]
        self.anthracite_bed_depth_m = 0
        self.flow_per_unit_m3hr = (
            self.flow_per_lane_m3perh / self.units_per_lane)
        self.unit_volume_m3 = (
            self.empty_bed_contact_time * self.flow_per_unit_m3hr / 60)
        self.unit_area_m2 = (
            self.flow_per_unit_m3hr / self.hydraulic_loading_rate_m3m2h)
        self.bed_height_m = self.unit_height_m = (
            np.ceil(self.unit_volume_m3 / self.unit_area_m2))
        self.unit_height_m = (
            np.ceil(self.unit_volume_m3 / self.unit_area_m2 + 1))
        self.doc_in_mgl = wq_parameters[
            'dissolved organic carbon'][INPUT_WQPARAMETER_KEY]  # mgl/l
        self.doc_out_mgl = wq_parameters[
            'dissolved organic carbon'][TARGET_WQPARAMETER_KEY]
        self.regeneration_interval_days = parameters[
            TPN['gac_regeneration_interval']] 
        self.gac_regeneration_energy_kWhperm3 = parameters[
            TPN['regeneration_energy_per_kg_of_gac']]
        self.water_viscosity = design_parameters.get(
            'dynamic viscosity', WATER_VISCOSITY_N_S_PER_M2)
        self.tanks_area_m2 = (
            self.unit_area_m2 * self.units_per_lane * self.lanes)
        self.superficial_velocity = (        
            self.flow_per_unit_m3hr/self.unit_area_m2)
        for tech_property in self.digest_parameter_list:
            if tech_property == 'volume':
                self.volume_m3 = self.unit_volume_m3 * self.units_per_lane * self.lanes
                self.parameters[tech_property] = self.volume_m3  
            elif tech_property == 'filter area':
                self.unit_area = self.unit_area_m2
                self.parameters[tech_property] = self.unit_area  
            elif tech_property == 'bed height':
                self.bed_height_m = (
                    np.ceil(self.unit_volume_m3 / self.unit_area_m2))
                self.parameters[tech_property] = self.bed_height_m  
        self.gac_inventory_kg = (
            self.unit_volume_m3 * self.units_per_lane * self.lanes * self.gac_density_kg_per_m3)

    def __repr__(self):
        return f"GAC bed area (m2)={self.unit_area_m2}, " \
                f"GAC filtration rate (m2/m3/h)={self.hydraulic_loading_rate_m3m2h}"
            
    def get_kpi(self, kpi: str) -> float:
        """Get the value for a KPI"""
        function_name = TECH_KPI_MAPPINGS.get(kpi, None)
        if function_name is not None:
            return getattr(self, function_name)
        else:
            raise ValueError(
                f"KPI '{kpi}' not implemented for {self.__class__.__name__}.")

    def get_kpi_dict(self, kpi_list=None):
        if kpi_list:
            return {kpi: self.get_kpi(kpi=kpi) for kpi in kpi_list}
        return {kpi: self.get_kpi(kpi=kpi) for kpi in TECH_KPI_MAPPINGS.keys()}

    @property
    def footprint_area__m2(self) -> float:
        return np.ceil(self.tanks_area_m2 * 1.1)

    @property
    def footprint_area_for_chemicals__m2(self) -> float:
        return 0.0

    @property
    def daily_mass_of_chemicals__kg(self) -> dict[str, float]:
        gac_loss_fraction = 0.05 # assuming 5% loss per regeneration
        gac_perday = self.gac_inventory_kg * gac_loss_fraction / self.regeneration_interval_days 
        return self._single_chemical_value(gac_perday)  
    
    @property
    def chemical_solution_concentration__mg_per_l(self) -> float:
        return 0.0  

    @property
    def hydraulic_headloss__bar(self) -> float:
        headloss = calculate_headloss_over_filtration_media(
            water_viscosity=self.water_viscosity,
            water_density_kg_per_m3=DENS_WATER_KG_PER_M3,
            porosity=self.gac_porosity,
            grain_size=self.particle_diameter,
            hydraulic_loading_rate_m3m2h=self.superficial_velocity,
            filter_bed_height_m=self.bed_height_m 
        )
        return meters_of_water_to_bar(headloss)
            
    @property
    def power__kw(self) -> float:
        power_kw = 0
        return power_kw  

    @property
    def daily_energy_consumption__kwh(self) -> float:
        """Apply a reduced duty-cycle factor to daily energy use."""
        gac_energy_kwh = self.gac_inventory_kg * self.gac_regeneration_energy_kWhperm3 / self.regeneration_interval_days 
        return gac_energy_kwh

    @property
    def co2_emissions__kg_co2_eq_per_m3(self) -> float:
        if self.emission_factor_electricity is None:
            raise ValueError("Emission factor for electricity is not set.")
        co2_emissions = (
            self.daily_energy_consumption__kwh *
            self.emission_factor_electricity)
        masses = self.daily_mass_of_chemicals__kg 
        emission_factors = self._resolve_per_chemical_factors(
            factor=self.chemical_emission_factor,
            default_value=float(self.chemical_emission_factor),
        )
        chemical_co2_emissions = sum(
            masses.get(chem_name, 0.0) * emission_factors.get(chem_name, 0.0)
            for chem_name in masses
        )
        return (co2_emissions + chemical_co2_emissions
                ) / self.nominal_flow_m3perh / 24


class PowderedActivatedCarbonFiltration(TreatmentKPI):
    """KPI calculations for a Powdered Activated Carbon (PAC) treatment unit."""
    tank_height_m: float
    silo_height_m: float
    lanes: int
    units_per_lane: int
    nominal_flow_m3perh: float
    flow_per_lane_m3perh: float
    storage_time_days: float
    pac_dosage_mg_liter: float
    pac_bulk_density_kg_m3: float
    slurry_concentration_w_w: float
    power_total_kw: float
    retention_time_min: float
    unit_volume_m3: float
    unit_area_m2: float
    unit_depth_m: float
    tanks_area_m2: float
    power_mixing_intensity_wperm3: float
    chemical_emission_factor: float
    emission_factor_electricity: float
    area_m2: float

    def __post_init__(self):
        super().__post_init__()
        parameters = self.parameters
        design_parameters = self.design_parameters
        plant_kpis = self.plant_kpis
        # wq_parameters = self.wq_parameters
        
        self.units_per_lane = parameters[TPN['units_per_lane']]
        self.lanes = design_parameters.get('number of lanes', None)
        self.unit_depth_m = parameters[TPN['tank_height']]
        self.silo_height_m = parameters.get(TPN['tank_height_chemical_storage'], 10.0)  # Average Silo Height
        self.nominal_flow_m3perh = plant_kpis.get(
            NOMINAL_FLOW_RATE_NAME, None)  # noqa: E501
        self.chemical_emission_factor = parameters[
            TPN['chemical_emission_factor']]
        self.emission_factor_electricity = design_parameters.get(
            EMISSION_FACTOR_ELEC_NAME, None)  
        self.flow_per_lane_m3perh = calculate_flow_per_lane(
            self.lanes, self.nominal_flow_m3perh)
        self.storage_time_days = parameters.get(
            TPN['storage_time_of_chemicals_days'], 30)
        self.pac_dosage_mg_liter = parameters[
            TPN['pac_dosage_concentration']]
        self.slurry_tank_height_m = parameters[TPN['slurry_tank_height']]
        self.pac_bulk_density_kg_m3 = parameters[
            TPN['mass_density_of_chemical']] * 1000
        # Convert from w/w% to w/w fraction
        self.slurry_concentration_w_w = parameters[
            TPN['pac_slurry_concentration']] / 100 # 5% w/w
        self.retention_time_min = parameters[TPN['retention_time_min']]
        self.power_mixing_intensity_wperm3 = parameters[
            TPN['power_density']]  # 10 W/m3
        for tech_property in self.digest_parameter_list:
            if tech_property == 'area':
                self.area_m2 = self.footprint_area__m2
                self.parameters[tech_property] = self.area_m2  # overwrite area

    def __repr__(self):
        return f"PAC tank height (m)={self.unit_depth_m}, " \
               f"silo height (m)={self.silo_height_m}, " \
               f"dosage (mg/L)={self.pac_dosage_mg_liter}, " \
               f"nominal flow (m3/hr)={self.nominal_flow_m3perh})"

    def get_kpi(self, kpi: str) -> float:
        """Get the value for a KPI"""
        function_name = TECH_KPI_MAPPINGS.get(kpi, None)
        if function_name is not None:
            return getattr(self, function_name)
        else:
            raise ValueError(
                f"KPI '{kpi}' not implemented for {self.__class__.__name__}.")

    def get_kpi_dict(self, kpi_list=None):
        if kpi_list:
            return {kpi: self.get_kpi(kpi=kpi) for kpi in kpi_list}
        return {kpi: self.get_kpi(kpi=kpi) for kpi in TECH_KPI_MAPPINGS.keys()}
    
    @property
    def daily_mass_of_chemicals__kg(self) -> dict[str, float]:
        """Calculates total dry PAC required per day."""
        hourly_mass = (self.nominal_flow_m3perh *
                       self.pac_dosage_mg_liter) / 1000
        return self._single_chemical_value(hourly_mass * 24)
    
    @property
    def chemical_solution_concentration__mg_per_l(self) -> float:
        return 0.0  # TODO

    @property
    def footprint_area_for_chemicals__m2(self) -> float:
        """Calculates the area required for the PAC storage silo."""
        safety_factor = 1.2  # Factor for PAC aeration/fluffing
        total_mass_stored = (
            self.sum_per_chemical(self.daily_mass_of_chemicals__kg)
            * self.storage_time_days
        )
        required_volume_m3 = (total_mass_stored /
                              self.pac_bulk_density_kg_m3) * safety_factor
        return required_volume_m3 / self.silo_height_m

    @property
    def footprint_area__m2(self) -> float:
        """Total area including Contact Basin and Silo storage."""
        unit_volume_m3 = calculate_unit_volume_m3(
            flow_per_lane_m3h=self.flow_per_lane_m3perh,
            units_per_lane=self.units_per_lane,
            retention_time_min=self.retention_time_min)
        unit_area_m2 = calculate_unit_area_tank(
            unit_volume_m3=unit_volume_m3,
            unit_height_m=self.unit_depth_m)
        storage_area_m2 = self.footprint_area_for_chemicals__m2
        daily_mass_kg = self.sum_per_chemical(self.daily_mass_of_chemicals__kg)
        volume_slurry_m3 = daily_mass_kg / (
            self.slurry_concentration_w_w * DENS_WATER_KG_PER_M3)
        slurry_tank_area_m2 = volume_slurry_m3 / self.slurry_tank_height_m
        return np.ceil(
            (unit_area_m2 * self.lanes + storage_area_m2 + slurry_tank_area_m2) * 1.1)

    @property
    def hydraulic_headloss__bar(self) -> float:
        """Headloss through the contact basin baffles."""
        return 0.03 + meters_of_water_to_bar(self.unit_depth_m)  # Approx 0.3m converted to bar

    @property
    def power__kw(self) -> float:
        """Total power for PAC."""
        seconds_per_day = 86400
        dosing_head_m = self.silo_height_m + 2.0
        total_mass_kg = self.sum_per_chemical(self.daily_mass_of_chemicals__kg)
        volume_chemical_day = total_mass_kg / self.pac_bulk_density_kg_m3
        flow_chemical_m3_s = volume_chemical_day / seconds_per_day
        power_pump_kw = (
            self.pac_bulk_density_kg_m3 * GRAVITY_M_PER_S2 *
            flow_chemical_m3_s * dosing_head_m) / (
                0.8 * 1000)
        power_mixing_kw = (self.flow_per_lane_m3perh * self.power_mixing_intensity_wperm3 *
            self.lanes) / 1000
        return (power_mixing_kw + power_pump_kw)  # Estimation of H202 dosage pumps of 0.1kW

    @property
    def co2_emissions__kg_co2_eq_per_m3(self) -> float:
        if self.emission_factor_electricity is None:
            raise ValueError("Emission factor for electricity is not set.")
        co2_emissions = (
            self.daily_energy_consumption__kwh *
            self.emission_factor_electricity)
        masses = self.daily_mass_of_chemicals__kg 
        emission_factors = self._resolve_per_chemical_factors(
            factor=self.chemical_emission_factor,
            default_value=float(self.chemical_emission_factor),
        )
        chemical_co2_emissions = sum(
            masses.get(chem_name, 0.0) * emission_factors.get(chem_name, 0.0)
            for chem_name in masses
        )
        return (co2_emissions + chemical_co2_emissions
                ) / self.nominal_flow_m3perh / 24


class UVAOP(TreatmentKPI):
    """KPI calculations for a UV/H2O2 Advanced Oxidation Process (AOP) unit."""
    tank_height_m: float
    chemicals_tank_height_m: float
    lanes: int
    units_per_lane: int
    nominal_flow_m3perh: float
    flow_per_lane_m3perh: float
    conc_chem_mgL: float
    solution_wwperc: float
    energy_per_m3_kwh: float
    storage_time_days: float
    exposure_time_sec: float
    lane_volume_m3: float
    lane_area_m2: float
    chemical_emission_factor: float
    emission_factor_electricity: float

    def __post_init__(self):
        super().__post_init__()
        parameters = self.parameters
        plant_kpis = self.plant_kpis
        design_parameters = self.design_parameters
        # wq_parameters = self.wq_parameters
        
        self.lanes = design_parameters.get('number of lanes', None)
        self.tank_height_m = parameters[TPN['tank_height']]
        self.nominal_flow_m3perh = plant_kpis.get(
            NOMINAL_FLOW_RATE_NAME, None)
        self.chemical_emission_factor = parameters[
            TPN['chemical_emission_factor']]
        self.emission_factor_electricity = design_parameters.get(
            EMISSION_FACTOR_ELEC_NAME, None)  
        self.flow_per_lane_m3perh = calculate_flow_per_lane(
            self.lanes, self.nominal_flow_m3perh)
        self.units_per_lane = parameters[TPN['units_per_lane']]
        self.conc_chem_mgL = parameters[
            TPN['target_concentration_of_dosing_chemical']]
        self.solution_wwperc = parameters[
            TPN['chemical_dosing_solution_concentration_w_per_wpercent']]
        self.chemicals_tank_height_m = parameters[
            TPN['tank_height_chemical_storage']]
        self.storage_time_days = parameters[TPN['storage_time_of_chemicals_days']]
        self.energy_per_m3_kwh = parameters[
            TPN['energy_intensity']]
        self.volume_chemical_day = calculate_dosing_volume__m3perday_perunit(
            concentration_mgL=self.conc_chem_mgL,
            flow_per_lane_m3hr=self.flow_per_lane_m3perh,
            units_per_lane=1,
            solution_concentration_w_w_percent=self.solution_wwperc,
        ) * self.lanes  # m3/day
        for tech_property in self.digest_parameter_list:
            if tech_property == 'nominal dosing flow rate':
                self.dosing_flow_rate_liter = 1000 * self.volume_chemical_day / 24
                self.parameters[tech_property] = self.dosing_flow_rate_liter 

    def __repr__(self):
        return f"UV AOP tank height (m)={self.tank_height_m}, " \
               f"chemicals tank height (m)={self.chemicals_tank_height_m}, " \
               f"dosage HO2 (mg/L)={self.conc_chem_mgL}."

    def get_kpi(self, kpi: str) -> float:
        """Get the value for a KPI"""
        function_name = TECH_KPI_MAPPINGS.get(kpi, None)
        if function_name is not None:
            return getattr(self, function_name)
        else:
            raise ValueError(
                f"KPI '{kpi}' not implemented for {self.__class__.__name__}.")

    def get_kpi_dict(self, kpi_list=None):
        if kpi_list:
            return {kpi: self.get_kpi(kpi=kpi) for kpi in kpi_list}
        return {kpi: self.get_kpi(kpi=kpi) for kpi in TECH_KPI_MAPPINGS.keys()}

    @property
    def daily_mass_of_chemicals__kg(self) -> dict[str, float]:
        """Calculates daily mass of pure H2O2 required."""
        daily_flow_m3 = self.nominal_flow_m3perh * 24
        mass_kg_per_day = (daily_flow_m3 * self.conc_chem_mgL) / 1000.0
        return self._single_chemical_value(mass_kg_per_day)

    @property
    def footprint_area_for_chemicals__m2(self) -> float:
        """Calculates area for H2O2 storage tanks including safety bunding."""
        daily_mass_solution_kg = (
            self.sum_per_chemical(self.daily_mass_of_chemicals__kg)
            / self.solution_wwperc
        )
        # Density of 35% H2O2 is ~1.1 kg/L:
        volume_m3 = daily_mass_solution_kg / 1100.0
        total_storage_vol_m3 = volume_m3 * self.storage_time_days
        base_area = total_storage_vol_m3 / self.chemicals_tank_height_m
        return base_area * 1.2

    @property
    def footprint_area__m2(self) -> float:
        reactor_area_per_unit = 8
        electrical_area_per_unit = 3
        maintenance_area_per_unit = 1

        uv_area = (
            self.lanes *
            self.units_per_lane *
            (
                reactor_area_per_unit +
                electrical_area_per_unit+
                maintenance_area_per_unit
            )
        )
        return np.ceil(uv_area + self.footprint_area_for_chemicals__m2)

    @property
    def power__kw(self) -> float:
        """Total power for UV lamps in AOP mode."""
        seconds_per_day = 86400
        dosing_head_m = self.chemicals_tank_height_m + 2.0
        flow_chemical_m3_s = self.volume_chemical_day / seconds_per_day
        power_pump_kw = (
            1197 * GRAVITY_M_PER_S2 *
            flow_chemical_m3_s * dosing_head_m) / (0.8 * 1000)
        return (
            self.flow_per_lane_m3perh * self.energy_per_m3_kwh *
            self.lanes + power_pump_kw)  # Estimation of H202 dosage pumps of 0.1kW


    @property
    def hydraulic_headloss__bar(self) -> float:
        unit_flow_m3_pers=(self.flow_per_lane_m3perh/self.units_per_lane)/3600
        diameter_m=0.4
        area_m2= np.pi * diameter_m**2 /4
        velocity_m_pers = unit_flow_m3_pers / area_m2
        K=15 #loss coefficient
        headloss = K * velocity_m_pers**2 / (2*GRAVITY_M_PER_S2)
        return meters_of_water_to_bar(self.tank_height_m + headloss)  

    @property
    def co2_emissions__kg_co2_eq_per_m3(self) -> float:
        if self.emission_factor_electricity is None:
            raise ValueError("Emission factor for electricity is not set.")
        co2_emissions = (
            self.daily_energy_consumption__kwh *
            self.emission_factor_electricity)
        masses = self.daily_mass_of_chemicals__kg
        emission_factors = self._resolve_per_chemical_factors(
            factor=self.chemical_emission_factor,
            default_value=float(self.chemical_emission_factor),
        )
        chemical_co2_emissions = sum(
            masses.get(chem_name, 0.0) * emission_factors.get(chem_name, 0.0)
            for chem_name in masses
        )
        return (co2_emissions + chemical_co2_emissions
                ) / self.nominal_flow_m3perh / 24


class BaffledOzonationContactor(TreatmentKPI):
    """KPI calculations for an Ozonation treatment unit."""
    tank_height_m: float
    lanes: int
    units_per_lane: int
    nominal_flow_m3perh: float
    retention_time_min: float
    ozone_dosage_mgliter: float
    energy_per_kg_ozone_kwh: float  # Energy efficiency of the ozonator
    flow_per_unit_m3hr: float
    lane_volume_m3: float
    lane_area_m2: float
    tank_area_m2: float
    volume_m3: float
    equipment_area_m2: float
    chemical_emission_factor: float
    emission_factor_electricity: float

    def __post_init__(self):
        super().__post_init__()
        parameters = self.parameters
        plant_kpis = self.plant_kpis
        design_parameters = self.design_parameters
        wq_parameters = self.wq_parameters

        self.lanes = design_parameters.get('number of lanes', None)
        self.nominal_flow_m3perh = plant_kpis.get(NOMINAL_FLOW_RATE_NAME, None)
        self.chemical_emission_factor = parameters[
            TPN['chemical_emission_factor']]
        self.emission_factor_electricity = design_parameters.get(
            EMISSION_FACTOR_ELEC_NAME, None)  
        self.flow_per_lane_m3perh = calculate_flow_per_lane(
            self.lanes, self.nominal_flow_m3perh)
        self.units_per_lane = parameters[TPN['units_per_lane']]
        self.flow_per_unit_m3hr = self.flow_per_lane_m3perh/self.units_per_lane 
        self.tank_height_m = parameters[TPN['tank_height']]
        self.retention_time_min = parameters[TPN['retention_time_min']]
        self.ozone_dosage_mgliter = parameters[
            TPN['target_concentration_of_dosing_chemical']]  # 3 mg/l
        self.energy_per_kg_ozone_kwh = parameters[
            TPN['energy_consumption_per_kg_ozone']]  # 8
        self.ecoli_initial = wq_parameters['E-Coli'][
            INPUT_WQPARAMETER_KEY]
        self.uv254_initial = wq_parameters['UV 254'][
            INPUT_WQPARAMETER_KEY]
        self.bromate_initial = wq_parameters['bromate'][
            INPUT_WQPARAMETER_KEY]
        self.aoc_initial = wq_parameters['assimilable organic carbon'][
            INPUT_WQPARAMETER_KEY]
        self.bromide_initial = wq_parameters['bromide'][
            INPUT_WQPARAMETER_KEY]
        self.bromate_final = wq_parameters['bromate'][TARGET_WQPARAMETER_KEY] 
        for tech_property in self.digest_parameter_list:
            if tech_property == 'volume':
                self.volume_m3 = (
                    self.flow_per_lane_m3perh * self.lanes *
                    self.retention_time_min) / 60.0
                self.parameters[tech_property] = self.volume_m3  # overwrite volume
        for tech_property in self.digest_parameter_list:
            if tech_property == 'area':
                self.area_m2 = self.volume_m3 / self.tank_height_m
                self.parameters[tech_property] = self.area_m2  # overwrite area

    def __repr__(self):
        return f"Ozonation tank height (m)={self.tank_height_m}, " \
               f"ozone dosage (mg/L)={self.ozone_dosage_mgliter}, " \
               f"nominal flow (m3/hr)={self.nominal_flow_m3perh})"

    def get_kpi(self, kpi: str) -> float:
        """Get the value for a KPI"""
        function_name = TECH_KPI_MAPPINGS.get(kpi, None)
        if function_name is not None:
            return getattr(self, function_name)
        else:
            raise ValueError(
                f"KPI '{kpi}' not implemented for {self.__class__.__name__}.")

    def get_kpi_dict(self, kpi_list=None):
        if kpi_list:
            return {kpi: self.get_kpi(kpi=kpi) for kpi in kpi_list}
        return {kpi: self.get_kpi(kpi=kpi) for kpi in TECH_KPI_MAPPINGS.keys()}

    @property
    def daily_mass_of_chemicals__kg(self) -> dict[str, float]:
        """Total ozone gas generated per day."""
        mass_kg_per_day = (
            self.nominal_flow_m3perh * 24 * self.ozone_dosage_mgliter
        ) / 1000.0
        return self._single_chemical_value(mass_kg_per_day)

    @property
    def footprint_area_for_chemicals__m2(self) -> float:
        """Ozone is generated on site from oxygen."""
        return 0.0

    @property
    def chemical_solution_concentration__mg_per_l(self) -> float:
        return self.ozone_dosage_mgliter 

    @property
    def footprint_area__m2(self) -> float:
        """
        Total Area = Contact Tank Area + Ozonator Equipment Room.
        """
        lane_volume_m3 = self.volume_m3 / self.lanes
        lane_area_m2 = lane_volume_m3 / self.tank_height_m
        tanks_area_m2 = lane_area_m2 * self.lanes
        ozone_flow_kg_per_h = (
            self.ozone_dosage_mgliter * self.nominal_flow_m3perh
            ) / 1000.0  # kg O3 per hour
        equipment_area_m2 = 1.1 * ozone_flow_kg_per_h * 10  # Assume
        return np.ceil(tanks_area_m2 + equipment_area_m2)

    @property
    def power__kw(self) -> float:
        """Calculates power consumption of the ozone generator + oxygen feed system."""
        kg_o3_per_hour = (
            self.nominal_flow_m3perh * self.ozone_dosage_mgliter
            ) / 1000.0
        return kg_o3_per_hour * self.energy_per_kg_ozone_kwh

    @property
    def hydraulic_headloss__bar(self) -> float:
        # Pressure required to overcome the water column in the contact tank
        # Roughly 0.1 bar per 1m of depth + diffuser friction
        return meters_of_water_to_bar(
            self.tank_height_m * 0.5 + 3)  # 3m extra losses

    @property
    def co2_emissions__kg_co2_eq_per_m3(self) -> float:
        if self.emission_factor_electricity is None:
            raise ValueError("Emission factor for electricity is not set.")
        co2_emissions = (
            self.daily_energy_consumption__kwh *
            self.emission_factor_electricity)
        specific_co2_emissions = co2_emissions / self.nominal_flow_m3perh / 24  # kg CO2 eq per m3
        return specific_co2_emissions


class PelletSoftening(TreatmentKPI):
    """KPI calculations for a Pellet Reactor Softening unit."""
    unit_depth_m: float
    unit_area_m2: float
    unit_diam_m: float
    lanes: int
    units_per_lane: int
    nominal_flow_m3perh: float
    total_hardness_in_mgliter: float
    target_hardness_mgliter: float
    target_upflow_velocity_mperh: float
    rho_pellet: float
    rho_lime_kgm3: float
    porosity_static: float
    porosity_expanded: float
    hardness_removed_kg: float
    lime_req_kgperday: float
    pellets_out_kg: float
    seed_req_kg: float
    chemical_emission_factor: float
    emission_factor_electricity: float
    area_m2: float

    def __post_init__(self):
        super().__post_init__()
        parameters = self.parameters
        plant_kpis = self.plant_kpis
        design_parameters = self.design_parameters
        wq_parameters = self.wq_parameters

        self.lanes = design_parameters.get('number of lanes', None)
        self.units_per_lane = parameters[TPN['units_per_lane']]
        self.nominal_flow_m3perh = plant_kpis.get(
            NOMINAL_FLOW_RATE_NAME, None)
        self.chemical_emission_factor = parameters[TPN['chemical_emission_factor']]
        self.emission_factor_electricity = design_parameters.get(
            EMISSION_FACTOR_ELEC_NAME, None)
        operational_units = (
            self.units_per_lane - 1) if self.units_per_lane > 1 else self.units_per_lane  # noqa: E501
        self.flow_per_unit_m3hr = self.nominal_flow_m3perh / (
            self.lanes * operational_units)
        self.total_hardness_in_mgliter = wq_parameters['total hardness'][
            INPUT_WQPARAMETER_KEY]
        self.target_hardness_mgliter = wq_parameters['total hardness'][
            TARGET_WQPARAMETER_KEY]
        self.target_upflow_velocity_mperh = parameters[
            TPN['target_upflow_velocity']]
        self.delta_c = max(
            0, self.total_hardness_in_mgliter - self.target_hardness_mgliter
            )
        self.h_static_m = parameters[TPN['static_height_of_pellet_bed']]
        self.porosity_static = parameters[TPN['pellet_porosity_static']]
        self.porosity_expanded = parameters[TPN['pellet_porosity_expanded']]
        self.rho_pellet = parameters[TPN['mass_density_of_pellets']] * 1000  # kg/m3
        self.rho_lime_kgm3 = parameters[TPN['mass_density_of_chemical']]* 1000  # g/cm3
        self.rho_water = DENS_WATER_KG_PER_M3  # assumption, kg/m3
        self.power_efficiency_pumps = parameters[
            TPN['power_efficiency_of_pumps']]
        self.chemical_purity_factor = parameters[
            TPN['lime_dosage_mass_fraction']]  # kg lime or caustic soda/kg CaCO3
        self.storage_days_chemicals = parameters[TPN['storage_time_of_chemicals_days']]
        
        (
            self.unit_diam_m,
            self.unit_depth_m,
            self.unit_area_m2
            ) = reactor_dimensions(
                flow_per_unit_m3hr=self.flow_per_unit_m3hr,
                upflow_velocity_target_mphr=self.target_upflow_velocity_mperh,
                h_static_m=self.h_static_m,
                porosity_static=self.porosity_static,
                porosity_expanded=self.porosity_expanded
                )
        (
            self.hardness_removed_kg,
            self.lime_req_kgperday,
            self.seed_req_kg,
            self.pellets_out_kg
            ) = daily_mass_balance__kg(
                nominal_flow_m3perh=self.nominal_flow_m3perh,
                delta_c=self.delta_c,
                chemical_mass_fraction=self.chemical_purity_factor)
        for tech_property in self.digest_parameter_list:
            if tech_property == 'area':
                self.area_m2 = self.footprint_area__m2
                self.parameters[tech_property] = self.area_m2  # overwrite area

    def __repr__(self):
        return f"Pellet Softening unit diameter (m)={self.unit_diam_m}, " \
                f"unit depth (m)={self.unit_depth_m}, " \
                f"lime required (kg/day)={self.lime_req_kgperday}, " \
                f"pellets produced (kg/day)={self.pellets_out_kg}"

    def get_kpi(self, kpi: str) -> float:
        """Get the value for a KPI"""
        function_name = TECH_KPI_MAPPINGS.get(kpi, None)
        if function_name is not None:
            return getattr(self, function_name)
        else:
            raise ValueError(
                f"KPI '{kpi}' not implemented for {self.__class__.__name__}.")

    def get_kpi_dict(self, kpi_list=None):
        if kpi_list:
            return {kpi: self.get_kpi(kpi=kpi) for kpi in kpi_list}
        return {kpi: self.get_kpi(kpi=kpi) for kpi in TECH_KPI_MAPPINGS.keys()}

    @property
    def daily_mass_of_chemicals__kg(self) -> dict[str, float]:
        """Calculates chemicals in and pellets out per day."""
        return self._single_chemical_value(self.lime_req_kgperday)

    @property
    def footprint_area_for_chemicals__m2(self) -> float:
        lime_depth_m = 2.5
        lime_vol = (
            self.lime_req_kgperday * self.storage_days_chemicals
            ) / self.rho_lime_kgm3
        lime_area = lime_vol / lime_depth_m
        pellet_depth_m = 2.5
        pellet_vol = self.pellets_out_kg * self.storage_days_chemicals / self.rho_pellet
        pellet_area = pellet_vol / pellet_depth_m
        return lime_area + pellet_area

    @property
    def chemical_solution_concentration__mg_per_l(self) -> float:
        lime_mgperl = 1000 * self.lime_req_kgperday / (
            self.nominal_flow_m3perh * 24)
        return lime_mgperl

    @property
    def footprint_area__m2(self) -> float:
        """Total Area = Reactors + Chemicals area + 20% margin."""
        reactors_area = self.unit_area_m2 * self.lanes * self.units_per_lane
        return np.ceil(
            (reactors_area + self.footprint_area_for_chemicals__m2) * 1.2
            )

    @property
    def hydraulic_headloss__bar(self) -> float:
        hl_m = self.h_static_m * (1 - self.porosity_static) * (
            (self.rho_pellet - DENS_WATER_KG_PER_M3) / DENS_WATER_KG_PER_M3)
        total_lift = hl_m + self.unit_depth_m + 2.0 
        return meters_of_water_to_bar(total_lift)

    @property
    def power__kw(self) -> float:
        """Power based on overcoming bed headloss + lift height."""
        hl_m = self.h_static_m * (1 - self.porosity_static) * (
            (self.rho_pellet - DENS_WATER_KG_PER_M3) / DENS_WATER_KG_PER_M3)
        total_lift = hl_m + self.unit_depth_m + 2  # 2m friction margin
        power = (
            (self.nominal_flow_m3perh / 3600) * self.rho_water *
            GRAVITY_M_PER_S2 * total_lift) / (
                self.power_efficiency_pumps * 1000)
        return power


    @property
    def co2_emissions__kg_co2_eq_per_m3(self) -> float:
        if self.emission_factor_electricity is None:
            raise ValueError("Emission factor for electricity is not set.")
        co2_emissions = (
            self.daily_energy_consumption__kwh *
            self.emission_factor_electricity)
        masses = self.daily_mass_of_chemicals__kg
        emission_factors = self._resolve_per_chemical_factors(
            factor=self.chemical_emission_factor,
            default_value=float(self.chemical_emission_factor),
        )
        chemical_co2_emissions = sum(
            masses.get(chem_name, 0.0) * emission_factors.get(chem_name, 0.0)
            for chem_name in masses
        )
        return (co2_emissions + chemical_co2_emissions
                ) / self.nominal_flow_m3perh / 24


class CationIonExchange(TreatmentKPI):
    """KPI calculations for Ion Exchange Softening with Brine Regeneration."""
    tank_height_m: float
    unit_area_m2: float
    unit_diam_m: float
    lanes: int
    units_per_lane: int
    nominal_flow_m3perh: float
    total_hardness_in_mgliter: float
    target_hardness_mgliter: float
    delta_c_eq_m3: float
    resin_capacity_eqperliter: float
    cycle_h: float
    nacl_density: float
    storage_days: int
    power_efficiency_pumps: float
    salt_ratio: float

    def __post_init__(self):
        super().__post_init__()
        parameters = self.parameters
        plant_kpis = self.plant_kpis
        design_parameters = self.design_parameters
        wq_parameters = self.wq_parameters

        self.nominal_flow_m3perh = plant_kpis.get(
            NOMINAL_FLOW_RATE_NAME, None)
        self.lanes = design_parameters.get('number of lanes', None)
        self.flow_per_lane_m3perh = self.nominal_flow_m3perh / self.lanes
        self.units_per_lane = parameters[TPN['units_per_lane']]
        self.units_per_lane = self.units_per_lane + 1
        self.chemical_emission_factor = parameters[
            TPN['chemical_emission_factor']]
        self.emission_factor_electricity = design_parameters.get(
            EMISSION_FACTOR_ELEC_NAME, None) 
        self.cycle_h = parameters[TPN['regeneration_duration']]
        self.tank_height_m = parameters[TPN['tank_height']]
        self.storage_days = parameters[TPN['storage_time_of_chemicals_days']]
        self.total_hardness_in_mgliter = wq_parameters['total hardness'][
            INPUT_WQPARAMETER_KEY]
        self.target_hardness_mgliter = wq_parameters['total hardness'][
            TARGET_WQPARAMETER_KEY]
        self.power_efficiency_pumps = parameters[
            TPN['power_efficiency_of_pumps']]/100
        # One vessel per lane unavailable during regeneration
        self.flow_per_unit_m3hr = self.nominal_flow_m3perh / (
            self.lanes * (self.units_per_lane - 1))
        self.delta_c_eq_m3 = (self.total_hardness_in_mgliter - self.target_hardness_mgliter) / 50.0 # equivalent weight of Calcium Carbonate/m3
        self.resin_capacity_eqperliter = 1.4  # eq/L of resin
        self.salt_ratio = 0.12  # kg NaCl per eq removed (avg range 0.16-0.24)
        self.nacl_density = parameters[TPN['mass_density_of_chemical']] * 1000  # kg/m3
        self.daily_removal_eq = self.delta_c_eq_m3 * self.nominal_flow_m3perh * 24

    def __repr__(self):
        return f"Ion Exchange bed height (m)={self.tank_height_m }, " \
                f"delta C (eq/m3)={self.delta_c_eq_m3}, " \
                f"cycle time (h)={self.cycle_h}, " \
                f"resin capacity (eq/L)={self.resin_capacity_eqperliter}."

    def get_kpi(self, kpi: str) -> float:
        """Get the value for a KPI"""
        function_name = TECH_KPI_MAPPINGS.get(kpi, None)
        if function_name is not None:
            return getattr(self, function_name)
        else:
            raise ValueError(
                f"KPI '{kpi}' not implemented for {self.__class__.__name__}.")

    def get_kpi_dict(self, kpi_list=None):
        if kpi_list:
            return {kpi: self.get_kpi(kpi=kpi) for kpi in kpi_list}
        return {kpi: self.get_kpi(kpi=kpi) for kpi in TECH_KPI_MAPPINGS.keys()}

    @property
    def daily_mass_of_chemicals__kg(self) -> dict[str, float]:
        """Calculates chemicals in """
        """Total salt consumed by the whole plant per day."""
        return self._single_chemical_value(self.daily_removal_eq * self.salt_ratio)

    @property
    def footprint_area_for_chemicals__m2(self) -> float:
        """Required area for salt storage."""
        daily_mass_kg = self.sum_per_chemical(self.daily_mass_of_chemicals__kg)
        salt_vol = daily_mass_kg * self.storage_days / self.nacl_density 
        area_salt = salt_vol / 2.5 # 2.5m stacking height
        return area_salt

    @property
    def chemical_solution_concentration__mg_per_l(self) -> float:
        nacl_mgperl = 1000 * self.sum_per_chemical(
            self.daily_mass_of_chemicals__kg
        ) / (
            self.nominal_flow_m3perh * 24)
        return nacl_mgperl

    @property
    def footprint_area__m2(self) -> float:
        eq_per_cycle = self.delta_c_eq_m3 * self.flow_per_unit_m3hr * self.cycle_h
        resin_volume_unit__m3 = (eq_per_cycle / self.resin_capacity_eqperliter) / 1000.0 * 1.1 
        a_unit = resin_volume_unit__m3 / self.tank_height_m
        area_tanks_m2 = a_unit * self.lanes * self.units_per_lane
        
        bv_waste_factor = 4.5  # 4.5 bed volumes of waste produced per regeneration cycle 
        single_unit_waste_vol_m3 = resin_volume_unit__m3 * bv_waste_factor
        regens_per_vessel_day = 24.0 / self.cycle_h
        total_vessels = self.lanes * self.units_per_lane
        total_plant_regens_per_day = regens_per_vessel_day * total_vessels
        regens_in_8_hours = total_plant_regens_per_day * (8.0 / 24.0)
        waste_storage_vol = single_unit_waste_vol_m3 * regens_in_8_hours
        area_waste_tank = waste_storage_vol / 3.0
        net_calculated_area = area_tanks_m2 + self.footprint_area_for_chemicals__m2 + area_waste_tank
        return np.ceil(net_calculated_area * 1.25)

    @property
    def hydraulic_headloss__bar(self) -> float:
        eq_per_cycle = self.delta_c_eq_m3 * self.flow_per_unit_m3hr * self.cycle_h
        resin_volume_unit__m3 = (eq_per_cycle / self.resin_capacity_eqperliter) / 1000.0 * 1.1 
        a_unit = resin_volume_unit__m3/ self.tank_height_m
        unit_surface_rate=self.flow_per_unit_m3hr/ a_unit
        unit_surface_rate_mps = unit_surface_rate / 3600
        # TODO: resin_porosity and bead_diameter should be fetched from the database
        resin_porosity = 0.4
        bead_diameter = 0.0007  # 0.7mm bead diameter
        term_laminar = 150 * (WATER_VISCOSITY_N_S_PER_M2 * (1 - resin_porosity)**2) / (bead_diameter**2 * resin_porosity**3) * unit_surface_rate_mps     
        term_turbulent = 1.75 * (DENS_WATER_KG_PER_M3 * (1 - resin_porosity)) / (bead_diameter * resin_porosity**3) * unit_surface_rate_mps**2   
        pressure_drop_pa = (term_laminar + term_turbulent) * self.tank_height_m
        headloss_bar = pressure_drop_pa / 100000
        tank_height_bar = (self.tank_height_m + 1.5) / 10.197
        headloss_bar += tank_height_bar
        return headloss_bar 

    @property
    def power__kw(self) -> float:
        eff = self.power_efficiency_pumps
        headloss_m=self.hydraulic_headloss__bar * METER_PER_BAR
        power_service_kW=(self.nominal_flow_m3perh / 3600 * DENS_WATER_KG_PER_M3 * GRAVITY_M_PER_S2 * headloss_m) / (eff * 1000)

        eq_per_cycle = self.delta_c_eq_m3 * self.flow_per_unit_m3hr * self.cycle_h
        resin_volume_unit__m3 = (eq_per_cycle / self.resin_capacity_eqperliter) / 1000.0 * 1.1 
        a_unit = resin_volume_unit__m3 / self.tank_height_m
        unit_backflow_rate= 2 * self.flow_per_unit_m3hr # 2 times the normal flow
        h_backwash_m = 1.5 * headloss_m
        total_vessels = self.lanes * self.units_per_lane
        backwash_hydraulic_power_kW = (
        unit_backflow_rate / 3600 * DENS_WATER_KG_PER_M3 * GRAVITY_M_PER_S2 * h_backwash_m
        ) / (eff * 1000)
    # 15 minutes backwashing per regeneration, averaged over the day across all vessels
        power_backwash_kW = (
            backwash_hydraulic_power_kW * 0.25 * (24 / self.cycle_h) * total_vessels
        ) / 24 
        power_kW = power_service_kW + power_backwash_kW
        return power_kW


    @property
    def co2_emissions__kg_co2_eq_per_m3(self) -> float:
        if self.emission_factor_electricity is None:
            raise ValueError("Emission factor for electricity is not set.")
        co2_emissions = (
            self.daily_energy_consumption__kwh *
            self.emission_factor_electricity)
        masses = self.daily_mass_of_chemicals__kg
        emission_factors = self._resolve_per_chemical_factors(
            factor=self.chemical_emission_factor,
            default_value=float(self.chemical_emission_factor),
        )
        chemical_co2_emissions = sum(
            masses.get(chem_name, 0.0) * emission_factors.get(chem_name, 0.0)
            for chem_name in masses
        )
        return (co2_emissions + chemical_co2_emissions
                ) / self.nominal_flow_m3perh / 24


class AnionicIEX(TreatmentKPI):
    """KPI calculations for Anion Ion Exchange for NOM/DOC removal with Brine Regeneration."""
    lanes: int
    units_per_lane: int
    nominal_flow_m3perh: float
    doc_in_mgl: float
    doc_target_mgl: float
    delta_doc_eq_m3: float
    resin_doc_capacity_g_per_l: float
    nacl_density: float
    storage_days: int
    cycle_h: float
    resin_cap: float
    bed_height_m: float
    unit_area_m2: float
    unit_diam_m: float
    ebct_min: float
    chemical_emission_factor: float
    emission_factor_electricity: float
    power_efficiency_pumps: float

    def __post_init__(self):
        super().__post_init__()
        parameters = self.parameters
        plant_kpis = self.plant_kpis
        design_parameters = self.design_parameters
        wq_parameters = self.wq_parameters

        self.lanes = design_parameters.get('number of lanes', None)
        self.units_per_lane = parameters[TPN['units_per_lane']]
        self.units_per_lane = self.units_per_lane + 1
        self.nominal_flow_m3perh = plant_kpis.get(
            NOMINAL_FLOW_RATE_NAME, None)  # noqa: E501
        self.chemical_emission_factor = parameters[
            TPN['chemical_emission_factor']]
        self.emission_factor_electricity = design_parameters.get(
            EMISSION_FACTOR_ELEC_NAME, None) 
        self.flow_per_lane_m3perh = calculate_flow_per_lane(
            self.lanes, self.nominal_flow_m3perh)
        self.flow_per_unit_m3hr = self.nominal_flow_m3perh / (
            self.lanes * (self.units_per_lane - 1))
        self.doc_in_mgl = wq_parameters[
            'dissolved organic carbon'][INPUT_WQPARAMETER_KEY]  # mgl/l
        self.doc_target_mgl = wq_parameters[
            'dissolved organic carbon'][TARGET_WQPARAMETER_KEY]  # mgl/l        
        self.delta_doc_gm3 = max(0.0, self.doc_in_mgl - self.doc_target_mgl)
        self.cycle_h = parameters[TPN['regeneration_duration']]
        self.ebct_min = parameters[TPN['empty_bed_contact_time']]  # 4 min.
        self.resin_doc_capacity_g_per_l = self.parameters[
            TPN['resin_volume_exchange']]  # 18 eq/l
        self.power_efficiency_pumps = parameters[
            TPN['power_efficiency_of_pumps']]/100
        self.nacl_density = parameters[
            TPN['mass_density_of_chemical']] * 1000 # kg/m3
        self.nacl_dose_per_m3_resin = 150.0  # kg per m3 of water
        self.bed_height_m = self.parameters[TPN['bed_height']]
        self.unit_area_m2 = 1.1 * (
            self.flow_per_unit_m3hr * self.ebct_min) / 60.0 / self.bed_height_m
        self.storage_days = self.parameters[
            TPN['storage_time_of_chemicals_days']]

    def __repr__(self):
        return f"Anion IEX bed height (m)={self.bed_height_m}, " \
            f"delta DOC (mg/L)={self.delta_doc_gm3}, " \
            f"EBCT (min)={self.ebct_min}, " \
            f"resin DOC capacity (g/L)={self.resin_doc_capacity_g_per_l}."

    def get_kpi(self, kpi: str) -> float:
        """Get the value for a KPI"""
        function_name = TECH_KPI_MAPPINGS.get(kpi, None)
        if function_name is not None:
            return getattr(self, function_name)
        else:
            raise ValueError(
                f"KPI '{kpi}' not implemented for {self.__class__.__name__}.")

    def get_kpi_dict(self, kpi_list=None):
        if kpi_list:
            return {kpi: self.get_kpi(kpi=kpi) for kpi in kpi_list}
        return {kpi: self.get_kpi(kpi=kpi) for kpi in TECH_KPI_MAPPINGS.keys()}

    @property
    def daily_mass_of_chemicals__kg(self) -> dict[str, float]:
        """Total salt (NaCl) consumed per day based on resin volume regenerated."""
        daily_doc_load_g = self.delta_doc_gm3 * self.nominal_flow_m3perh * 24.0        
        resin_exhausted_l_day = daily_doc_load_g / self.resin_doc_capacity_g_per_l

        resin_m3_day = resin_exhausted_l_day / 1000.0
        return self._single_chemical_value(
            resin_m3_day * self.nacl_dose_per_m3_resin
        )

    @property
    def footprint_area_for_chemicals__m2(self) -> float:
        """Required area for salt storage."""
        salt_vol = (
            self.sum_per_chemical(self.daily_mass_of_chemicals__kg)
            * self.storage_days
        ) / self.nacl_density
        area_salt = salt_vol / 2.0  # 2.0m stacking height safety factor
        return area_salt

    @property
    def chemical_solution_concentration__mg_per_l(self) -> float:
        nacl_mgperl = 1000 * self.sum_per_chemical(
            self.daily_mass_of_chemicals__kg
        ) / (
            self.nominal_flow_m3perh * 24)
        return nacl_mgperl

    @property
    def footprint_area__m2(self) -> float:
        """Total area including vessels, chemical storage, and waste tanks."""
        # unit_area_m2 = self.flow_per_unit_m3hr / self.surface_overflow_rate  # TODO: please check!!!
        # unit_area_m2 = self.unit_area_m2 * self.lanes * self.units_per_lane
        total_vessels_area = self.unit_area_m2 * self.lanes * self.units_per_lane
        v_resin_total = (self.unit_area_m2 * self.lanes * self.units_per_lane * self.bed_height_m)
        regens_per_day = 24 / self.cycle_h
        bv_waste_factor = 4.0  # Brine + slow rinse volumes
        waste_storage_vol = (v_resin_total * regens_per_day *
                             bv_waste_factor) * (12 / 24)  # 12h buffer
        area_waste_tank = waste_storage_vol / 3.0
        raw_footprint = total_vessels_area + self.footprint_area_for_chemicals__m2 + area_waste_tank
        return float(np.ceil(raw_footprint * 1.20)) # 20% spacing factor for maintenance # 20% spacing factor for maintenance

    @property
    def hydraulic_headloss__bar(self) -> float:
        """Calculates pressure drop using the Ergun Equation + Internal Losses."""
        unit_surface_rate = self.flow_per_unit_m3hr / self.unit_area_m2
        unit_surface_rate_mps = unit_surface_rate / 3600
        resin_porosity = 0.4
        bead_diameter = 0.0007 # 0.7mm bead diameter
        term_laminar = 150 * (WATER_VISCOSITY_N_S_PER_M2 * (1 - resin_porosity)**2) / (bead_diameter**2 * resin_porosity**3) * unit_surface_rate_mps     
        term_turbulent = 1.75 * (DENS_WATER_KG_PER_M3 * (1 - resin_porosity)) / (bead_diameter * resin_porosity**3) * unit_surface_rate_mps**2   
        pressure_drop_pa = (term_laminar + term_turbulent) * self.bed_height_m
        headloss_bar = pressure_drop_pa / 1e5 
        tank_height_bar = (self.bed_height_m + 1.5) /10.197
        headloss_bar += tank_height_bar
        return headloss_bar

    @property
    def power__kw(self) -> float:
        """Total power for service pumps and regeneration pumps."""
        eff = self.power_efficiency_pumps
        head_m = self.hydraulic_headloss__bar * 10.197 # Bar to meters
        p_service = (self.nominal_flow_m3perh / 3600 * 1000 * 9.81 * head_m) / (eff * 1000)
        unit_backflow_rate= 2* self.flow_per_unit_m3hr # 2 times the normal flow
        h_backwash_m = 1.5 * head_m
        total_vessels = self.lanes * self.units_per_lane
        backwash_hydraulic_power_kW = (
            unit_backflow_rate / 3600 * DENS_WATER_KG_PER_M3 * GRAVITY_M_PER_S2 * h_backwash_m
        ) / (eff * 1000)
        power_backwash_kW = (
            backwash_hydraulic_power_kW * 0.25 * (24 / self.cycle_h) * total_vessels
        ) / 24
        return p_service + power_backwash_kW

    
    @property
    def co2_emissions__kg_co2_eq_per_m3(self) -> float:
        if self.emission_factor_electricity is None:
            raise ValueError("Emission factor for electricity is not set.")
        co2_emissions = (
            self.daily_energy_consumption__kwh *
            self.emission_factor_electricity)
        masses = self.daily_mass_of_chemicals__kg
        emission_factors = self._resolve_per_chemical_factors(
            factor=self.chemical_emission_factor,
            default_value=float(self.chemical_emission_factor),
        )
        chemical_co2_emissions = sum(
            masses.get(chem_name, 0.0) * emission_factors.get(chem_name, 0.0)
            for chem_name in masses
        )
        return (co2_emissions + chemical_co2_emissions
                ) / self.nominal_flow_m3perh / 24


class AirFlotationDAF(TreatmentKPI):
    """KPI calculations for Dissolved Air Flotation (DAF)."""
    surface_overflow_rate: float
    air_solids_ratio: float
    recirculation_ratio: float
    air_density: float
    nominal_flow_m3perh: float
    retention_time_min: float
    pressure_difference_kpa: float
    bubble_diameter_m: float
    powereff_compressor: float
    tss_in_mgl: float
    unit_area_m2: float
    emission_factor_electricity: float
    area_m2: float

    def __post_init__(self):
        super().__post_init__()
        parameters = self.parameters
        plant_kpis = self.plant_kpis
        design_parameters = self.design_parameters
        wq_parameters = self.wq_parameters
        
        self.lanes = design_parameters.get('number of lanes', None)
        self.units_per_lane = parameters[TPN['units_per_lane']]
        self.emission_factor_electricity = design_parameters.get(EMISSION_FACTOR_ELEC_NAME, None)
        self.nominal_flow_m3perh = plant_kpis.get(
            NOMINAL_FLOW_RATE_NAME, None)
        self.flow_per_lane = self.nominal_flow_m3perh / self.lanes
        self.surface_overflow_rate = parameters[TPN['surface_overflow_rate']]  # m3/m2/h
        self.air_solids_ratio = parameters[TPN['air_solids_ratio']] # kg air/kg solids
        self.recirculation_ratio = parameters[TPN['recirculation_ratio']]
        self.air_density = parameters[TPN['mass_density_of_air']]  # kg/m3
        self.retention_time_min = parameters [TPN['retention_time_min']]  # minutes_min = parameters.get(TPN['retention_time'], 120.0)  # minutes       
        self.pressure_difference_kpa = parameters.get(
            TPN.get('air_pressure_difference'), 
            parameters.get('air_pressure_difference', 600.0)
        )    
        self.tss_in_mgl = wq_parameters[
            'total suspended solids'][INPUT_WQPARAMETER_KEY]  # 150 mgl/l
        self.tss_out_mgl = wq_parameters[
            'total suspended solids'][TARGET_WQPARAMETER_KEY]  # 50 mgl/l
        self.powereff_compressor = parameters[TPN['power_efficiency']]/100
        self.min_depth_m = parameters [TPN['tank_height']]  # m
        self.unit_area_m2 = (self.flow_per_lane / self.units_per_lane
                             ) / self.surface_overflow_rate
        self.unit_volume_m3 = (
            (self.flow_per_lane / self.units_per_lane) * (self.retention_time_min / 60.0))

        self.unit_depth_m = max(
            self.min_depth_m, self.unit_volume_m3 / self.unit_area_m2)
        self.unit_width_m = self.unit_depth_m / 0.8
        self.unit_length_m = self.unit_area_m2 / self.unit_width_m
        for tech_property in self.digest_parameter_list:
            if tech_property == 'area':
                self.area_m2 = self.footprint_area__m2
                self.parameters[tech_property] = self.area_m2  # overwrite area

    def __repr__(self):
        return f"DAF surface overflow rate (m3/m2/h)={self.surface_overflow_rate}, " \
                f"air to solids ratio (kg/kg)={self.air_solids_ratio}, " \
                f"recirculation ratio={self.recirculation_ratio}, " \
                f"retention time (min)={self.retention_time_min}, " \
                f"pressure difference (kPa)={self.pressure_difference_kpa}."

    def get_kpi(self, kpi: str) -> float:
        """Get the value for a KPI"""
        function_name = TECH_KPI_MAPPINGS.get(kpi, None)
        if function_name is not None:
            return getattr(self, function_name)
        else:
            raise ValueError(
                f"KPI '{kpi}' not implemented for {self.__class__.__name__}.")

    def get_kpi_dict(self, kpi_list=None):
        if kpi_list:
            return {kpi: self.get_kpi(kpi=kpi) for kpi in kpi_list}
        return {kpi: self.get_kpi(kpi=kpi) for kpi in TECH_KPI_MAPPINGS.keys()}

    @property
    def daily_mass_of_chemicals__kg(self) -> dict[str, float]:
        return {}  # No chemicals used in DAF

    @property
    def footprint_area__m2(self) -> float:
        """Total area for DAF tanks + recirculation units."""
        daf_area = self.unit_area_m2 * self.lanes * self.units_per_lane
        area_recirc = (
            self.recirculation_ratio * self.flow_per_lane * self.lanes
            ) * 0.1 / 2.0
        return np.ceil((daf_area + area_recirc) * 1.25)  # 25% spacing

    def air_mass__kg(self) -> float:
        """Calculates total air required in kg/day."""
        air_required_unit = (
            self.air_solids_ratio * self.tss_in_mgl * (
                self.flow_per_lane / self.units_per_lane) * 24.0) / 1000.0
        self.unit_depth_m
        return air_required_unit * self.lanes * self.units_per_lane

    @property
    def chemical_solution_concentration__mg_per_l(self) -> float:
        return 0.0  # No chemicals used

    @property
    def footprint_area_for_chemicals__m2(self):
        return 0.0  # No chemicals used in DAF

    @property
    def hydraulic_headloss__bar(self) -> float:
        """Headloss calculation assumptions"""
        headlosses = self.unit_depth_m + self.unit_depth_m * 0.1  # assuming 0.1m per unit depth
        return meters_of_water_to_bar(headlosses) 

    @property
    def power__kw(self) -> float:
        """Calculates power for compressor and recirculation pumps."""
        air_req_sec = self.air_mass__kg() / 86400.0
        p_compressor = (
            air_req_sec *
            self.pressure_difference_kpa) / self.powereff_compressor
        q_recirc = (self.recirculation_ratio * self.nominal_flow_m3perh) / 3600.0
        p_recirculation = (q_recirc * self.pressure_difference_kpa) / 0.75  # 0.75 assumed pump eff

        return p_compressor + p_recirculation


    @property
    def co2_emissions__kg_co2_eq_per_m3(self) -> float:
        if self.emission_factor_electricity is None:
            raise ValueError("Emission factor for electricity is not set.")
        co2_emissions = (
            self.daily_energy_consumption__kwh *
            self.emission_factor_electricity)
        specific_co2_emissions = co2_emissions / self.nominal_flow_m3perh / 24  # kg CO2 eq per m3
        return specific_co2_emissions  


class SludgeBlanketClarifier(TreatmentKPI):
    """KPI calculations for Sludge Blanket Clarifier."""
    surface_overflow_rate: float
    lanes: int
    units_per_lane: int
    nominal_flow_m3perh: float
    flow_per_lane: float
    nominal_flow_m3perh: float
    flow_per_unit: float
    retention_time_h: float
    unit_depth_input_m: float
    sludge_tank_height_m: float
    tss_in_mgl: float
    tss_out_mgl: float
    sludge_density_kg_m3: float
    power_density_wperm3: float
    tank_height_m: float
    emission_factor_electricity: float
    backwash_filtration_rate: float
    backwash_duration_min: float
    backwash_tank_height_m: float
    scraper_power_coeff_kw_m2: float
    power_efficiency_pumps: float
    area_m2: float

    def __post_init__(self):
        super().__post_init__()
        parameters = self.parameters
        plant_kpis = self.plant_kpis
        design_parameters = self.design_parameters
        wq_parameters = self.wq_parameters
        self.lanes = design_parameters.get('number of lanes', None)
        self.units_per_lane = parameters[TPN['units_per_lane']]
        self.emission_factor_electricity = design_parameters.get(
            EMISSION_FACTOR_ELEC_NAME, None)
        self.nominal_flow_m3perh = plant_kpis.get(NOMINAL_FLOW_RATE_NAME, None)
        self.flow_per_lane = self.nominal_flow_m3perh / self.lanes
        self.flow_per_unit = self.flow_per_lane / self.units_per_lane
        self.surface_overflow_rate = parameters[
            TPN['surface_overflow_rate']]  # m3/m2/h
        self.backwash_filtration_rate = parameters[
            TPN['backwash_filtration_rate']]  # m/h
        self.backwash_duration_min = parameters[
            TPN['backwash_duration']]
        self.retention_time_min = parameters[TPN['retention_time_min']]
        self.tank_height_m = parameters[TPN['tank_height']]
        self.backwash_tank_height_m = parameters[TPN['backwash_tank_height']]
        self.sludge_tank_height_m = parameters[TPN['tank_height']]  # m
        self.scraper_power_coeff_kw_m2 = parameters[
            TPN['scraper_power_coefficient']]
        self.power_efficiency_pumps = parameters[
            TPN['power_efficiency_of_pumps']] / 100
        self.tss_in_mgl = wq_parameters[
            'total suspended solids'][INPUT_WQPARAMETER_KEY]  # mgl/l
        self.tss_out_mgl = wq_parameters[
            'total suspended solids'][TARGET_WQPARAMETER_KEY]  # mgl/l
        self.sludge_density_kg_m3 = parameters[
            TPN['mass_density_of_tss']] * 1000  # 30 g/cm3 (not user specified)
        self.power_density_wperm3 = parameters[
            TPN['power_density']]  # W/m3
        self.unit_area_m2 = self.flow_per_unit / self.surface_overflow_rate       
        self.unit_volume_m3 = self.flow_per_unit * (self.retention_time_min/60)
        self.tank_height_m = max(self.tank_height_m, self.unit_volume_m3 / self.unit_area_m2)
        self.tanks_area_m2 = self.unit_area_m2 * self.units_per_lane * self.lanes 
        for tech_property in self.digest_parameter_list:
            if tech_property == 'area':
                self.area_m2 = self.tanks_area_m2
                self.parameters[tech_property] = self.area_m2  # overwrite area

    def __repr__(self):
        return f"Sludge Blanket Clarifier surface overflow rate (m3/m2/h)={self.surface_overflow_rate}, " \
            f"TSS in (mg/L)={self.tss_in_mgl}, " \
            f"TSS out (mg/L)={self.tss_out_mgl}, " \
            f"sludge density (kg/m3)={self.sludge_density_kg_m3}"

    def get_kpi(self, kpi: str) -> float:
        """Get the value for a KPI"""
        function_name = TECH_KPI_MAPPINGS.get(kpi, None)
        if function_name is not None:
            return getattr(self, function_name)
        else:
            raise ValueError(
                f"KPI '{kpi}' not implemented for {self.__class__.__name__}.")

    def get_kpi_dict(self, kpi_list=None):
        if kpi_list:
            return {kpi: self.get_kpi(kpi=kpi) for kpi in kpi_list}
        return {kpi: self.get_kpi(kpi=kpi) for kpi in TECH_KPI_MAPPINGS.keys()}

    @property
    def chemical_solution_concentration__mg_per_l(self) -> float:
        return 0.0  # No chemicals used

    @property
    def daily_mass_of_chemicals__kg(self) -> dict[str, float]:
        return {}  # No chemicals used in Sludge clarifiers 
    
    @property
    def sludge_production_kg(self) -> float:
        """Calculates sludge production (waste solids) in kg/day."""
        sludge_production_kgh = self.nominal_flow_m3perh * (
            self.tss_in_mgl - self.tss_out_mgl) / 1000.0
        return sludge_production_kgh * 24.0

    @property
    def footprint_area__m2(self) -> float:
        """Total Area = Clarifier Area + Sludge Thickening Area."""
        daily_sludge_vol = (
            self.sludge_production_kg / self.sludge_density_kg_m3)
        sludge_area_m2 = daily_sludge_vol / self.sludge_tank_height_m
        backwash_flow = self.unit_area_m2 / self.backwash_filtration_rate
        backwash_volume_m3 = backwash_flow / (
            self.backwash_duration_min / 60)
        backwash_area_m2 = (
            backwash_volume_m3 / self.backwash_tank_height_m  # monthly backwash
        )
        return 1.2 * (
            self.tanks_area_m2 + sludge_area_m2 + backwash_area_m2)
    
    @property
    def footprint_area_for_chemicals__m2(self):
        return 0.0  # No chemicals used in Sludge Blanket Clarifier

    @property
    def hydraulic_headloss__bar(self) -> float: 
        return meters_of_water_to_bar(1.1 * (self.tank_height_m + 0.01 * self.unit_area_m2))

    @property
    def power__kw(self) -> float:
        """Power for sludge scrapers/pumps based on sludge production."""     
        scraper_unit_kW = self.scraper_power_coeff_kw_m2 * self.unit_area_m2
        backwash_flow = self.unit_area_m2 / self.backwash_filtration_rate
        head = 10  # assuming 10 meters of pressure head
        backwash_pump_kw = (
            DENS_WATER_KG_PER_M3 * backwash_flow *
            GRAVITY_M_PER_S2 * head) /(
                3600 * self.power_efficiency_pumps * 1000)
        return (
            scraper_unit_kW * self.lanes *
            self.units_per_lane) + backwash_pump_kw


    @property
    def daily_energy_consumption__kwh(self) -> float:
        """Apply a reduced duty-cycle factor to daily energy use."""
        daily_kWh = 0.03  # Scraper and backwash pumps run monthly.
        return self.power__kw * 24.0 * daily_kWh

    @property
    def co2_emissions__kg_co2_eq_per_m3(self) -> float:
        if self.emission_factor_electricity is None:
            raise ValueError("Emission factor for electricity is not set.")
        co2_emissions = (
            self.daily_energy_consumption__kwh *
            self.emission_factor_electricity)
        specific_co2_emissions = co2_emissions / self.nominal_flow_m3perh / 24  # kg CO2 eq per m3
        return specific_co2_emissions


class UVdisinfection(TreatmentKPI):
    """KPI calculations for a UV for Disinfection."""
    tank_height_m: float
    uv_dose_mjpercm2: float
    lanes: int
    units_per_lane: int
    nominal_flow_m3perh: float
    flow_per_lane_m3perh: float
    energy_per_m3_kwh: float
    exposure_time_sec: float
    unit_volume_m3: float
    power_per_m3_kW: float
    emission_factor_electricity: float

    def __post_init__(self):
        super().__post_init__()
        parameters = self.parameters
        plant_kpis = self.plant_kpis
        design_parameters = self.design_parameters
        # wq_parameters = self.wq_parameters
        
        self.lanes = design_parameters.get('number of lanes', None)
        self.units_per_lane = parameters[TPN['units_per_lane']]
        self.units_per_lane = self.units_per_lane + 1
        self.emission_factor_electricity = design_parameters.get(EMISSION_FACTOR_ELEC_NAME, None)
        self.nominal_flow_m3perh = plant_kpis.get(
            NOMINAL_FLOW_RATE_NAME, None)
        self.flow_per_lane_m3perh = calculate_flow_per_lane(
            self.lanes, self.nominal_flow_m3perh)
        self.flow_per_unit_m3perh = self.flow_per_lane_m3perh / (self.units_per_lane - 1)
        self.uv_dose_mjpercm2 = parameters[TPN['uv_dose']]  # 40 mJ/cm2
        self.average_intensity_mWpercm2 = parameters[
            TPN['uv_power_intensity']]  # 10 mW/cm2
        self.tank_height_m = parameters[TPN['tank_height']]  # 0.15 m  
        self.power_per_m3_kW = parameters[TPN['power_per_m3']]  # 0.040 kW/m3            
        self.exposure_time_sec = (
            self.uv_dose_mjpercm2 /
            self.average_intensity_mWpercm2)
        self.unit_volume_m3 = (self.flow_per_unit_m3perh / 3600) *  self.exposure_time_sec / 0.8 # hydraulic efficiency

    def __repr__(self):
        return f"UV tank height (m)={self.tank_height_m}, " \
               f"Power required per m3 of water (kW/m3)={self.power_per_m3_kW}, " \
               f"UV dose for disinfection (mJ/cm2)={self.uv_dose_mjpercm2}."

    def get_kpi(self, kpi: str) -> float:
        """Get the value for a KPI"""
        function_name = TECH_KPI_MAPPINGS.get(kpi, None)
        if function_name is not None:
            return getattr(self, function_name)
        else:
            raise ValueError(
                f"KPI '{kpi}' not implemented for {self.__class__.__name__}.")

    def get_kpi_dict(self, kpi_list=None):
        if kpi_list:
            return {kpi: self.get_kpi(kpi=kpi) for kpi in kpi_list}
        return {kpi: self.get_kpi(kpi=kpi) for kpi in TECH_KPI_MAPPINGS.keys()}

    @property
    def daily_mass_of_chemicals__kg(self) -> dict[str, float]:
        return {}

    @property
    def chemical_solution_concentration__mg_per_l(self) -> float:
        return 0.0

    @property
    def footprint_area_for_chemicals__m2(self) -> float:
        """Calculates area for H2O2 storage tanks including safety bunding."""
        return 0.0

    @property
    def footprint_area__m2(self) -> float:
        unit_area_m2 = self.unit_volume_m3 / self.tank_height_m
        uv_area_m2 = unit_area_m2 * self.units_per_lane * self.lanes 
        maintenance_factor = 1.3
        return np.ceil(maintenance_factor * uv_area_m2)

    @property
    def power__kw(self) -> float:
        uv_transmittance_percent = 90 # assuming UV transmittance of 90% 
        power_kW = self.power_per_m3_kW * self.nominal_flow_m3perh /(uv_transmittance_percent/100)
        return np.ceil(power_kW)

    @property
    def hydraulic_headloss__bar(self) -> float:
        return 0.1 + meters_of_water_to_bar(self.tank_height_m)

    @property
    def co2_emissions__kg_co2_eq_per_m3(self) -> float:
        if self.emission_factor_electricity is None:
            raise ValueError("Emission factor for electricity is not set.")
        co2_emissions = (
            self.daily_energy_consumption__kwh *
            self.emission_factor_electricity)
        specific_co2_emissions = co2_emissions / self.nominal_flow_m3perh / 24  # kg CO2 eq per m3
        return specific_co2_emissions


class LamellaClarifierSlope(TreatmentKPI):
    """KPI calculations for Lamella clarifier,slope plates."""
    surface_overflow_rate: float
    backwash_filtration_rate: float
    lanes: int
    units_per_lane: int
    nominal_flow_m3perh: float
    flow_per_lane: float
    nominal_flow_m3perh: float
    flow_per_unit: float
    plate_angle: float
    unit_depth_input_m: float
    tss_in_mgl: float
    tss_out_mgl: float
    mass_density_of_tss: float
    scraper_power_coeff_kw_m2: float
    sludge_tank_height_m: float
    backwash_tank_height_m: float
    backwash_filtration_rate: float
    backwash_duration_min: float
    power_efficiency_pump: float
    emission_factor_electricity: float
    area_m2: float

    def __post_init__(self):
        super().__post_init__()
        parameters = self.parameters
        plant_kpis = self.plant_kpis
        design_parameters = self.design_parameters
        wq_parameters = self.wq_parameters
        
        self.lanes = design_parameters.get('number of lanes', None)
        self.units_per_lane = parameters[TPN['units_per_lane']]
        self.emission_factor_electricity = design_parameters.get(
            EMISSION_FACTOR_ELEC_NAME, None)
        self.nominal_flow_m3perh = plant_kpis.get(NOMINAL_FLOW_RATE_NAME, None)
        self.flow_per_lane = self.nominal_flow_m3perh / self.lanes
        self.flow_per_unit = self.flow_per_lane / self.units_per_lane
        self.surface_overflow_rate = parameters[
            TPN['surface_overflow_rate']]  # m3/m2/h
        self.plate_angle = parameters[TPN['plate_angle']]
        self.sludge_tank_height_m = parameters[
            TPN['sludge_tank_height']]  # m
        self.scraper_power_coeff_kw_m2 = parameters[
            TPN['scraper_power_coefficient']]
        self.backwash_filtration_rate = parameters[
            TPN['backwash_filtration_rate']]
        self.backwash_duration_min = parameters[
            TPN['backwash_duration']]
        self.backwash_tank_height_m = parameters[
            TPN['backwash_tank_height']]
        self.tss_in_mgl = wq_parameters[
            'total suspended solids'][INPUT_WQPARAMETER_KEY]  # mgl/l
        self.tss_out_mgl = wq_parameters[
            'total suspended solids'][TARGET_WQPARAMETER_KEY]  # mgl/l
        self.sludge_density_kg_m3 = parameters[
            TPN['mass_density_of_tss']] * 1000  # 30 g/cm3 (not user specified)
        self.power_efficiency_pumps = parameters[
            TPN['power_efficiency_of_pumps']]
        for tech_property in self.digest_parameter_list:
            if tech_property == 'area':
                self.area_m2 = self.footprint_area__m2
                self.parameters[tech_property] = self.area_m2  # overwrite area
    
    def __repr__(self):
        return f"Lamella Slope Plate Clarifier surface overflow rate (m3/m2/h)={self.surface_overflow_rate}, " \
            f"TSS in (mg/L)={self.tss_in_mgl}, " \
            f"TSS out (mg/L)={self.tss_out_mgl}, " \
            f"sludge density (kg/m3)={self.sludge_density_kg_m3}"

    def get_kpi(self, kpi: str) -> float:
        """Get the value for a KPI"""
        function_name = TECH_KPI_MAPPINGS.get(kpi, None)
        if function_name is not None:
            return getattr(self, function_name)
        else:
            raise ValueError(
                f"KPI '{kpi}' not implemented for {self.__class__.__name__}.")

    def get_kpi_dict(self, kpi_list=None):
        if kpi_list:
            return {kpi: self.get_kpi(kpi=kpi) for kpi in kpi_list}
        return {kpi: self.get_kpi(kpi=kpi) for kpi in TECH_KPI_MAPPINGS.keys()}

    @property
    def chemical_solution_concentration__mg_per_l(self) -> float:
        return 0.0  # No chemicals used

    @property
    def daily_mass_of_chemicals__kg(self) -> dict[str, float]:
        return {}  # No chemicals used in Sludge clarifiers
    
    @property
    def sludge_production_kg(self) -> float:
        """Calculates sludge production (waste solids) in kg/day."""
        sludge_production_kgh = self.nominal_flow_m3perh * (
            self.tss_in_mgl - self.tss_out_mgl) / 1000.0
        return sludge_production_kgh * 24.0

    @property
    def footprint_area__m2(self) -> float:
        """Total Area = Clarifier Area + Sludge Thickening Area."""
        angle_coeff = 1.285 - 0.013 * self.plate_angle  # transform the angle to coefficient
        unit_area_m2 = 1.1 * (self.flow_per_unit / self.surface_overflow_rate) * angle_coeff
        clarifiers_area_total = unit_area_m2 * self.units_per_lane * self.lanes 
        daily_sludge_vol = self.sludge_production_kg / self.sludge_density_kg_m3
        sludge_area_m2 = daily_sludge_vol / self.sludge_tank_height_m
        backwash_flow = unit_area_m2 / self.backwash_filtration_rate
        backwash_volume_m3 = backwash_flow / (self.backwash_duration_min/60)
        backwash_area_m2 = 7 * backwash_volume_m3 / self.backwash_tank_height_m #assuming daily backwash and 7 days of backwash storage
        return 1.2 * (clarifiers_area_total + sludge_area_m2 + backwash_area_m2)  # 20% access factor
    
    @property
    def footprint_area_for_chemicals__m2(self):
        return 0.0  # No chemicals used in Sludge Blanket Clarifier

    @property
    def hydraulic_headloss__bar(self) -> float:
        mathfactor = 1.285 - 0.013 * self.plate_angle # transform the angle to calculation factor
        unit_area_m2 = 1.1 * (self.flow_per_unit / self.surface_overflow_rate) * mathfactor 
        tank_height_m = 1
        return meters_of_water_to_bar(1.1 * (tank_height_m + 0.001 * unit_area_m2))

    @property
    def power__kw(self) -> float:
        """Power for sludge scrapers/pumps based on sludge production."""
        mathfactor =  1.285 - 0.013 * self.plate_angle # transform the angle to calculation factor
        unit_area_m2 = 1.1 * (self.flow_per_unit / self.surface_overflow_rate) * mathfactor 
        scraper_unit_kW = self.scraper_power_coeff_kw_m2 * unit_area_m2 
        backwash_flow = unit_area_m2 / self.backwash_filtration_rate
        head = 8 # assuming 8 meters of pressure head
        backwash_pump_kw = DENS_WATER_KG_PER_M3 * backwash_flow * GRAVITY_M_PER_S2 * head /(3600 * self.power_efficiency_pumps * 1000)
        return (scraper_unit_kW * self.lanes * self.units_per_lane) + backwash_pump_kw

    @property
    def daily_energy_consumption__kwh(self) -> float:
        """Apply the configured duty-cycle factor to daily energy use."""
        daily_kWh = 1/7  # Scraper and backwash pumps run once per week.
        return self.power__kw * (self.backwash_duration_min/60) * daily_kWh

    @property
    def co2_emissions__kg_co2_eq_per_m3(self) -> float:
        if self.emission_factor_electricity is None:
            raise ValueError("Emission factor for electricity is not set.")
        co2_emissions = (
            self.daily_energy_consumption__kwh *
            self.emission_factor_electricity)
        specific_co2_emissions = co2_emissions / self.nominal_flow_m3perh / 24  # kg CO2 eq per m3
        return specific_co2_emissions


class LamellaClarifierHorizontal(TreatmentKPI):
    """KPI calculations for Lamella clarifier,horizontal plates."""
    surface_overflow_rate: float
    backwash_filtration_rate: float
    lanes: int
    units_per_lane: int
    nominal_flow_m3perh: float
    flow_per_lane: float
    nominal_flow_m3perh: float
    flow_per_unit: float
    unit_depth_input_m: float
    tss_in_mgl: float
    tss_out_mgl: float
    mass_density_of_tss: float
    scraper_power_coeff_kw_m2: float
    sludge_tank_height_m: float
    backwash_tank_height_m: float
    backwash_filtration_rate: float
    backwash_duration_min: float
    power_efficiency_pump: float
    emission_factor_electricity: float
    area_m2: float

    def __post_init__(self):
        super().__post_init__()
        parameters = self.parameters
        plant_kpis = self.plant_kpis
        design_parameters = self.design_parameters
        wq_parameters = self.wq_parameters
        
        self.lanes = design_parameters.get('number of lanes', None)
        self.units_per_lane = parameters[TPN['units_per_lane']]
        self.emission_factor_electricity = design_parameters.get(EMISSION_FACTOR_ELEC_NAME, None)
        self.nominal_flow_m3perh = plant_kpis.get(
            NOMINAL_FLOW_RATE_NAME, None)
        self.flow_per_lane = self.nominal_flow_m3perh / self.lanes
        self.flow_per_unit = self.flow_per_lane / self.units_per_lane
        self.surface_overflow_rate = parameters[
            TPN['surface_overflow_rate']]  # m3/m2/h
        self.sludge_tank_height_m = parameters[TPN['sludge_tank_height']] # m
        self.scraper_power_coeff_kw_m2 = parameters[
            TPN['scraper_power_coefficient']]
        self.backwash_filtration_rate = parameters [TPN['backwash_filtration_rate']]  
        self.backwash_duration_min = parameters [TPN['backwash_duration']] 
        self.backwash_tank_height_m = parameters [TPN['backwash_tank_height']]  
        self.tss_in_mgl = wq_parameters[
            'total suspended solids'][INPUT_WQPARAMETER_KEY]  # mgl/l
        self.tss_out_mgl = wq_parameters[
            'total suspended solids'][TARGET_WQPARAMETER_KEY]  # mgl/l
        self.sludge_density_kg_m3 = parameters[
            TPN['mass_density_of_tss']] * 1000  # 30 g/cm3 (not user specified)
        self.power_efficiency_pumps = parameters[
            TPN['power_efficiency_of_pumps']]
        for tech_property in self.digest_parameter_list:
            if tech_property == 'area':
                self.area_m2 = self.footprint_area__m2
                self.parameters[tech_property] = self.area_m2  # overwrite area
    
    def __repr__(self):
        return f"Lamella Slope Plate Clarifier surface overflow rate (m3/m2/h)={self.surface_overflow_rate}, " \
            f"TSS in (mg/L)={self.tss_in_mgl}, " \
            f"TSS out (mg/L)={self.tss_out_mgl}, " \
            f"sludge density (kg/m3)={self.sludge_density_kg_m3}"

    def get_kpi(self, kpi: str) -> float:
        """Get the value for a KPI"""
        function_name = TECH_KPI_MAPPINGS.get(kpi, None)
        if function_name is not None:
            return getattr(self, function_name)
        else:
            raise ValueError(
                f"KPI '{kpi}' not implemented for {self.__class__.__name__}.")

    def get_kpi_dict(self, kpi_list=None):
        if kpi_list:
            return {kpi: self.get_kpi(kpi=kpi) for kpi in kpi_list}
        return {kpi: self.get_kpi(kpi=kpi) for kpi in TECH_KPI_MAPPINGS.keys()}

    @property
    def chemical_solution_concentration__mg_per_l(self) -> float:
        return 0.0  # No chemicals used

    @property
    def daily_mass_of_chemicals__kg(self) -> dict[str, float]:
        return {}  # No chemicals used in Sludge clarifiers
    
    @property
    def sludge_production_kg(self) -> float:
        """Calculates sludge production (waste solids) in kg/day."""
        sludge_production_kgh = self.nominal_flow_m3perh * (self.tss_in_mgl - self.tss_out_mgl) / 1000.0
        return sludge_production_kgh * 24.0

    @property
    def footprint_area__m2(self) -> float:
        """Total Area = Clarifier Area + Sludge Thickening Area."""
        unit_area_m2 = 1.1 * (self.flow_per_unit / self.surface_overflow_rate)    
        clarifiers_area_total = unit_area_m2 * self.units_per_lane * self.lanes 
        daily_sludge_vol = self.sludge_production_kg / self.sludge_density_kg_m3
        sludge_area_m2 = daily_sludge_vol / self.sludge_tank_height_m
        backwash_flow = unit_area_m2 / self.backwash_filtration_rate
        backwash_volume_m3 = backwash_flow / (self.backwash_duration_min/60)
        backwash_area_m2 = 7 * backwash_volume_m3 / self.backwash_tank_height_m #assuming daily backwash and 7 days of backwash storage
        return 1.2 * (clarifiers_area_total + sludge_area_m2 + backwash_area_m2)  # 20% access factor
    
    @property
    def footprint_area_for_chemicals__m2(self):
        return 0.0  # No chemicals used in Sludge Blanket Clarifier

    @property
    def hydraulic_headloss__bar(self) -> float:
        unit_area_m2 = 1.1 * (self.flow_per_unit / self.surface_overflow_rate)
        tank_height_m = 1
        return meters_of_water_to_bar(1.1 * (tank_height_m + 0.001 * unit_area_m2))

    @property
    def power__kw(self) -> float:
        """Power for sludge scrapers/pumps based on sludge production."""
        unit_area_m2 = 1.1 * (self.flow_per_unit / self.surface_overflow_rate) 
        scraper_unit_kW = self.scraper_power_coeff_kw_m2 * unit_area_m2 
        backwash_flow = unit_area_m2 / self.backwash_filtration_rate
        head = 8 # assuming 8 meters of pressure head
        backwash_pump_kw = DENS_WATER_KG_PER_M3 * backwash_flow * GRAVITY_M_PER_S2 * head /(3600 * self.power_efficiency_pumps * 1000)
        return (scraper_unit_kW * self.lanes * self.units_per_lane) + backwash_pump_kw

    @property
    def daily_energy_consumption__kwh(self) -> float:
        """Apply the configured duty-cycle factor to daily energy use."""
        daily_kWh = 1  # Scraper and backwash pumps run once per day.
        return self.power__kw * (self.backwash_duration_min/60) * daily_kWh

    @property
    def co2_emissions__kg_co2_eq_per_m3(self) -> float:
        if self.emission_factor_electricity is None:
            raise ValueError("Emission factor for electricity is not set.")
        co2_emissions = (
            self.daily_energy_consumption__kwh *
            self.emission_factor_electricity)
        specific_co2_emissions = co2_emissions / self.nominal_flow_m3perh / 24  # kg CO2 eq per m3
        return specific_co2_emissions

