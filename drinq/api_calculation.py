import numpy as np

# ***Calculate daily nominal flow in m3/day***
# See for variance and standard deviation calculation:
# https://nicoco007.github.io/Propagation-of-Uncertainty-Calculator/


def stdev(variance: float):
    return float(np.sqrt(variance))


def lppd_to_m3phr(flow_in_liter_per_day: float):
    return flow_in_liter_per_day / 1000 / 24


def calculate_flow_per_lane(
    lanes: int,
    flow: float,
) -> float:
    return flow / lanes


def calculate_flow_per_unit(
    units: int,
    flow_per_lane: float
) -> float:
    return flow_per_lane / units


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


def var_population(
    delta_population: float,
    consumption_lppd: float,
    leakage_factor: float
) -> float:
    var_p = (
        (consumption_lppd/24000 * (leakage_factor + 1)) * delta_population)**2
    return var_p


def var_leakage_factor(
    delta_leakage_factor: float,
    population_persons: float,
    consumption_lppd: float,
    demand_industry: float = 0.,
    demand_agriculture: float = 0.,
):
    var_L = (
        (population_persons/24000 * consumption_lppd + demand_agriculture
         + demand_industry) * delta_leakage_factor
        )**2
    return var_L


def var_demand_largescaleconsumption(
    delta_demand_largescaleconsumption: float,
    leakage_factor: float,
):
    var_demand_lscons = (
        (leakage_factor + 1) * delta_demand_largescaleconsumption)**2
    return var_demand_lscons


def var_consumption_lppd(
    delta_consumption_lppd: float,    
    population_persons: float,
    leakage_factor: float,
):
    var_cons = (
        (population_persons/24000 * (1 + leakage_factor)
         ) * delta_consumption_lppd)**2
    return var_cons


def var_total_water_demand(
    delta_population: float,
    delta_leakage_factor: float,
    delta_consumption_lppd: float,
    delta_demand_largescaleconsumption: float,
    leakage_factor: float,
    population_persons: int | float,
    consumption_lppd: float,
    demand_largescaleconsumption: float | None = None,
) -> float:
    if demand_largescaleconsumption is None:
        demand_largescaleconsumption = 0.
    var_persons = var_population(
        delta_population, consumption_lppd, leakage_factor)
    var_leakage = var_leakage_factor(
        delta_leakage_factor,
        population_persons,
        consumption_lppd,
        demand_largescaleconsumption)   
    var_demand_lscons = var_demand_largescaleconsumption(
        delta_demand_largescaleconsumption,
        leakage_factor)
    var_cons_lppd = var_consumption_lppd(
        delta_consumption_lppd, population_persons, leakage_factor)
    return var_persons + var_leakage + var_demand_lscons + var_cons_lppd


class TreatmentPlantPerformanceCalculator:
    treatmentplant_id: int
    stages: list[str]  # names of stages
    technologies: list[str]  # names of technologies
    design_parameters: dict[str, float | int]  # parameter_id: value in m3/day

    def __init__(
        self,
        treatmentplant_id: int, 
        design_parameters: dict[str, float | int],
        technologies: list[str] = None,
        stages: list[str] = None
    ):
        self.treatmentplant_id = treatmentplant_id
        self.design_parameters = design_parameters
        self.technologies = technologies
        self.stages = stages

    def get_nominal_flow_m3hr(
        self,
    ):
        parameters = self.design_parameters
        population_persons = parameters.get('population persons', None)
        avg_consumption_lppd = parameters.get(
            'average consumption (lppd)', None)
        largescaleconsumption_m3pd = parameters.get(
            'large-scale consumption (m3/day)', 0.)
        leakage_factor = parameters.get('leakage factor', None)
        peak_demand_factor = parameters.get('peak demand factor', None)
        if (
            population_persons is None or avg_consumption_lppd is None
        ) or leakage_factor is None or peak_demand_factor is None:
            raise ValueError(
                "Population persons, peak demand factor, average consumption "
                " and leakage factor must be provided.")
        flow_population = calculate_water_demand_m3hr_for_population(
            population_persons=int(population_persons),
            avg_consumption_lppd=avg_consumption_lppd)
        expected_flow = flow_population + largescaleconsumption_m3pd/24
        return expected_flow * (1 + leakage_factor) * peak_demand_factor

    def get_constructioncosts(
        self,
        plant_properties: dict[str, float] = None,
        cost_parameters: dict[str, dict] = None,
    ) -> float:
        """Purpose: Calculate costs based on design parameters and nominal
        flow.
        
        Args:
            plant_properties (dict[str, float], optional): Dictionary of plant 
                properties, where each key is a plant property name. 
                Defaults to None.
            cost_parameters (dict[str, dict], optional): Dictionary of cost 
                parameters for each technology. The keys of the dictionary 
                refer to technology names. Defaults to None.
        """
        if cost_parameters is None:
            raise ValueError("Cost parameters must be provided.")
        if plant_properties is None:
            raise ValueError("Plant properties must be provided.")
        # parameters = self.design_parameters
        # plc_costs = parameters.get('PLC costs (EUR)', 0.)
        # personnel_costs = parameters.get('personnel costs (EUR)', 0.)

        costs = 0.
        if self.technologies:
            for technology in self.technologies:
                x_value = 0.
                constrcost_params = cost_parameters[technology]
                if constrcost_params is not None:
                    a, b, c = (
                        constrcost_params.get('a', 0.),
                        constrcost_params.get('b', 0.),
                        constrcost_params.get('c', 0.),
                    )
                    plant_property = constrcost_params.get('plantproperty', None)  # noqa, E501
                    technology_property = constrcost_params.get(
                        'technologyproperty', None)
                    plantproperty_value = constrcost_params.get(
                        'plantproperty_value', 0)
                    technologyproperty_value = constrcost_params.get(
                        'technologyproperty_value', 0)
                    if plantproperty_value:
                        x_value = plantproperty_value
                    if technologyproperty_value:
                        x_value = technologyproperty_value
                    constr_costs = a*x_value**2 + b*x_value + c
                    costs += constr_costs
        costs = 1000 * round(abs(costs)/1000.0, 2)
        return costs

    def get_filterarea(
        self,
        filter_technology,
        units_per_lane: int = 1,
        nominal_flow: float | None = None,
    ):

        # Input parameters
        parameters = self.design_parameters
        lanes = parameters.get('number of lanes', 1)
        filter_area, filter_area_per_unit = None, None
        if nominal_flow is None:
            nominal_flow = self.get_nominal_flow_m3hr()

        # Calculate surface loading rate based on filter technology
        match filter_technology:
            case str(tech) if ('single medium' or 'granular activated carbon') in tech:  # noqa, E501
                surface_loading_rate = 10
            case str(tech) if 'dual media' in tech:
                surface_loading_rate = 15  # m3/h/m2 average filtration rate for a dual media filtration  # noqa, E501
            case str(tech) if 'moving bed' in tech:
                surface_loading_rate = 8.5  # m3/h/m2 average filtration rate for moving bed filtration  # noqa, E501
            case _:
                surface_loading_rate = None

        # Calculate filter area
        if surface_loading_rate is not None:
            filter_area = nominal_flow / surface_loading_rate
            filter_area_per_lane = filter_area / lanes
            filter_area_per_unit = filter_area_per_lane / units_per_lane

        return filter_area, filter_area_per_unit

