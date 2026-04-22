import numpy as np
import re
import logging
from dataclasses import dataclass

from drinq.utils.treatmentkpi import (
    MicroStrainer,
    Strainer,
    CascadeMixerCoagulationDosing, 
    CoagulationDynamicMixing,
    ChlorineDisinfection,
    ChloramineDisinfection,
    ChainScrapedSedimentation,
    SludgeBlanketClarifier,
    AirFlotationDAF,
    GranularActivatedCarbonFiltration,
    PowderedActivatedCarbonFiltration,
    PelletSoftening,
    CationIonExchange,
    RapidSandDoubleMediumFiltration,
    RapidSandSingleMediumFiltration,
    RapidSandPressurizedVesselFiltration,
    MembraneFiltration,
    calculate_water_demand_m3hr_for_population,
    calculate_flow_per_unit,
    INPUT_WQPARAMETER_KEY,
    TARGET_WQPARAMETER_KEY,
    NOMINAL_FLOW_RATE_NAME,
)
from drinq.utils.financial_costs import (
    construction_costs_total,
    total_investment_costs_peryear,
    energy_costs_perm3,
    energy_costs_peryear,
    operation_maintenance_costs_peryear,
    chemical_costs_peryear,
    levelized_cost_of_water
)

# NOTE: TECHKPI names should match those in the database!
TECHKPI_ENERGYCONSUMPTION_KWHRPERDAY = 'daily energy consumption'
TECHKPI_FOOTPRINT_AREA_M2 = 'footprint area'
TECHKPI_MASS_OF_CHEMICALS = 'mass of chemicals'
TECHKPI_POWER_KW = 'power'
TECHKPI_HEADLOSS_BAR = 'head loss'
TECHKPI_CO2_EMISSIONS_KGPERM3 = 'CO2 equivalent emissions'

TODRINQ_KPINAMES_TOSUM = [
    TECHKPI_FOOTPRINT_AREA_M2,
    TECHKPI_ENERGYCONSUMPTION_KWHRPERDAY,
    TECHKPI_POWER_KW,
    TECHKPI_HEADLOSS_BAR,
    TECHKPI_CO2_EMISSIONS_KGPERM3,  # NOT WORKING YET
]

# Below follow the database names for the KPIs
KPI_NOMINAL_FLOW_M3PERH = NOMINAL_FLOW_RATE_NAME
KPI_ENERGY_CONSUMPTION_KWHRPERDAY = 'energy consumption (kwhrperday)'
KPI_ENERGY_CONSUMPTION_KWHRPERM3 = 'specific energy consumption'
KPI_FOOTPRINT_AREA_M2 = 'footprint area'
KPI_SPECIFIC_CONSTRUCTION_COSTS = 'construction costs'
KPI_INVESTMENT_COSTS_ANN = 'investment costs (annual)'
KPI_OPER_AND_MAINT_COSTS_ANN = 'operation and maintenance costs (annual)'
KPI_CO2_EMISSIONS_KGPERM3 = 'CO2 equivalent emissions'

logger = logging.getLogger(__name__)

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


# TODO: implement in views.py
@dataclass
# Name WaterQualityParameterData or WaterqualityParameterKPI. Not to be
# confused with the db table.
class WaterqualityParameterData:
    input_value: float | None = None
    target_value: float | None = None
    name: str | None = None
    input_label: str = INPUT_WQPARAMETER_KEY
    target_label: str = TARGET_WQPARAMETER_KEY

    def to_db_kpi_dict(
            self,
            is_input_parameter: bool = False,
            is_target_parameter: bool = False,
        ) -> dict[str, float | int | None]:

        if self.name is None:
            return {}
        else:
            if is_input_parameter and is_target_parameter:
                raise ValueError(
                    "A water quality parameter cannot be both an input and target parameter.")
            elif not (is_input_parameter or is_target_parameter):
                raise ValueError(
                    "A water quality parameter must be either an input or target parameter.")
            elif is_input_parameter:
                return {
                    self.name: self.input_value,
                }
            elif is_target_parameter:
                return {
                    self.name: self.target_value,
                }

    def to_dict(self) -> dict[str, float | int | None]:
        if self.name is None:
            return {}
        return {
            self.name: {
                self.input_label: self.input_value,
                self.target_label: self.target_value,
            }
        }

    def __repr__(self):
        if self.name is None:
            return "No water quality parameter(s)"
        return (
            f"Water quality indicator {self.name}: (input) {self.input_value:.2f}"
            f", (target) {self.target_value:.2f}")

    def __str__(self):
        if self.name is None:
            return "No water quality parameter(s)"
        return f"{self.name}, input: {self.input_value}; output: {self.target_value}"  # noqa, E501


class TechnologyPerformanceCalculator:
    treatmentplant_id: int
    stages: list[str]  # names of stages
    technologies: list[str]  # names of technologies
    tech_parameters: dict[str, dict[str, float | int]]  # tech: {parameter_id: value}
    design_parameters: dict[str, float | int]  # plant parameter_id: value
    waterquality_parameters: dict[str, dict[str, float | int]]  # tech: wq_dict
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
        self.tech_kpis = {technology: None for technology in technologies}
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

        if technologies is None or stages is None:
            raise ValueError("Technologies and stages must be provided.")
        for stage in stages:
            for technology in technologies:
                digest_property_list = self.digested_tech_parameter_list.get(technology, None)  # noqa, E501
                if digest_property_list is None:
                    digest_property_list = []
                tech_wq_parameters = wq_parameters.get(technology, {})
                tech_kwargs = {
                    'parameters': parameters[technology],
                    'plant_kpis': plant_kpis,
                    'design_parameters': design_parameters,
                    'wq_parameters': tech_wq_parameters,
                    'digest_parameter_list': digest_property_list,
                }
                match stage.lower():
                    case 'algae screening':
                        match technology.lower():
                            case 'micro strainer':
                                microstrainer = MicroStrainer(**tech_kwargs)  # noqa, E501
                                self.tech_kpis[technology] = microstrainer.get_kpi_dict(**tech_kpilist)  # noqa, E501
                                self.tech_parameters[technology] = microstrainer.parameters  # noqa, E501
                            # case 'strainer':
                            #     strainer = Strainer(**tech_kwargs)
                            #     self.tech_kpis[technology] = strainer.get_kpi_dict(**tech_kpilist)  # noqa, E501
                            #     self.tech_parameters[technology] = strainer.parameters  # noqa, E501

                    case 'screening':
                        if 'strainer' in technology.lower():
                            strainer = Strainer(**tech_kwargs)
                            self.tech_kpis[technology] = strainer.get_kpi_dict(**tech_kpilist)  # noqa, E501
                            self.tech_parameters[technology] = strainer.parameters  # noqa, E501
                    case 'coagulation':
                        if ('coagulant dosing' and 'dynamic mixing') in technology.lower():
                            coag_dynmixer = CoagulationDynamicMixing(**tech_kwargs)  # noqa, E501
                            self.tech_kpis[technology] = coag_dynmixer.get_kpi_dict()  # noqa, E501
                            self.tech_parameters[technology] = coag_dynmixer.parameters  # noqa, E501                            
                        elif ('cascade' and 'coagulant dosing') in technology.lower():
                            cascade_mixer = CascadeMixerCoagulationDosing(**tech_kwargs)  # noqa, E501
                            self.tech_kpis[technology] = cascade_mixer.get_kpi_dict(**tech_kpilist)  # noqa, E501
                            self.tech_parameters[technology] = cascade_mixer.parameters  # noqa, E501
                    case 'floc removal':
                        if 'sludge blanket' in technology.lower():
                            sludgeblanket_cl = SludgeBlanketClarifier(**tech_kwargs)  # noqa, E501
                            self.tech_kpis[technology] = sludgeblanket_cl.get_kpi_dict(**tech_kpilist)  # noqa, E501
                            self.tech_parameters[technology] = sludgeblanket_cl.parameters  # noqa, E501
                        elif 'chain scraped sedimentation' in technology.lower():  # noqa, E501
                            chain_scraped_sed = ChainScrapedSedimentation(**tech_kwargs)  # noqa, E501
                            self.tech_kpis[technology] = chain_scraped_sed.get_kpi_dict(**tech_kpilist)  # noqa, E501
                            self.tech_parameters[technology] = chain_scraped_sed.parameters  # noqa, E501
                        elif 'flotation with saturated air' in technology.lower():
                            daf = AirFlotationDAF(**tech_kwargs)  # noqa, E501
                            self.tech_kpis[technology] = daf.get_kpi_dict(**tech_kpilist)  # noqa, E501
                            self.tech_parameters[technology] = daf.parameters  # noqa, E501
                    case 'submerged rapid sand filtration':
                        if ('rapid sand filtration' in technology.lower() and
                            'submerged' in technology.lower() and
                            'single' in technology.lower()):
                            rsf = RapidSandSingleMediumFiltration(**tech_kwargs)  # noqa, E501
                            self.tech_kpis[technology] = rsf.get_kpi_dict(**tech_kpilist)  # noqa, E501
                            self.tech_parameters[technology] = rsf.parameters  # noqa, E501
                        elif ('rapid sand filtration' in technology.lower() and
                              'submerged' in technology.lower() and
                              'double' in technology.lower()):  # noqa, E501
                            rsfd = RapidSandDoubleMediumFiltration(**tech_kwargs)  # noqa, E501
                            self.tech_kpis[technology] = rsfd.get_kpi_dict(**tech_kpilist)  # noqa, E501
                            self.tech_parameters[technology] = rsfd.parameters  # noqa, E501
                        elif ('rapid sand filtration' in technology.lower() and
                              'submerged' in technology.lower() and
                              'pressurized' in technology.lower()):  # noqa, E501
                            rsfp = RapidSandPressurizedVesselFiltration(**tech_kwargs)  # noqa, E501
                            self.tech_kpis[technology] = rsfp.get_kpi_dict(**tech_kpilist)  # noqa, E501
                            self.tech_parameters[technology] = rsfp.parameters  # noqa, E501

                    case 'omp removal':
                        if ('nanofiltration') in technology.lower():  # noqa, E501
                            membr_filtration = MembraneFiltration(**tech_kwargs)  # noqa, E501
                            self.tech_kpis[technology] = membr_filtration.get_kpi_dict(**tech_kpilist)  # noqa, E501
                            self.tech_parameters[technology] = membr_filtration.parameters  # noqa, E501
                        elif ('granular activated carbon') in technology.lower():  # noqa, E501
                            gac_filtration = GranularActivatedCarbonFiltration(**tech_kwargs)  # noqa, E501
                            self.tech_kpis[technology] = gac_filtration.get_kpi_dict(**tech_kpilist)  # noqa, E501
                            self.tech_parameters[technology] = gac_filtration.parameters  # noqa, E501
                        elif ('powdered activated carbon') in technology.lower():  # noqa, E501
                            pac_filtration = PowderedActivatedCarbonFiltration(**tech_kwargs)  # noqa, E501
                            self.tech_kpis[technology] = pac_filtration.get_kpi_dict(**tech_kpilist)  # noqa, E501
                            self.tech_parameters[technology] = pac_filtration.parameters  # noqa, E501

                    case 'softening':
                        if ('pellet softening') in technology.lower():
                            pellet_softening = PelletSoftening(**tech_kwargs)  # noqa, E501
                            self.tech_kpis[technology] = pellet_softening.get_kpi_dict(**tech_kpilist)  # noqa, E501
                            self.tech_parameters[technology] = pellet_softening.parameters  # noqa, E501
                        elif ('cation exchange') in technology.lower():
                            ciex = CationIonExchange(**tech_kwargs)  # noqa, E501
                            self.tech_kpis[technology] = ciex.get_kpi_dict(**tech_kpilist)  # noqa, E501
                            self.tech_parameters[technology] = ciex.parameters  # noqa, E501
        print("-- Calculated technology KPIs:")
        for tech, kpis in self.tech_kpis.items():
            print(f"---- {tech}: {kpis}")
        
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
            allowed_kpis = TODRINQ_KPINAMES_TOSUM
        for _, kpis in self.tech_kpis.items():
            for kpi_name, kpi_value in kpis.items():
                for kpi in allowed_kpis:
                    if re.search(kpi, kpi_name) is None:
                        continue  # skip when kpi not in list
                    if kpi_value is not None:
                        if kpi_name in summed_kpis:
                            print(
                                f'-- Adding to summed KPI: {kpi_name}, tech: {_}')
                            if kpi_value is None:
                                logger.warning(
                                    f"---- Warning: None value for {kpi_name} in technology {_}, skipping addition to summed KPI.")  # noqa, E501
                                continue
                            if callable(kpi_value):
                                logger.error(
                                    f"---- Error: Callable value for {kpi_name} in technology {_}, skipping addition to summed KPI.")  # noqa, E501
                                raise ValueError(f"Callable value for {kpi_name} in technology {_} is not supported.")  # noqa, E501
                            summed_kpis[kpi_name] += kpi_value
                        else:
                            summed_kpis[kpi_name] = kpi_value
        self.summed_kpis = summed_kpis
        # return summed_kpis


@dataclass
class PlantKPI:
    name: str
    value: float | int | None
    name_in_dbtable: str | None = None

    def __post_init__(self):
        if self.name_in_dbtable is None:
            self.name_in_dbtable = self.name.lower().replace(" ", "_")

    def to_db_kpi_dict(self) -> dict[str, float | int | None]:
        return {
            self.name_in_dbtable: self.value,
        }

    def to_dict(self) -> dict[str, float | int | None]:
        return {
            self.name: self.value
        }

    def __repr__(self):
        return f"Treatment Plant KPI {self.name}): {self.value:.2f}"

    def __str__(self):
        return f"{self.name}: {self.value}"


class NominalFlowKPI(PlantKPI):
    name: str = KPI_NOMINAL_FLOW_M3PERH
    value: float | int | None = None

    def calculate_value(
        self,
        population_persons: int,
        avg_consumption_lppd: float,
        leakage_factor: float,
        peak_demand_factor: float,
        largescaleconsumption_m3pd: float = 0.,
    ) -> float:
        flow_population = calculate_water_demand_m3hr_for_population(
            population_persons=population_persons,
            avg_consumption_lppd=avg_consumption_lppd)
        expected_flow = flow_population + largescaleconsumption_m3pd/24
        self.value = expected_flow * (1 + leakage_factor) * peak_demand_factor
        return self.value


class FootprintAreaM2KPI(PlantKPI):
    name: str = TECHKPI_FOOTPRINT_AREA_M2
    value: float | int | None


class EnergyConsumptionPerDayKPI(PlantKPI):
    name: str = KPI_ENERGY_CONSUMPTION_KWHRPERDAY
    value: float | int | None


class EnergyConsumptionPerM3KPI(PlantKPI):
    name: str = 'specific energy consumption'
    value: float | int | None

    def calculate_value(
        self,
        energy_consumption_kwhperday: float,
        nominal_flow_m3perhr: float,
    ) -> float:
        if nominal_flow_m3perhr == 0:
            raise ValueError("Nominal flow (m3perh) cannot be zero.")
        nominal_flow_m3perday = nominal_flow_m3perhr * 24
        self.value = energy_consumption_kwhperday / nominal_flow_m3perday
        return self.value


class PowerKWKPI(PlantKPI):
    name: str = TECHKPI_POWER_KW
    value: float | int | None


class HeadLossBarKPI(PlantKPI):
    name: str = TECHKPI_HEADLOSS_BAR
    value: float | int | None


class MassOfChemicalsDailyKPI(PlantKPI):
    name: str = TECHKPI_MASS_OF_CHEMICALS
    value: float | int | None


class CO2EmissionsPerM3KPI(PlantKPI):
    name: str = TECHKPI_CO2_EMISSIONS_KGPERM3
    value: float | int | None


class EnergyCostsPerYearKPI(PlantKPI):
    name: str = 'energy costs (eur/year)'
    value: float | int | None

    def calculate_value(
        self,
        energy_costs_per_m3: float,
        yearly_water_production_m3: float,
    ) -> float:
        self.value = energy_costs_peryear(
            energy_costs_per_m3=energy_costs_per_m3,
            yearly_water_production_m3=yearly_water_production_m3,
        )
        return self.value


class OperAndMaintenanceCostsKPI(PlantKPI):
    name: str = KPI_OPER_AND_MAINT_COSTS_ANN
    value: float | int | None
    """
    Calculate the operational and maintenance costs per year.
    """

    def calculate_value(
        self,
        construction_costs: float,
        oper_maintenance_percentage: float,
    ) -> float:
        self.value = operation_maintenance_costs_peryear(
            construction_costs,
            oper_maintenance_percentage,
        )
        return self.value


class ConstructionCostsKPI(PlantKPI):
    name: str = KPI_SPECIFIC_CONSTRUCTION_COSTS
    value: float | int | None

    def calculate_value(
        self,
        construction_costs: float,
        construction_costs_percentage: float = 20,
        tail_costs_percentage: float = 5,
        general_facilities_costs_percentage: float = 5,
    ) -> float:
        self.value = construction_costs_total(
            construction_costs,
            construction_costs_percentage,
            tail_costs_percentage,
            general_facilities_costs_percentage,
        )
        return self.value


class InvestmentCostsYearKPI(PlantKPI):
    name: str = KPI_INVESTMENT_COSTS_ANN
    value: float | int | None

    def calculate_value(
        self,
        construction_costs_total: float,
        operation_maintenance_percentage: float,
        energy_cost_per_year: float,
        personnel_costs_per_year: float,
        chemical_costs_per_year: float,
        interest_rate: float,
        lifespan_years: int,
    ) -> float:
        # for the depreciation, the lifespan_years is used
        self.value = total_investment_costs_peryear(
            construction_costs_total=construction_costs_total,
            interest_rate=interest_rate,
            lifespan_years=lifespan_years,
            oper_maintenance_percentage=operation_maintenance_percentage,
            energy_costs_peryr=energy_cost_per_year,
            personnel_costs_peryr=personnel_costs_per_year,
            chemical_costs_peryr=chemical_costs_per_year,
        )
        return self.value


class LevelizedCostOfWaterKPI(PlantKPI):
    name: str = 'levelized cost of water (eur/m3)'
    value: float | int | None

    def calculate_value(
        self,
        total_investment_costs_peryear: float,
        yearly_water_production_m3: float,
    ) -> float:
        if yearly_water_production_m3 == 0:
            raise ValueError("Yearly water production (m3) cannot be zero.")
        self.value = levelized_cost_of_water(
            total_investment_costs_peryear,
            yearly_water_production_m3,
        )
        return self.value


class FootprintAreaKPI(PlantKPI):
    name: str = KPI_FOOTPRINT_AREA_M2
    value: float | int | None


@dataclass
class PlantKPICollection:
    kpis: dict[str, PlantKPI]

    def __init__(self, kpis: list[PlantKPI]):
        self.kpis = {kpi.name: kpi for kpi in kpis}

    def to_db_kpi_dict(self) -> dict[str, float | int | None]:
        db_kpi_dict = {}
        for kpi in self.kpis.values():
            db_kpi_dict.update(kpi.to_db_kpi_dict())
        return db_kpi_dict


class TreatmentPlantPerformanceCalculator:
    treatmentplant_id: int
    stages: list[str]  # names of stages
    technologies: list[str]  # names of technologies
    design_parameters: dict[str, float | int]  # parameter_id: value in m3/day
    plant_kpis: dict[str, float | int | None]  # plant performance indicators
    db_kpi_mapping: dict[str, str | None]  # database KPI names
    waterquality_parameters: dict[str, dict[str, float | int]] | None  # tech: wq_dict

    nominal_flow_m3perhr: NominalFlowKPI
    footprint_area_m2: FootprintAreaM2KPI
    energyconsumption_kwhrperday: EnergyConsumptionPerDayKPI
    energyconsumption_kwhrperm3: EnergyConsumptionPerM3KPI
    constructioncosts_eur: ConstructionCostsKPI
    investmentcosts_eur: InvestmentCostsYearKPI
    operation_maintenance_costs_peryear: OperAndMaintenanceCostsKPI
    head_loss_bar: HeadLossBarKPI
    # mass_of_chemicals_daily_kg: MassOfChemicalsDailyKPI
    power_kw: PowerKWKPI
    co2_emissions_kgperm3: CO2EmissionsPerM3KPI

    def __init__(
        self,
        treatmentplant_id: int,
        design_parameters: dict[str, float | int],
        technologies: list[str] = None,
        stages: list[str] = None,
        plant_kpis: dict[str, float | int] = None,
        db_kpi_mapping: dict[str, str | None] = None,
        waterquality_parameters: dict[str, dict[str, float | int]] = None,
    ):
        self.treatmentplant_id = treatmentplant_id
        self.design_parameters = design_parameters
        self.technologies = technologies
        self.stages = stages
        self.db_kpi_mapping = db_kpi_mapping
        if waterquality_parameters is None:
            waterquality_parameters = {}  # Initialize as empty dictionary
        self.waterquality_parameters = waterquality_parameters
        self.kpi_attr_mapping = {
            'nominal_flow_m3perhr': KPI_NOMINAL_FLOW_M3PERH,
            'footprint_area_m2': KPI_FOOTPRINT_AREA_M2,
            'energyconsumption_kwhrperday': KPI_ENERGY_CONSUMPTION_KWHRPERDAY,
            'energyconsumption_kwhrperm3': KPI_ENERGY_CONSUMPTION_KWHRPERM3,
            'constructioncosts_eur': KPI_SPECIFIC_CONSTRUCTION_COSTS,
            'investmentcosts_eur': KPI_INVESTMENT_COSTS_ANN,
            'head_loss_bar': TECHKPI_HEADLOSS_BAR,
            # 'mass_of_chemicals_daily_kg': TECHKPI_MASS_OF_CHEMICALS,
            'power_kw': TECHKPI_POWER_KW,
            'co2_emissions_kgperm3': TECHKPI_CO2_EMISSIONS_KGPERM3,
            'oper_and_maintenancecosts_eurperyear': KPI_OPER_AND_MAINT_COSTS_ANN,
        }

        # intermediate and final KPI results
        self.nominal_flow_m3perhr = NominalFlowKPI(
            name=KPI_NOMINAL_FLOW_M3PERH, value=None,
            name_in_dbtable=self.db_kpi_mapping.get(
                KPI_NOMINAL_FLOW_M3PERH, None))
        self.footprint_area_m2 = FootprintAreaM2KPI(
            name=KPI_FOOTPRINT_AREA_M2, value=None,
            name_in_dbtable=self.db_kpi_mapping.get(
                KPI_FOOTPRINT_AREA_M2, None)
        )
        self.energyconsumption_kwhrperday = EnergyConsumptionPerDayKPI(
            name=KPI_ENERGY_CONSUMPTION_KWHRPERDAY, value=None,
            name_in_dbtable=self.db_kpi_mapping.get(
                KPI_ENERGY_CONSUMPTION_KWHRPERDAY, None)
            )
        self.energyconsumption_kwhrperm3 = EnergyConsumptionPerM3KPI(
            name=KPI_ENERGY_CONSUMPTION_KWHRPERM3,
            value=None,
            name_in_dbtable=self.db_kpi_mapping.get(
                KPI_ENERGY_CONSUMPTION_KWHRPERM3, None)
        )
        self.constructioncosts_eur = ConstructionCostsKPI(
            name=KPI_SPECIFIC_CONSTRUCTION_COSTS,
            value=None, name_in_dbtable=self.db_kpi_mapping.get(
                KPI_SPECIFIC_CONSTRUCTION_COSTS, None)
        )
        self.investmentcosts_eur = InvestmentCostsYearKPI(
            name=KPI_INVESTMENT_COSTS_ANN, value=None,
            name_in_dbtable=self.db_kpi_mapping.get(KPI_INVESTMENT_COSTS_ANN, None)
            )  # total investment costs in EUR
        self.head_loss_bar = HeadLossBarKPI(
            name=TECHKPI_HEADLOSS_BAR, value=None,
            name_in_dbtable=self.db_kpi_mapping.get(TECHKPI_HEADLOSS_BAR, None)
        )
        # self.mass_of_chemicals_daily_kg = MassOfChemicalsDailyKPI(
        #     name=TECHKPI_MASS_OF_CHEMICALS, value=None,
        #     name_in_dbtable=self.db_kpi_mapping.get(
        #         TECHKPI_MASS_OF_CHEMICALS, None)
        # )
        self.co2_emmissions_chemicals_kgperm3 = CO2EmissionsPerM3KPI(
            name=KPI_CO2_EMISSIONS_KGPERM3, value=None,
            name_in_dbtable=self.db_kpi_mapping.get(
                KPI_CO2_EMISSIONS_KGPERM3, None)
        )
        self.power_kw = PowerKWKPI(
            name=TECHKPI_POWER_KW, value=None,
            name_in_dbtable=self.db_kpi_mapping.get(TECHKPI_POWER_KW, None)
        )
        self.co2_emissions_kgperm3 = CO2EmissionsPerM3KPI(
            name=TECHKPI_CO2_EMISSIONS_KGPERM3, value=None,
            name_in_dbtable=self.db_kpi_mapping.get(
                TECHKPI_CO2_EMISSIONS_KGPERM3, None)
        )
        self.oper_and_maintenancecosts_eurperyear = OperAndMaintenanceCostsKPI(
            name=KPI_OPER_AND_MAINT_COSTS_ANN, value=None,
            name_in_dbtable=self.db_kpi_mapping.get(
                KPI_OPER_AND_MAINT_COSTS_ANN, None)
        )
        self.plant_kpis = plant_kpis

    def update_nominal_flow_m3perhr(
        self,
    ):
        """
        Calculates and sets the nominal flow rate in cubic meters per hour
        based on design parameters.

        This method retrieves required parameters from `design_parameters`, e.g.
        including population size, average consumption per person per day,
        large-scale consumption, leakage factor, and peak demand factor.
        It validates the presence of essential parameters and raises a
        ValueError if any are missing. The nominal flow rate is then calculated
        using these parameters and stored in `nominal_flow_m3perhr`.

        Returns:
            The updated `self.nominal_flow_m3perhr` object after calculation.

        Raises:
            ValueError: If any of the required parameters (e.g.
                'population persons', 'average consumption (lppd)',
                'large-scale consumption (m3/day)', 'leakage factor',
                or 'peak demand factor') are missing from
                `design_parameters`.
        """        
        nominal_flow_m3perhr = self.nominal_flow_m3perhr
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
        new_value = nominal_flow_m3perhr.calculate_value(
            population_persons=int(population_persons),
            avg_consumption_lppd=avg_consumption_lppd,
            leakage_factor=leakage_factor,
            peak_demand_factor=peak_demand_factor,
            largescaleconsumption_m3pd=largescaleconsumption_m3pd,
        )
        return new_value

    def update_plant_kpis(self):
        """Update plant KPI values based on current calculations."""
        db_kpi_mapping = self.db_kpi_mapping
        self.plant_kpis = {
            db_kpi_mapping[kpi_name]: getattr(self, kpi_attr).value
            for kpi_attr, kpi_name in self.kpi_attr_mapping.items()
            if (
                getattr(self, kpi_attr).value is not None and
                getattr(self, kpi_attr).name_in_dbtable is not None and
                kpi_name in db_kpi_mapping)
        }

    def set_constructioncosts(
        self,
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
        # parameters = self.design_parameters
        # plc_costs = parameters.get('PLC costs (EUR)', 0.)
        # personnel_costs = parameters.get('personnel costs (EUR)', 0.)

        costs = self.constructioncosts_eur.value or 0.0
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
                    # plant_property = constrcost_params.get('plantproperty', None)  # noqa, E501
                    # technology_property = constrcost_params.get(
                    #     'technologyproperty', None)
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
                else:
                    logger.warning(
                        f"Construction cost parameters not found for "
                        f"technology: {technology}")
                    continue
        costs = 1000 * round(abs(costs)/1000.0, 2)
        self.constructioncosts_eur.value = costs

    def get_energyconsumption_per_m3(
        self,
    ) -> float:
        energy_consumption_kwhperday = self.energyconsumption_kwhrperday.value
        nominal_flow_m3perday = self.nominal_flow_m3perhr.value * 24
        if (
            energy_consumption_kwhperday is None
            or nominal_flow_m3perday is None
        ):
            raise ValueError(
                "Total energy consumption and nominal flow must be provided.")
        energy_consumption_per_m3 = (
            energy_consumption_kwhperday / nominal_flow_m3perday)
        return energy_consumption_per_m3
    

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

