import numpy as np

from drinq.utils.treatmentkpi import (
    MicroStrainer,
    Strainer,
    CascadeMixerCoagulationDosing, 
    CoagulationDynamicMixing,
    ChlorineDisinfection,
    ChloramineDisinfection,
    ChainScrapedSedimentation,
    MembraneFiltration,
    calculate_water_demand_m3hr_for_population,
    calculate_flow_per_unit
)

# ***Calculate daily nominal flow in m3/day***
# See for variance and standard deviation calculation:
# https://nicoco007.github.io/Propagation-of-Uncertainty-Calculator/


def stdev(variance: float):
    return float(np.sqrt(variance))


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


def technology_selector(
    stage: str,
    technology_options: list[str],
) -> str | None:
    """Select technology based on performance indicators.

    Args:
        stage (str): treatment stage
        technology_options (list[str]): list of technology options
        performance_indicators (dict[str, float | int]): performance indicators

    Returns:
        str | None: selected technology or None if no selection is made
    """
    selected_technology = None
    match stage.lower():
        case 'screening':
            for technology in technology_options:
                match technology.lower():
                    case 'strainer':
                        selected_technology = technology
                    case _:
                        pass
        case 'algae screening':
            for technology in technology_options:
                match technology.lower():
                    case 'micro strainer':
                        selected_technology = technology
                    case _:
                        pass
        case 'coagulation':
            for technology in technology_options:
                match technology.lower():
                    case str(technology) if (
                        'coagulant dosing' and 'dynamic mixing'
                        ) in technology:
                        selected_technology = technology
                    case _:
                        pass
        case 'flocculation':
            for technology in technology_options:
                match technology.lower():
                    case 'dynamic mixer':
                        selected_technology = technology
                    case _:
                        pass
        case _:
            pass
    return selected_technology


class TechnologyPerformanceCalculator:
    treatmentplant_id: int
    stages: list[str]  # names of stages
    technologies: list[str]  # names of technologies
    tech_parameters: dict[str, dict[str, float | int]]  # tech: {parameter_id: value}
    design_parameters: dict[str, float | int]  # plant parameter_id: value
    waterquality_parameters: dict[str, float | int]  # waterqual parameter_id: value
    plant_kpis: dict[str, float | int]  # plant performance indicators
    tech_kpinames: list[str]  # technology performance indicators
    digested_tech_parameter_list: dict[str, list[str]]  # technology: [property names]

    def __init__(
        self,
        treatmentplant_id: int, 
        technologies: list[str],
        stages: list[str],
        design_parameters: dict[str, float | int],
        plant_kpis: dict[str, float | int] = dict(),
        tech_parameters: dict[str, dict[str, float | int]] = dict(),
        waterquality_parameters: dict[str, dict[str, float | int]] = dict(),
        tech_kpinames: list[str] = None,
        digested_tech_parameter_list: dict[str, list[str]] = None,
    ):
        self.treatmentplant_id = treatmentplant_id
        self.tech_parameters = tech_parameters
        self.design_parameters = design_parameters
        self.technologies = technologies
        self.waterquality_parameters = waterquality_parameters
        self.stages = stages
        self.plant_kpis = plant_kpis
        self.tech_kpinames = tech_kpinames
        if tech_kpinames is None:
            self.tech_kpis = {
                technology: dict() for technology in technologies}
        else:
            self.tech_kpis = {
                technology: {kpi: None for kpi in tech_kpinames}
                for technology in technologies}
        self.digested_tech_parameter_list = digested_tech_parameter_list
        self.summed_kpis = dict()

    def calculate_kpi(
        self,
    ):
        parameters = self.tech_parameters
        stages = self.stages
        technologies = self.technologies
        design_parameters = self.design_parameters
        wq_parameters = self.waterquality_parameters
        plant_kpis = self.plant_kpis
        tech_kpilist = {"kpi_list": self.tech_kpinames}

        footprint_area = None
        if technologies is None or stages is None:
            raise ValueError("Technologies and stages must be provided.")
        footprint_area = {tech: None for tech in technologies}
        for stage in stages:
            for technology in technologies:
                digest_property_list = self.digested_tech_parameter_list.get(technology, None)  # noqa, E501
                if len(digest_property_list) == 0:
                    digest_property_list = None
                tech_kwargs = {
                    'parameters': parameters[technology],
                    'plant_kpis': plant_kpis,
                    'design_parameters': design_parameters,
                    'wq_parameters': wq_parameters[technology],
                    'digest_parameter_list': digest_property_list,
                }
                match stage.lower():
                    case 'algae screening':
                        match technology.lower():
                            case 'micro strainer':
                                microstrainer = MicroStrainer(**tech_kwargs)  # noqa, E501
                                self.tech_kpis[technology] = microstrainer.get_kpi_dict(**tech_kpilist)  # noqa, E501
                                self.tech_parameters[technology] = microstrainer.parameters  # noqa, E501
                            case 'strainer':
                                strainer = Strainer(**tech_kwargs)
                                self.tech_kpis[technology] = strainer.get_kpi_dict(**tech_kpilist)  # noqa, E501
                                self.tech_parameters[technology] = strainer.parameters  # noqa, E501
                            case _:
                                pass
                    case 'coagulation':
                        match technology.lower():
                            case str(technology) if (
                                'coagulant dosing' and 'dynamic mixing'
                                ) in technology:
                                coag_dynmixer = CoagulationDynamicMixing(**tech_kwargs)  # noqa, E501
                                self.tech_kpis[technology] = coag_dynmixer.get_kpi_dict()  # noqa, E501
                            case _:
                                pass
                    case 'omp removal':
                        match technology.lower():
                            case str(technology) if ('nanofiltration') in technology.lower():  # noqa, E501
                                membr_filtration = MembraneFiltration(**tech_kwargs)  # noqa, E501
                                self.tech_kpis[technology] = membr_filtration.get_kpi_dict()  # noqa, E501
                            case _:
                                pass

        if footprint_area is None:
            raise ValueError("Not possible to calculate footprint area (m2).")
        return footprint_area

    def sum_kpis(
        self,
        allowed_kpis: list[str] = None,
    ) -> dict[str, float | int]:
        """Sum KPI values across all technologies.

        Returns:
            dict[str, float | int]: summed KPI values
        """
        summed_kpis = {}
        if allowed_kpis is None:
            allowed_kpis = [
                'area',
                'mass',
                'energy consumption',
                'power',
                'head loss',
                'emissions',
            ]
        for _, kpis in self.tech_kpis.items():
            for kpi_name, kpi_value in kpis.items():
                if kpi_name not in allowed_kpis:
                    continue
                if kpi_value is not None:
                    if kpi_name in summed_kpis:
                        summed_kpis[kpi_name] += kpi_value
                    else:
                        summed_kpis[kpi_name] = kpi_value
        self.summed_kpis = summed_kpis
        # return summed_kpis


class TreatmentPlantPerformanceCalculator:
    treatmentplant_id: int
    stages: list[str]  # names of stages
    technologies: list[str]  # names of technologies
    design_parameters: dict[str, float | int]  # parameter_id: value in m3/day
    plant_kpis: dict[str, float | int]  # plant performance indicators

    def __init__(
        self,
        treatmentplant_id: int, 
        design_parameters: dict[str, float | int],
        technologies: list[str] = None,
        stages: list[str] = None,
        plant_kpis: dict[str, float | int] = None
    ):
        self.treatmentplant_id = treatmentplant_id
        self.design_parameters = design_parameters
        self.technologies = technologies
        self.stages = stages
        self.plant_kpis = plant_kpis

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
        """Purpose: Calculate costs based on design parameters.
        
        Args:
            plant_properties (dict[str, float], optional): Dictionary of plant 
                properties, where each key is a plant property name. 
                Defaults to None.
            cost_parameters (dict[str, dict], optional): Dictionary of cost 
                parameters for each technology. The keys of the dictionary 
                refer to technology names. Defaults to None.

        Note:
            The cost parameters dictionary for each technology should contain
            the parameters 'a', 'b', and 'c' for the quadratic cost function.
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

    # TODO: this will be moved to the specific class of the filter technologies
    # def get_filterarea(
    #     self,
    #     filter_technology,
    #     units_per_lane: int = 1,
    #     nominal_flow: float | None = None,
    # ):

    #     # Input parameters
    #     parameters = self.design_parameters
    #     lanes = parameters.get('number of lanes', 1)
    #     filter_area, filter_area_per_unit = None, None
    #     if nominal_flow is None:
    #         nominal_flow = self.get_nominal_flow_m3hr()

    #     # Calculate surface loading rate based on filter technology
    #     match filter_technology:
    #         case str(tech) if ('single medium' or 'granular activated carbon') in tech:  # noqa, E501
    #             surface_loading_rate = 10
    #         case str(tech) if 'dual media' in tech:
    #             surface_loading_rate = 15  # m3/h/m2 average filtration rate for a dual media filtration  # noqa, E501
    #         case str(tech) if 'moving bed' in tech:
    #             surface_loading_rate = 8.5  # m3/h/m2 average filtration rate for moving bed filtration  # noqa, E501
    #         case _:
    #             surface_loading_rate = None

    #     # Calculate filter area
    #     if surface_loading_rate is not None:
    #         filter_area = nominal_flow / surface_loading_rate
    #         filter_area_per_lane = filter_area / lanes
    #         filter_area_per_unit = filter_area_per_lane / units_per_lane

    #     return filter_area, filter_area_per_unit

