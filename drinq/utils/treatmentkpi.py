import numpy as np
from abc import ABC, abstractmethod
from dataclasses import dataclass
from drinq.utils.unit_conversions import (
    lppd_to_m3phr, bar_to_meters_of_water, meters_of_water_to_bar)
from drinq.utils.physics_and_chemistry import (
    DENS_WATER_KG_PER_M3,
    WATER_VISCOSITY_N_S_PER_M2,
    GRAVITY_M_PER_S2,
    METER_PER_BAR,
    dynamic_viscosity_water_pa_s,
    friction_factor_pipe,
    reynolds_number_pipe,
    calculate_pressure_drop_pipe
    )

import json


# NOTE: The keys of these mappings SHOULD BE in sync with
# the database table "technologykpi"!
TECH_KPI_MAPPINGS = {
    'footprint area': 'footprint_area__m2',
    'footprint area for chemicals': 'footprint_area_for_chemicals__m2',
    'daily energy consumption': 'daily_energy_consumption__kwh',
    'daily mass of chemicals': 'daily_mass_of_chemicals__kg',
    'chemical solution concentration': 'chemical_solution_concentration__mg_per_l',  # noqa, E501
    'head loss': 'hydraulic_headloss__bar',
    'power': 'power__kw',
    'co2 emissions': 'co2_emissions__kg_co2_eq_per_m3',
}

# IMPORTANT PROPERTIES FOR COST CALCULATIONS
# - volume (m3)
# - filter area (m2)
# - membrane area (m2)
# - dosing flow rate (1e-3 m3/hr) [Coagulation with dynamic mixing]
# - area (m2) [Strainer, Microstrainer, Chain-scraped sedimentation tank, Lamella clarifier, DAF, PAC, Pellet softening, sludge blanket filtr]  # noqa, E501

# NOTE We import all the parameter names from a json file. This file SHOULD BE kept
# in sync with the database table "technologyproperty"!
with open("drinq/utils/treatmentpropertyname.json", "r") as file:
    TPN = json.load(file)
with open("drinq/utils/treatmentplantpropertyname.json", "r") as file:
    TPPN = json.load(file)

NOMINAL_FLOW_RATE_NAME = TPPN['nominal_flow_rate_m3perh']


def match_tech_kpi(kpi_fullname: str) -> str:
    """Match user-provided KPI name to available KPIs.

    Args:
        kpi_name (str): The name of the KPI to match. This names should 
        correspond to the KPIs defined in table "technologykpi".
    """
    KPI_reverse_mappings = {v: k for k, v in TECH_KPI_MAPPINGS.items()}
    if kpi_fullname.lower() in KPI_reverse_mappings.keys():
        return KPI_reverse_mappings[kpi_fullname.lower()]
    raise ValueError(f"KPI '{kpi_fullname}' not found in available KPIs.")


def get_value_of_dictionary_with_lower_key_str(
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
    return dictionary.get(value.lower(), None)


@dataclass
class TreatmentDataclassMixin:
    """Dataclass mixin for treatment KPIs.
    
    Args:
        parameters (dict): Dictionary of technology parameters.
        design_parameters (dict): Dictionary of design parameters.
        plant_kpis (dict): Dictionary of plant performance indicators.
        digest_parameter_list (list[str], optional): List of parameter names 
            which are digested for cost or other calculations. Defaults to None.
    """
    parameters: dict
    design_parameters: dict
    plant_kpis: dict
    wq_parameters: dict | None = None
    digest_parameter_list: list[str] | None = None

    def __post_init__(self):
        self.parameters = self.parameters
        self.wq_parameters = self.wq_parameters
        self.design_parameters = self.design_parameters
        self.plant_kpis = self.plant_kpis
        if len(self.digest_parameter_list) == 0:
            self.digest_parameter_list = None
        self.digest_parameter_list = self.digest_parameter_list


class TreatmentKPI(ABC, TreatmentDataclassMixin):
    """Abstract base class for treatment KPIs."""

    @abstractmethod
    def get_kpi(self, kpi_name: str) -> float:
        """Get the value of the specified KPI.

        Args:
            kpi_name (str): The name of the KPI to retrieve.

        Returns:
            float: The value of the specified KPI.
        """
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
        raise NotImplementedError("Subclasses should implement this method")

    @property
    @abstractmethod
    def footprint_area_for_chemicals__m2(self) -> float:
        raise NotImplementedError("Subclasses should implement this method")

    @property
    @abstractmethod
    def daily_energy_consumption__kwh(self) -> float:
        raise NotImplementedError("Subclasses should implement this method")

    @property
    @abstractmethod
    def daily_mass_of_chemicals__kg(self) -> float:
        raise NotImplementedError("Subclasses should implement this method")

    @property
    @abstractmethod
    def chemical_solution_concentration__mg_per_l(self) -> float:
        raise NotImplementedError("Subclasses should implement this method")

    @property
    @abstractmethod
    def hydraulic_headloss__bar(self) -> float:
        raise NotImplementedError("Subclasses should implement this method")

    @property
    @abstractmethod
    def power__kw(self) -> float:
        raise NotImplementedError("Subclasses should implement this method")

    @property
    @abstractmethod
    def co2_emissions__kg_co2_eq_per_m3(self) -> float:
        raise NotImplementedError("Subclasses should implement this method")


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
        volume_dosing_m3perday_perunit (float): dosing volume in m3/day per unit
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
        residual_chlorine_mgL (float): target residual chlorine concentration in mg/L
        dosing_solution_concentration_w_w (float): chlorine solution concentration in w/w%
    """
    if dosing_solution_concentration_w_w <= 0:
        raise ValueError("Dosing solution concentration must be greater than zero.")    
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
        raise ValueError("Chlorine to ammonia ratio must be greater than zero.")
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
        pressure_vessel_orientation: int,
        membranes_per_vessel: int,
        vessels_per_unit: float) -> float:
    """Calculate membrane area based on vessel orientation.

    Args:
        pressure_vessel_orientation (int): 0 for vertical, 1 for horizontal
        membranes_per_vessel (int): number of membranes per vessel
        vessels_per_unit (float): number of vessels per unit
    """
    if pressure_vessel_orientation == 0:  # vertical alignment

        return membranes_per_vessel * vessels_per_unit
    else:
        return membranes_per_vessel * vessels_per_unit * 2


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


class CoagulationDynamicMixing(TreatmentKPI):
    """KPI calculations for a Coagulation with Dynamic Mixing treatment unit."""
    tank_height: float
    chem_tank_height: float
    lanes: int
    nominal_flow_m3hr: float
    units_per_lane: int
    conc_chem_mgL: float
    solution_wwperc: float
    density_chemical_gpercm3: float
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
    dosing_flow_rate_literhr: float  # needed for cost calculations

    def __post_init__(self):
        super().__post_init__()
        parameters = self.parameters
        design_parameters = self.design_parameters
        performance_indicators = self.plant_kpis

        self.tank_height = parameters[TPN['tank_height']]
        self.chem_tank_height = parameters[TPN['tank_height_chemical_storage']]
        self.lanes = design_parameters.get('number of lanes', 1)
        self.nominal_flow_m3hr = performance_indicators.get(
            NOMINAL_FLOW_RATE_NAME, None)  # noqa, E501
        self.units_per_lane = design_parameters.get('units per lane', 1)
        self.conc_chem_mgL = parameters[
            TPN['target_concentration_of_dosing_chemical_mg_l']]
        self.solution_wwperc = parameters[
            TPN['chemical_dosing_solution_concentration_w_w_percent']]
        # TODO: verify with Greg if fixed mass density of FeCl3 is correct
        self.density_chemical_gpercm3 = parameters[
             TPN['mass_density_of_chemical_g_cm3']]
        self.retention_time_min = parameters[
            TPN['retention_time_min']]
        self.storage_time_days = parameters[
            TPN['storage_time_of_chemicals_days']]
        self.efficiency_mixer = parameters[TPN['power_efficiency_of_mixers']] / 100  # noqa, E501
        self.mixer_velocity_grad = parameters[TPN['mixer_velocity_gradient']]
        self.water_viscosity = design_parameters.get(
            'dynamic viscosity', WATER_VISCOSITY_N_S_PER_M2)
        self.flow_per_lane = calculate_flow_per_lane(
            self.lanes, self.nominal_flow_m3hr)
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
            units_per_lane=1,
            solution_concentration_w_w_percent=self.solution_wwperc,
        ) * self.lanes  # m3/day
        # Update the dosing rate
        self.dosing_flow_rate_literhr = calculate_dosing_flow_rate__m3perhr(
            volume_dosing_m3perday_perunit=self.volume_chemical_day,
            units_per_lane=1,
            lanes=1,
        ) * 1000
        self.parameters[TPN['nominal_dosing_flow_rate']] = self.dosing_flow_rate_literhr  # noqa, E501
        self.chemicals_area_m2 = calculate_chemical_storage_area__m2(
            daily_volume_m3perday=self.volume_chemical_day,
            storage_time_days=self.storage_time_days,
            tank_height_m=self.chem_tank_height,
        )

    def __repr__(self):
        return f"CoagulationDynamicMixing(tank height (m)={self.tank_height}, " \
                f"retention time (min)={self.retention_time_min}, " \
                f"nominal flow (m3/hr)={self.nominal_flow_m3hr})"

    def get_kpi(self, kpi: str) -> float:
        """Get the value for a KPI"""
        function_name = get_value_of_dictionary_with_lower_key_str(
            TECH_KPI_MAPPINGS, kpi)
        if function_name is not None:
            return getattr(self, function_name)()
        else:
            raise ValueError(
                f"KPI '{kpi}' not implemented for {self.__class__.__name__}.")

    def get_kpi_dict(self, kpi_list=None):
        if kpi_list:
            return {kpi: self.get_kpi(kpi=kpi) for kpi in kpi_list}
        return {kpi: self.get_kpi(kpi=kpi) for kpi in TECH_KPI_MAPPINGS.keys()}

    def footprint_area__m2(self) -> float:
        return np.ceil(self.tanks_area_m2 + self.chemicals_area_m2)

    def footprint_area_for_chemicals__m2(self) -> float:
        return self.chemicals_area_m2

    def daily_mass_of_chemicals__kg(self) -> float:
        dosing_per_lane = calculate_dosing_mass__perday_perunit(
            concentration_mgL=self.conc_chem_mgL,  # noqa, E501
            flow_per_lane_m3hr=self.flow_per_lane,
            units_per_lane=self.units_per_lane,
        )
        return dosing_per_lane * self.lanes
    
    def chemical_solution_concentration__mg_per_l(self) -> float:
        return self.conc_chem_mgL

    def hydraulic_headloss__bar(self) -> float:
        return 1 + (0.001 * self.tanks_area_m2) + self.tank_height

    def power__kw(self) -> float:
        seconds_per_day = 86400
        power_kw_unit = (
            (
                (1/self.efficiency_mixer) * self.mixer_velocity_grad**2
             ) * self.water_viscosity * self.unit_volume_m3) / 1000
        # TODO: check formula with Greg, i.e. why factor 5? 5 Pumps?
        density_chemical = self.density_chemical_gpercm3 * 1000  # to kg/m3
        power_pump_kw = (
            density_chemical * GRAVITY_M_PER_S2 *
            self.volume_chemical_day * 5) / (
                seconds_per_day * self.efficiency_mixer) / 1000
        return power_kw_unit * self.units_per_lane * self.lanes + power_pump_kw

    def co2_emissions__kg_co2_eq_per_m3(self) -> float:
        return 0.0  # TODO: placeholder for CO2 emissions calculation

    def daily_energy_consumption__kwh(self) -> float:
        return self.power__kw() * 24  # Assuming continuous operation


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

    def __post_init__(self):
        super().__post_init__()
        parameters = self.parameters
        design_parameters = self.design_parameters
        performance_indicators = self.plant_kpis
        digest_parameter_list = self.digest_parameter_list

        self.weir_height = parameters[TPN['weir_height']]
        self.tank_height = parameters[TPN['tank_height']]
        self.units_per_lane = design_parameters.get('units per lane', 1)
        self.weir_coefficient = parameters[TPN['weir_coefficient']]
        self.headloss_coefficient = parameters[TPN['head_loss_coefficient']]
        self.chem_dosing_solution_concentration_w_w = (
            parameters[
                TPN['chemical_dosing_solution_concentration_w_w_percent']
                ])
        self.power_for_dosing_kw = parameters[TPN['power']]
        self.target_chemical_concentration_mgL = (
            parameters[TPN['target_concentration_of_dosing_chemical_mg_l']])
        self.power_efficiency_mixer = parameters[TPN['power_efficiency_of_mixers']] / 100  # noqa
        self.water_viscosity = design_parameters.get(
            'dynamic viscosity', WATER_VISCOSITY_N_S_PER_M2)
        self.lanes = design_parameters.get('number of lanes', 1)
        self.nominal_flow_m3hr = performance_indicators.get(
            NOMINAL_FLOW_RATE_NAME, None)
        self.flow_per_lane_m3perh = calculate_flow_per_lane(
            self.lanes, self.nominal_flow_m3hr)
        self.retention_time_min = parameters[
            TPN['retention_time_min']]
        self.number_of_cascade_stages = parameters[
            TPN['number_of_cascade_stages']]
        self.storage_time_days = design_parameters[
            TPN['storage_time_of_chemicals_days']]
        self.chemical_tank_height = parameters[
            TPN['tank_height_chemical_storage']]
        self.unit_volume_m3 = calculate_unit_volume_m3(
            flow_per_lane_m3h=self.flow_per_lane_m3perh,
            units_per_lane=1,
            retention_time_min=self.retention_time_min)
        # TODO: verify formula with Greg, why only 1/3 of area per lane?
        self.casc_lane_width_m = np.sqrt(self.unit_volume_m3 / (
            self.tank_height) / 3)  # assuming 1/3 of area per lane

    def __repr__(self):
        return f"CascadeMixerCoagulationDosing(tank height (m)={self.tank_height}, " \
                f"retention time (min)={self.retention_time_min}, " \
                f"nominal flow (m3/hr)={self.nominal_flow_m3hr})"

    def get_kpi(self, kpi: str) -> float:
        """Get the value for a KPI"""
        function_name = get_value_of_dictionary_with_lower_key_str(
            TECH_KPI_MAPPINGS, kpi)
        if function_name is not None:
            return getattr(self, function_name)
        else:
            raise ValueError(
                f"KPI '{kpi}' not implemented for {self.__class__.__name__}.")

    def get_kpi_dict(self, kpi_list=None):
        if kpi_list:
            return {kpi: self.get_kpi(kpi=kpi) for kpi in kpi_list}
        return {kpi: self.get_kpi(kpi=kpi) for kpi in TECH_KPI_MAPPINGS.keys()}

    def footprint_area__m2(self) -> float:
        cascade_area_m2 = (self.unit_volume_m3 / self.tank_height
                           ) * self.lanes * self.units_per_lane
        chemicals_area_m2 = self.footprint_area_for_chemicals__m2()
        return np.ceil(cascade_area_m2 + chemicals_area_m2)

    def footprint_area_for_chemicals__m2(self) -> float:
        volume_chemicals_m3 = calculate_dosing_volume__m3perday_perunit(  # noqa, E501
            concentration_mgL=self.target_chemical_concentration_mgL,
            flow_per_lane_m3hr=self.flow_per_lane_m3perh,
            units_per_lane=1,
            solution_concentration_w_w_percent=(
                self.chem_dosing_solution_concentration_w_w),
        ) * self.lanes  # m3/day
        chemicals_area_m2 = calculate_chemical_storage_area__m2(
            daily_volume_m3perday=volume_chemicals_m3,
            storage_time_days=self.storage_time_days,
            tank_height_m=self.chemical_tank_height,
        )
        return chemicals_area_m2

    def daily_energy_consumption__kwh(self) -> float:
        return self.power__kw() * 24  # Assuming continuous operation

    def daily_mass_of_chemicals__kg(self) -> float:
        return 0.0  # TODO: implement chemical dosing mass calculation
    
    def chemical_solution_concentration__mg_per_l(self) -> float:
        return 0.0  # TODO: implement chemical dosing concentration calculation

    def hydraulic_headloss__bar(self) -> float:
        # TODO: verify formula with Greg
        flow_per_cascade_stage_m3persec = (
            self.flow_per_lane_m3perh / self.number_of_cascade_stages) / 3600
        cascade_flowing_area_m2 = (self.casc_lane_width_m * self.weir_height)
        headloss_weir = self.headloss_coefficient * (
            (flow_per_cascade_stage_m3persec / cascade_flowing_area_m2) ** 2
            ) / (2 * GRAVITY_M_PER_S2)
        headloss_cascade = headloss_weir * self.number_of_cascade_stages
        total_headloss = self.tank_height + headloss_cascade
        return meters_of_water_to_bar(total_headloss)

    def power__kw(self) -> float:
        headloss_m = bar_to_meters_of_water(self.hydraulic_headloss__bar())
        flow_m3_per_s = (self.flow_per_lane_m3perh / 3600) * self.lanes
        power_watts = (
            DENS_WATER_KG_PER_M3 * GRAVITY_M_PER_S2 * headloss_m *
            flow_m3_per_s)
        power_kw = power_watts / 1000  # Convert watts to kW
        return power_kw

    def co2_emissions__kg_co2_eq_per_m3(self) -> float:
        pass  # Placeholder for CO2 emissions calculation


class MicroStrainer(TreatmentKPI):
    """KPI calculations for a strainer or microstrainer treatment unit."""
    open_area_factor: float
    nominal_flow_m3perh: float
    screen_velocity_mpersec: float
    lanes: int
    flow_per_lane_m3perh: float
    headloss_coefficient: float
    area: float  # equal to footprint area, used for cost calculations

    def __post_init__(self):
        super().__post_init__()
        parameters = self.parameters
        design_parameters = self.design_parameters
        performance_indicators = self.plant_kpis

        self.nominal_flow_m3perh = performance_indicators.get(
            NOMINAL_FLOW_RATE_NAME, None)
        self.screen_velocity_mpersec = parameters[TPN['velocity_bar_screen']]
        self.lanes = design_parameters.get('number of lanes', 1)
        self.flow_per_lane_m3perh = calculate_flow_per_lane(
            self.lanes, self.nominal_flow_m3perh)
        self.headloss_coefficient = parameters[TPN['head_loss_coefficient']]
        self.open_area_factor = parameters[TPN['open_area_factor']]
        self.area = 0.0  # Initialize area, will be calculated later
        for tech_property in self.digest_parameter_list:
            if tech_property == 'area':
                self.area = self.footprint_area__m2()
            self.parameters[tech_property] = self.area  # overwrite area

    def __repr__(self):
        return f"Micro strainer(nominal flow (m3/hr)={self.nominal_flow_m3perh})"

    def get_kpi(self, kpi: str) -> float:
        """Get the value for a KPI"""
        function_name = get_value_of_dictionary_with_lower_key_str(
            TECH_KPI_MAPPINGS, kpi)
        if function_name is not None:
            return getattr(self, function_name)()
        else:
            raise ValueError(
                f"KPI '{kpi}' not implemented for {self.__class__.__name__}.")

    def get_kpi_dict(self, kpi_list=None):
        if kpi_list:
            return {kpi: self.get_kpi(kpi=kpi) for kpi in kpi_list}
        return {kpi: self.get_kpi(kpi=kpi) for kpi in TECH_KPI_MAPPINGS.keys()}

    def footprint_area__m2(self) -> float:
        effective_area = calculate_footprint_area_strainer_screens__m2(
            flow_m3hr=self.nominal_flow_m3perh,
            screen_velocity_mpersec=self.screen_velocity_mpersec,
        )
        fp_area = effective_area / self.open_area_factor
        self.area = fp_area  # Store area for cost calculations
        return fp_area

    def footprint_area_for_chemicals__m2(self) -> float:
        return 0.0  # No chemicals used in Strainer

    def hydraulic_headloss__bar(self) -> float:
        return calculate_hydraulic_headloss_strainer_screens__bar(
            headloss_coefficient=self.headloss_coefficient,
            screen_velocity_mpersec=self.screen_velocity_mpersec)

    def power__kw(self) -> float:
        # TODO: check the formula with Greg
        headloss_m = bar_to_meters_of_water(self.hydraulic_headloss__bar())
        flow_per_lane_m3persec = self.flow_per_lane_m3perh / 3600
        power_watts = (
            DENS_WATER_KG_PER_M3 * GRAVITY_M_PER_S2 * headloss_m *
            flow_per_lane_m3persec * self.lanes)
        return power_watts / 1000  # Convert watts to kW

    def daily_energy_consumption__kwh(self) -> float:
        return self.power__kw() * 24  # Assuming continuous operation

    def daily_mass_of_chemicals__kg(self) -> float:
        return 0.0  # No chemicals used in Micro strainer
    
    def chemical_solution_concentration__mg_per_l(self) -> float:
        return 0.0  # No chemicals used in Micro strainer

    def co2_emissions__kg_co2_eq_per_m3(self) -> float:
        pass  # Placeholder for CO2 emissions calculation


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

    def __post_init__(self):
        super().__post_init__()
        parameters = self.parameters
        design_parameters = self.design_parameters
        performance_indicators = self.plant_kpis

        self.bar_spacing = parameters[TPN['bar_spacing']]
        self.bar_width = parameters[TPN['bar_width']]
        self.blockage_factor = parameters[TPN['blockage_factor']]
        self.open_area_friction = (
            self.bar_spacing/(self.bar_spacing + self.bar_width)
                ) * (1 - self.blockage_factor)
        self.nominal_flow_m3perh = performance_indicators.get(
            NOMINAL_FLOW_RATE_NAME, None)
        self.screen_velocity_mpersec = parameters[TPN['velocity_bar_screen']]
        self.lanes = design_parameters.get('number of lanes', 1)
        self.flow_per_lane_m3perh = calculate_flow_per_lane(
            self.lanes, self.nominal_flow_m3perh)
        self.headloss_coefficient = parameters[TPN['head_loss_coefficient']]

    def __repr__(self):
        return f"Strainer(bar spacing (m)={self.bar_spacing}, " \
                f"bar width (m)={self.bar_width}, " \
                f"nominal flow (m3/hr)={self.nominal_flow_m3perh})"

    def get_kpi(self, kpi: str) -> float:
        """Get the value for a KPI"""
        function_name = get_value_of_dictionary_with_lower_key_str(
            TECH_KPI_MAPPINGS, kpi)
        if function_name is not None:
            return getattr(self, function_name)
        else:
            raise ValueError(
                f"KPI '{kpi}' not implemented for {self.__class__.__name__}.")

    def get_kpi_dict(self, kpi_list=None):
        if kpi_list:
            return {kpi: self.get_kpi(kpi=kpi) for kpi in kpi_list}
        return {kpi: self.get_kpi(kpi=kpi) for kpi in TECH_KPI_MAPPINGS.keys()}

    def footprint_area__m2(self) -> float:
        return calculate_footprint_area_strainer_screens__m2(
            flow_m3hr=self.nominal_flow_m3perh,
            screen_velocity_mpersec=self.screen_velocity_mpersec,
        )

    def footprint_area_for_chemicals__m2(self) -> float:
        return 0.0  # No chemicals used in Strainer

    def hydraulic_headloss__bar(self) -> float:
        return calculate_hydraulic_headloss_strainer_screens__bar(
            headloss_coefficient=self.headloss_coefficient,
            screen_velocity_mpersec=self.screen_velocity_mpersec)

    def power__kw(self) -> float:
        # TODO: check the formula with Greg
        headloss_m = bar_to_meters_of_water(self.hydraulic_headloss__bar())
        flow_per_lane_m3persec = self.flow_per_lane_m3perh / 3600
        power_watts = (
            DENS_WATER_KG_PER_M3 * GRAVITY_M_PER_S2 * headloss_m *
            flow_per_lane_m3persec * self.lanes)
        return power_watts / 1000  # Convert watts to kW

    def daily_energy_consumption__kwh(self) -> float:
        return self.power__kw() * 24  # Assuming continuous operation

    def daily_mass_of_chemicals__kg(self) -> float:
        return 0.0  # No chemicals used in Strainer

    def chemical_solution_concentration__mg_per_l(self) -> float:
        return 0.0  # No chemicals used in Strainer

    def co2_emissions__kg_co2_eq_per_m3(self) -> float:
        pass  # Placeholder for CO2 emissions calculation


class ChainScrapedSedimentation(TreatmentKPI):
    """KPI calculations for a Chain Scraped Sedimentation treatment unit."""
    lanes: int
    units_per_lane: int
    flow_m3perh: float
    flow_m3persec: float
    flow_per_lane_m3perh: float
    retention_time_min: float
    scraper_power_per_m2: float
    total_suspended_solids: float
    overflow_rate_m3_per_m2_per_h: float

    def __post_init__(self):
        super().__post_init__()
        parameters = self.parameters
        design_parameters = self.design_parameters
        performance_indicators = self.plant_kpis
        wq_parameters = self.wq_parameters

        self.lanes = design_parameters.get('number of lanes', 1)
        self.units_per_lane = design_parameters.get('units per lane', 1)
        self.flow_m3perh = performance_indicators.get(
            'nominal flow rate (m3/hr)', None)
        self.flow_m3persec = self.flow_m3perh / 3600
        self.flow_per_lane_m3perh = calculate_flow_per_lane(
            self.lanes, self.flow_m3perh)
        self.retention_time_min = parameters[TPN['retention_time_min']]
        self.scraper_power_per_m2 = parameters[TPN['scraper_power_coefficient']]
        self.total_suspended_solids = wq_parameters.get(
            'total suspended solids (mg/l)', 0)
        self.overflow_rate_m3_per_m2_per_h = design_parameters['overflow rate (m3/m2/h)']
        self.unit_area_m2 = (self.flow_per_lane_m3perh /
                             self.overflow_rate_m3_per_m2_per_h)
        # TODO: verify formula with Greg
        self.unit_volume_m3 = (
            self.flow_m3perh * self.retention_time_min / 60) / (
                self.lanes * self.units_per_lane)
        self.tank_height_m = self.unit_volume_m3 / self.unit_area_m2

    def __repr__(self):
        return f"ChainScrapedSedimentation(retention time (min)={self.retention_time_min}, " \
                f"nominal flow (m3/hr)={self.flow_m3perh})"

    def get_kpi(self, kpi: str) -> float:
        """Get the value for a KPI"""
        function_name = get_value_of_dictionary_with_lower_key_str(
            TECH_KPI_MAPPINGS, kpi)
        if function_name is not None:
            return getattr(self, function_name)
        else:
            raise ValueError(
                f"KPI '{kpi}' not implemented for {self.__class__.__name__}.")

    def get_kpi_dict(self, kpi_list=None):
        if kpi_list:
            return {kpi: self.get_kpi(kpi=kpi) for kpi in kpi_list}
        return {kpi: self.get_kpi(kpi=kpi) for kpi in TECH_KPI_MAPPINGS.keys()}

    def footprint_area__m2(self) -> float:
        return np.ceil(self.unit_area_m2 * self.units_per_lane * self.lanes)

    def footprint_area_for_chemicals__m2(self) -> float:
        return 0.0  # No chemicals used in Chain Scraped Sedimentation

    def daily_mass_of_chemicals__kg(self) -> float:
        return 0.0  # No chemicals used in Chain Scraped Sedimentation
    
    def chemical_solution_concentration__mg_per_l(self) -> float:
        return 0.0  # No chemicals used in Chain Scraped Sedimentation

    def hydraulic_headloss__bar(self) -> float:
        headloss_m_constant = 0.5  # constant headloss in meters
        number_of_units = self.units_per_lane * self.lanes
        headloss_m = headloss_m_constant + 0.05 * (
            self.flow_m3persec / number_of_units / self.unit_area_m2) ** 2 / (
                2 * GRAVITY_M_PER_S2
            )  # TODO: verify formula with Greg
        return meters_of_water_to_bar(headloss_m)

    def power__kw(self) -> float:
        number_of_units = self.units_per_lane * self.lanes
        scraper_power_per_unit_kw = (
            self.scraper_power_per_m2 * self.unit_area_m2)
        total_power_kw = scraper_power_per_unit_kw * number_of_units
        return np.ceil(total_power_kw)

    def daily_energy_consumption__kwh(self) -> float:
        return self.power__kw() * 24  # Assuming continuous operation

    def co2_emissions__kg_co2_eq_per_m3(self) -> float:
        pass  # Placeholder for CO2 emissions calculation


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

    def __post_init__(self):
        super().__post_init__()
        parameters = self.parameters
        design_parameters = self.design_parameters
        plant_kpis = self.plant_kpis

        self.units_per_lane = design_parameters.get('units per lane', 1)        
        self.lanes = design_parameters.get('number of lanes', 1)
        self.tank_height_m = parameters[
            TPN['tank_height']]
        self.chemicals_tank_height_m = parameters[
            TPN['tank_height_chemical_storage']]
        self.storage_time_days = design_parameters.get(
            TPN['storage_time_of_chemicals_days'], 30)
        self.nominal_flow_m3perh = plant_kpis.get(
            NOMINAL_FLOW_RATE_NAME, None)
        self.flow_per_lane_m3perh = calculate_flow_per_lane(
            self.lanes, self.nominal_flow_m3perh)
        self.power_of_dosing_kw = parameters[
            TPN['power']]
        self.retention_time_min = parameters[
            TPN['retention_time_min']]
        self.target_residual_chlorine_mgL = parameters[
            TPN['target_residual_concentration_mg_l']]  # noqa, E501
        self.chlorine_dosing_mgL = parameters[
            TPN['target_concentration_of_dosing_chemical_mg_l']]  # noqa, E501
        self.chlorine_solution_w_w = parameters[
            TPN['chemical_dosing_solution_concentration_w_w_percent']]  # noqa, E501
        self.chlorine_concentration_mgL = calculate_chlorine_concentration_mgL(  # noqa, E501
            residual_chlorine_mgL=self.target_residual_chlorine_mgL,
            dosing_solution_concentration_w_w=self.chlorine_solution_w_w
        )

    def __repr__(self):
        return f"ChlorineDisinfection(tank height (m)={self.tank_height_m}, " \
                f"chemical tank height (m)={self.chemicals_tank_height_m}, " \
                f"retention time (min)={self.retention_time_min}, " \
                f"nominal flow (m3/hr)={self.nominal_flow_m3perh})"

    def get_kpi(self, kpi: str) -> float:
        """Get the value for a KPI"""
        function_name = get_value_of_dictionary_with_lower_key_str(
            TECH_KPI_MAPPINGS, kpi)
        if function_name is not None:
            return getattr(self, function_name)
        else:
            raise ValueError(
                f"KPI '{kpi}' not implemented for {self.__class__.__name__}.")

    def get_kpi_dict(self, kpi_list=None):
        if kpi_list:
            return {kpi: self.get_kpi(kpi=kpi) for kpi in kpi_list}
        return {kpi: self.get_kpi(kpi=kpi) for kpi in TECH_KPI_MAPPINGS.keys()}

    def footprint_area__m2(self) -> float:
        unit_volume_m3 = calculate_unit_volume_m3(
            flow_per_lane_m3h=self.flow_per_lane_m3perh,
            units_per_lane=self.units_per_lane,
            retention_time_min=self.retention_time_min)
        unit_area_m2 = calculate_unit_area_tank(
            unit_volume_m3=unit_volume_m3,
            unit_height_m=self.tank_height_m)
        chemicals_area_m2 = self.footprint_area_for_chemicals__m2()
        return np.ceil(unit_area_m2 * self.lanes + chemicals_area_m2)

    def footprint_area_for_chemicals__m2(self) -> float:
        # TODO: verify formula with Greg
        volume_chemical_day_m3 = self.daily_mass_of_chemicals__kg() / (
            1000 * self.chlorine_solution_w_w)  # m3/day
        chemicals_area_m2 = (
            volume_chemical_day_m3 * self.storage_time_days) / (
            self.chemicals_tank_height_m)
        return chemicals_area_m2

    def daily_mass_of_chemicals__kg(self) -> float:
        dosing_per_lane = calculate_dosing_mass__perday_perunit(
            concentration_mgL=self.chlorine_concentration_mgL,
            flow_per_lane_m3hr=self.flow_per_lane_m3perh,
            units_per_lane=1,
        )
        return dosing_per_lane * self.lanes * 1

    def chemical_solution_concentration__mg_per_l(self) -> float:
        return self.chlorine_concentration_mgL

    def hydraulic_headloss__bar(self) -> float:
        return 0.2  # Assumed constant headloss for chlorine disinfection

    def power__kw(self) -> float:
        return self.power_of_dosing_kw

    def daily_energy_consumption__kwh(self) -> float:
        return self.power__kw() * 24  # Assuming continuous operation

    def co2_emissions__kg_co2_eq_per_m3(self) -> float:
        pass  # Placeholder for CO2 emissions calculation


class ChloramineDisinfection(TreatmentKPI):
    """KPI calculations for a Chloramine Disinfection treatment unit."""
    def __init__(
            self,
            parameters: dict,
            plant_kpis: dict,
            design_parameters: dict,
    ):
        self.chlorine_disinfection = ChlorineDisinfection(
            parameters,
            plant_kpis,
            design_parameters,
        )
        self.ammonia_dosing_mgL = self.chlorine_disinfection.chlorine_dosing_mgL / 5  # noqa, E501
        self.ammonia_concentration_mgL = calculate_ammonia_concentration_mgL(
            target_chlorine_mgL=parameters[
                TPN['target_residual_concentration_mgL']],
            chlorine_to_ammonia_ratio=5,
        )
        self.lanes = design_parameters.get('number of lanes', 1)
        self.flow_per_lane_m3perh = calculate_flow_per_lane(
            self.lanes, plant_kpis.get('nominal flow rate (m3/hr)', None))
        self.retention_time_min = parameters[TPN['retention_time_min']]
        self.units_per_lane = design_parameters.get('number of units per lane', 1)
        self.number_of_units = self.units_per_lane * self.lanes
        self.storage_time_days = parameters[TPN['chemical_storage_time_days']]
        self.tank_height_m = parameters[TPN['tank_height']]
        # TODO: verify formula with Greg
        self.volume_chlorine_m3day = self.chlorine_disinfection.daily_mass_of_chemicals__kg() / (  # noqa, E501
            1000 * 1.19)
        self.volume_ammonia_m3day = self.daily_mass_of_chemicals__kg() / (
            1000 * 0.68)

    def get_kpi(self, kpi: str) -> float:
        """Get the value for a KPI"""
        function_name = get_value_of_dictionary_with_lower_key_str(
            TECH_KPI_MAPPINGS, kpi)
        if function_name is not None:
            return getattr(self, function_name)
        else:
            raise ValueError(
                f"KPI '{kpi}' not implemented for {self.__class__.__name__}.")

    def get_kpi_dict(self, kpi_list=None):
        if kpi_list:
            return {kpi: self.get_kpi(kpi=kpi) for kpi in kpi_list}
        return {kpi: self.get_kpi(kpi=kpi) for kpi in TECH_KPI_MAPPINGS.keys()}

    def footprint_area__m2(self) -> float:
        unit_volume_m3 = calculate_unit_volume_m3(
            flow_per_lane_m3h=self.flow_per_lane_m3perh,
            units_per_lane=self.units_per_lane,
            retention_time_min=self.retention_time_min)
        unit_area_m2 = calculate_unit_area_tank(
            unit_volume_m3=unit_volume_m3,
            unit_height_m=self.tank_height_m)
        chemicals_area_m2 = self.footprint_area_for_chemicals__m2()
        return np.ceil(unit_area_m2 * self.number_of_units + chemicals_area_m2)

    def footprint_area_for_chemicals__m2(self) -> float:
        volume_chemicals_m3day = (
            self.volume_chlorine_m3day + self.volume_ammonia_m3day)
        chemicals_area = (
            volume_chemicals_m3day * self.storage_time_days
            ) / self.tank_height_m

        return chemicals_area
    
    def daily_mass_of_chemicals__kg(self) -> float:
        mass_chlorine_kgday = self.chlorine_disinfection.daily_mass_of_chemicals__kg()  # noqa, E501
        mass_ammonia_kgday = calculate_dosing_mass__perday_perunit(
            concentration_mgL=self.ammonia_concentration_mgL,
            flow_per_lane_m3hr=self.flow_per_lane_m3perh,
            units_per_lane=self.units_per_lane,
        )
        return mass_chlorine_kgday + mass_ammonia_kgday

    def chemical_solution_concentration__mg_per_l(self) -> float:
        return self.ammonia_concentration_mgL

    def hydraulic_headloss__bar(self) -> float:
        return self.chlorine_disinfection.hydraulic_headloss__bar()

    def power__kw(self) -> float:
        # TODO: verify formulas with Greg: 1190 kg/m3 for chlorine, 680 kg/m3 for ammonia?
        chlorine_dosing_flow_m3s = self.volume_chlorine_m3day / (24 * 3600)
        ammonia_dosing_flow_m3s = self.volume_ammonia_m3day / (24 * 3600)
        power_chlorine_kw = (
            chlorine_dosing_flow_m3s * 9.81 * 1190) / (0.7 * 1000)
        power_ammonia_kw = (
            ammonia_dosing_flow_m3s * 9.81 * self.chlorine_to_ammonia_ratio *
            680) / (0.7 * 1000)  # storage at -33 °C, efficiency 70%?
        return power_chlorine_kw + power_ammonia_kw

    def daily_energy_consumption__kwh(self) -> float:
        return self.power__kw() * 24  # Assuming continuous operation
    
    def co2_emissions__kg_co2_eq_per_m3(self) -> float:
        pass  # Placeholder for CO2 emissions calculation


class MembraneFiltration(TreatmentKPI):
    """KPI calculations for a Membrane Filtration treatment unit."""
    def __init__(
            self,
            parameters: dict,
            performance_indicators: dict,
            design_parameters: dict,
    ):
        self.lanes = design_parameters[TPN['number_of_lanes']]
        self.units_per_lane = design_parameters[TPN['number_of_units_per_lane']]
        self.flow_rate_m3perh = performance_indicators.get(
            'nominal flow rate (m3/hr)', None)
        self.number_of_units = self.units_per_lane * self.lanes
        self.flow_per_lane_m3perh = calculate_flow_per_lane(
            self.lanes, self.flow_rate_m3perh)
        self.membranes_per_vessel = parameters[
            TPN['membranes_per_pressure_vessel']]                                               
        self.recovery_rate = parameters[TPN['recovery_rate_percent']] / 100
        self.membrane_flux_literperm2perh = parameters[TPN['membrane_flux_lmh']]
        self.membrane_area_m2 = parameters[TPN['membrane_area_m2']]
        self.operating_pressure_bar = parameters[
            TPN['operating_pressure_bar']]
        self.power_efficiency_pump = parameters[
            TPN['power_efficiency_of_pumps']] / 100  # noqa, E501
        self.vessels_per_unit = parameters[
            TPN['pressure_vessels_per_unit']]
        self.pressure_vessel_orientation = parameters[
            TPN['pressure_vessel_orientation']]  # noqa, E501
        self.flow_per_unit_m3perh = (
            self.flow_per_lane_m3perh / (self.units_per_lane - 1))  # account for backwash
        self.permeate_flow_per_unit_m3perh = (
            self.flow_per_unit_m3perh * self.recovery_rate)
        self.area_per_unit_m2 = calculate_membrane_vessel_area__m2(
            pressure_vessel_orientation=self.pressure_vessel_orientation,
            membranes_per_vessel=self.membranes_per_vessel,
            vessels_per_unit=self.vessels_per_unit,
        )

    def get_kpi(self, kpi: str) -> float:
        """Get the value for a KPI"""
        function_name = get_value_of_dictionary_with_lower_key_str(
            TECH_KPI_MAPPINGS, kpi)
        if function_name is not None:
            return getattr(self, function_name)
        else:
            raise ValueError(
                f"KPI '{kpi}' not implemented for {self.__class__.__name__}.")

    def get_kpi_dict(self):
        if kpi_list:
            return {kpi: self.get_kpi(kpi=kpi) for kpi in kpi_list}        
        return {kpi: self.get_kpi(kpi=kpi) for kpi in TECH_KPI_MAPPINGS.keys()}

    def footprint_area__m2(self) -> float:
        # including 20% extra space for piping and access
        return np.ceil(1.2 * self.area_per_unit_m2 * self.number_of_units)

    def footprint_area_for_chemicals__m2(self) -> float:
        return 0.0  # No chemicals used in Membrane Filtration

    def daily_mass_of_chemicals__kg(self) -> float:
        return 0.0  # No chemicals used in Membrane Filtration
    
    def chemical_solution_concentration__mg_per_l(self) -> float:
        return 0.0  # No chemicals used in Membrane Filtration

    def hydraulic_headloss__bar(self) -> float:
        return self.operating_pressure_bar + 0.5  # including fouling headloss

    def power__kw(self) -> float:
        flow_m3_per_s = (
            self.permeate_flow_per_unit_m3perh / 3600) * self.number_of_units
        head_m = bar_to_meters_of_water(self.hydraulic_headloss__bar())
        power_watts = (
            DENS_WATER_KG_PER_M3 * GRAVITY_M_PER_S2 * head_m * flow_m3_per_s
        )
        return power_watts / (1000 * self.power_efficiency_pump)  # to kW

    def daily_energy_consumption__kwh(self) -> float:
        return self.power__kw() * 24  # Assuming continuous operation

    def co2_emissions__kg_co2_eq_per_m3(self) -> float:
        pass  # Placeholder for CO2 emissions calculation


class IntakePump(TreatmentKPI):
    """KPI calculations for an Intake Pump treatment unit."""
    def __init__(
            self,
            parameters: dict,
            performance_indicators: dict,
            design_parameters: dict,
    ):
        self.flow_m3perh = performance_indicators.get('nominal flow', None)
        self.units_per_lane = design_parameters.get(
            TPN['units_per_lane'], 1)
        self.lanes = design_parameters.get('number of lanes', 1)
        self.pipe_diameter_m = parameters[TPN['pipe_diameter_m']]
        self.pipe_length_m = parameters[TPN['pipe_length_m']]
        self.pipe_roughness = parameters[TPN['pipe_roughness']]
        self.power_efficiency = parameters[TPN['power_efficiency']] / 100
        self.motor_efficiency = parameters[TPN['motor_efficiency']] / 100
        self.level_difference_m = parameters[TPN['level_difference_m']]

    def get_kpi(self, kpi: str) -> float:
        """Get the value for a KPI"""
        function_name = get_value_of_dictionary_with_lower_key_str(
            TECH_KPI_MAPPINGS, kpi)
        if function_name is not None:
            return getattr(self, function_name)
        else:
            raise ValueError(
                f"KPI '{kpi}' not implemented for {self.__class__.__name__}.")

    def get_kpi_dict(self, kpi_list=None):
        if kpi_list:
            return {kpi: self.get_kpi(kpi=kpi) for kpi in kpi_list}        
        return {kpi: self.get_kpi(kpi=kpi) for kpi in TECH_KPI_MAPPINGS.keys()}

    def footprint_area__m2(self) -> float:
        # TODO: add formula with Greg
        return 5.0  # Assumed constant footprint area for intake pump

    def footprint_area_for_chemicals__m2(self) -> float:
        return 0.0  # No chemicals used in Intake Pump

    def daily_mass_of_chemicals__kg(self) -> float:
        return 0.0  # No chemicals used in Intake Pump

    def chemical_solution_concentration__mg_per_l(self) -> float:
        return 0.0  # No chemicals used in Intake Pump

    def hydraulic_headloss__bar(self) -> float:
        # Calculate headloss due to friction in the pipe
        # TODO: verify formula with Greg.
        reynolds_number = reynolds_number_pipe(
            flow_m3perh=self.flow_m3perh,
            pipe_diameter_m=self.pipe_diameter_m,
        )
        friction_factor = friction_factor_pipe(
            reynolds_number_pipe=reynolds_number,
            pipe_roughness=self.pipe_roughness,
            pipe_diameter_m=self.pipe_diameter_m,
        )
        headloss_bar = calculate_pressure_drop_pipe(
            flow_m3perh=self.flow_m3perh,
            pipe_diameter_m=self.pipe_diameter_m,
            pipe_length_m=self.pipe_length_m,
            friction_factor=friction_factor,
        )
        headloss_bar += meters_of_water_to_bar(self.level_difference_m)
        return 1.15 * headloss_bar  # 15% safety factor??

    def power__kw(self) -> float:
        flow_m3_per_s = self.flow_m3perh / 3600
        total_dynamic_head_m = bar_to_meters_of_water(
            self.hydraulic_headloss__bar())
        # In Greg's notes, there is an additional factor of  0.000012?
        power_watts = (
            DENS_WATER_KG_PER_M3 * GRAVITY_M_PER_S2 *
            total_dynamic_head_m * flow_m3_per_s
        )
        total_efficiency = self.power_efficiency * self.motor_efficiency
        return power_watts / (1000 * total_efficiency)  # to kW

    def daily_energy_consumption__kwh(self) -> float:
        return self.power__kw() * 24  # Assuming continuous operation

    def co2_emissions__kg_co2_eq_per_m3(self) -> float:
        pass  # Placeholder for CO2 emissions calculation


class CleanWaterStorageTank(TreatmentKPI):
    """KPI calculations for a Clean Water Storage Tank treatment unit."""
    def __init__(
            self,
            parameters: dict,
            performance_indicators: dict,
            design_parameters: dict,
    ):
        self.tank_height_m = parameters[TPN['tank height']]
        self.retention_time_hrs = parameters[TPN['retention_time_hr']]
        self.lanes = design_parameters.get('number of lanes', 1)
        self.units_per_lane = design_parameters.get(TPN['units_per_lane'], 1)
        self.number_of_units = self.units_per_lane * self.lanes
        self.flow_m3perh = performance_indicators.get(
            'nominal flow rate (m3/hr)', None)
        self.unit_volume_m3 = (
            self.retention_time_hrs * self.flow_m3perh) / (
            3600 * self.number_of_units)
        self.unit_area_m2 = calculate_unit_area_tank(
            unit_volume_m3=self.unit_volume_m3,
            unit_height_m=self.tank_height_m)
        
    def get_kpi(self, kpi: str) -> float:
        """Get the value for a KPI"""
        function_name = get_value_of_dictionary_with_lower_key_str(
            TECH_KPI_MAPPINGS, kpi)
        if function_name is not None:
            return getattr(self, function_name)
        else:
            raise ValueError(
                f"KPI '{kpi}' not implemented for {self.__class__.__name__}.")

    def get_kpi_dict(self, kpi_list=None):
        if kpi_list:
            return {kpi: self.get_kpi(kpi=kpi) for kpi in kpi_list}
        return {kpi: self.get_kpi(kpi=kpi) for kpi in TECH_KPI_MAPPINGS.keys()}

    def footprint_area__m2(self) -> float:
        return np.ceil(self.unit_area_m2 * self.units_per_lane * self.lanes)

    def footprint_area_for_chemicals__m2(self) -> float:
        return 0.0  # No chemicals used in Clean Water Storage Tank

    def daily_mass_of_chemicals__kg(self) -> float:
        return 0.0  # No chemicals used in Clean Water Storage Tank

    def chemical_solution_concentration__mg_per_l(self) -> float:
        return 0.0  # No chemicals used in Clean Water Storage Tank

    def hydraulic_headloss__bar(self) -> float:
        return 0.1  # TODO: modify with Greg

    def power__kw(self) -> float:
        return 0.0  # No power used in Clean Water Storage Tank

    def daily_energy_consumption__kwh(self) -> float:
        return 0.0  # No power used in Clean Water Storage Tank

    def co2_emissions__kg_co2_eq_per_m3(self) -> float:
        return 0.0  # Placeholder for CO2 emissions calculation


class RapidSandSingleMediumFiltration(TreatmentKPI):
    """KPI calculations for a Rapid Sand Filtration treatment unit."""
    # TODO: (Greg) check the Excel file and fix/modify equations!!
    def __init__(
            self,
            parameters: dict,
            performance_indicators: dict,
            design_parameters: dict,
    ):
        self.flow_m3perh = performance_indicators.get(
            'nominal flow rate (m3/hr)', None)
        self.lanes = design_parameters.get('number of lanes', 1)
        self.flow_per_lane_m3perh = calculate_flow_per_lane(
            self.lanes, self.flow_m3perh)
        self.filtration_rate_m3_per_m2_per_h = parameters[
            TPN['filtration_rate_m3_per_m2_per_h']]
        self.unit_area_m2 = (
            self.flow_per_lane_m3perh /
            self.filtration_rate_m3_per_m2_per_h)
        self.unit_depth_m = parameters[TPN['filter_bed_depth_m']]
        self.unit_volume_m3 = self.unit_area_m2 * self.unit_depth_m

    def get_kpi(self, kpi: str) -> float:
        """Get the value for a KPI"""
        function_name = get_value_of_dictionary_with_lower_key_str(
            TECH_KPI_MAPPINGS, kpi)
        if function_name is not None:
            return getattr(self, function_name)
        else:
            raise ValueError(
                f"KPI '{kpi}' not implemented for {self.__class__.__name__}.")

    def get_kpi_dict(self, kpi_list=None):
        if kpi_list:
            return {kpi: self.get_kpi(kpi=kpi) for kpi in kpi_list}
        return {kpi: self.get_kpi(kpi=kpi) for kpi in TECH_KPI_MAPPINGS.keys()}

    def footprint_area__m2(self) -> float:
        return np.ceil(self.unit_area_m2 * self.lanes)

    def footprint_area_for_chemicals__m2(self) -> float:
        return 0.0  # No chemicals used in Rapid Sand Filtration

    def daily_mass_of_chemicals__kg(self) -> float:
        return 0.0  # No chemicals used in Rapid Sand Filtration
    
    def chemical_solution_concentration__mg_per_l(self) -> float:
        return 0.0  # No chemicals used in Rapid Sand Filtration

    def hydraulic_headloss__bar(self) -> float:
        return 1.0  # TODO: verify with Greg

    def power__kw(self) -> float:
        return -99.0  # TODO: Greg to provide formula

    def daily_energy_consumption__kwh(self) -> float:
        return self.power__kw() * 24  # Assuming continuous operation
    
    def co2_emissions__kg_co2_eq_per_m3(self) -> float:
        pass  # Placeholder for CO2 emissions calculation