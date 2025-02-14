from unittest import TestCase

try:
    from research.flowcalc import (
        calculate_daily_flow, calculate_flow_per_lane, calculate_flow_per_unit,
        calculate_total_water_demand, calculate_water_demand_for_population, 
        var_consumption_lppd, var_total_water_demand
    )
except ModuleNotFoundError:
    import os
    import pathlib
    
    research_path = pathlib.Path(__file__).parent.parent.joinpath('research')
    pythonpath = os.environ['PYTHONPATH']
    pythonpath += f";{research_path}"
    

    from research.proof_of_concept.flowcalc import (
        calculate_total_water_demand_phr,
        calculate_flow_per_lane, 
        calculate_flow_per_unit,
        calculate_flow_phr, 
        calculate_water_demand_phr_for_population,
        var_consumption_lppd,
        var_total_water_demand,
    )


class TotalwaterdemandTestCase(TestCase):

    def test_total_water_demand(self):
        population = 1000
        consumption_lppd = 150
        demand_industry = 0
        demand_agriculture = 0
        leakage_factor = 0.1
        expected_demand = (population * (consumption_lppd / 1000 / 24)) * (1 + leakage_factor)
        result = calculate_total_water_demand_phr(
            population, consumption_lppd, demand_industry, demand_agriculture, leakage_factor)
        self.assertAlmostEqual(result, expected_demand, places=5) 

    def test_var_total_water_demand(self):
        delta_population = 0.1
        delta_leakage_factor = 0.01
        delta_consumption_lppd = 10
        delta_demand_industry = 100
        delta_demand_agriculture = 50
        leakage_factor = 0.05
        population_persons = 5000
        consumption_lppd = 200
        demand_industry = 1000
        demand_agriculture = 0
        result = var_total_water_demand(
            delta_population,
            delta_leakage_factor,
            delta_consumption_lppd,
            delta_demand_industry,
            delta_demand_agriculture,
            leakage_factor,
            population_persons,
            consumption_lppd,
            demand_industry,
            demand_agriculture
        )
        self.assertIsInstance(result, float)
        self.assertAlmostEqual(result, 13894.54, places=2)

    def test_water_demand_pop_and_agriculture(self):
        population = 2500
        consumption_lppd = 120
        demand_agriculture = 500
        leakage_factor = 0.2
        expected_demand = (population * (
            consumption_lppd / 1000 / 24)) + demand_agriculture / 24
        expected_demand *= (1 + leakage_factor)
        result = calculate_total_water_demand_phr(
            population_persons=population,
            consumption_lppd=consumption_lppd,
            demand_industry_m3pd=0, 
            demand_agriculture_m3pd=demand_agriculture,
            leakage_factor=leakage_factor)
        self.assertAlmostEqual(result, expected_demand, places=2) 

    def test_calculate_total_water_demand(self):
        population = 3000
        consumption = 180
        demand_industry = 800
        demand_agriculture = 600
        leakage_factor = 0.15
        expected_demand = (
            population * consumption / 1000 / 24) + (
                demand_industry + demand_agriculture) / 24
        expected_demand *= (1 + leakage_factor)
        result = calculate_total_water_demand_phr(
            population_persons=population,
            consumption_lppd=consumption,
            demand_industry_m3pd=demand_industry,
            demand_agriculture_m3pd=demand_agriculture,
            leakage_factor=leakage_factor)
        self.assertAlmostEqual(result, expected_demand, places=2) 

    def test_water_demand_only_population(self):
        population = 1500
        consumption = 100
        demand_industry = 0.0
        demand_agriculture = 0.0
        leakage_factor = 0.0
        expected_demand = (
            population * (consumption / 1000 / 24)) * (
                1 + leakage_factor)
        result = calculate_total_water_demand_phr(
            population, consumption, demand_industry, demand_agriculture, leakage_factor)
        self.assertAlmostEqual(result, expected_demand, places=5) 

    def test_waterdemand_pop_and_industry(self):
        population_persons = 2000
        consumption_lppd = 90
        demand_industry = 0
        demand_agriculture = 300
        leakage_factor = 0.1
        expected_demand = (population_persons * (
            consumption_lppd / 1000 / 24)) + (
                demand_industry + demand_agriculture) / 24
        expected_demand *= (1 + leakage_factor)
        self.assertAlmostEqual(
            calculate_total_water_demand_phr(
                population_persons=population_persons, 
                consumption_lppd=consumption_lppd,
                demand_industry_m3pd=demand_industry, 
                demand_agriculture_m3pd=demand_agriculture,
                leakage_factor=leakage_factor
                ),
            expected_demand
            )


if __name__ == '__main__':
    test_case = TotalwaterdemandTestCase()
    # test_case.test_calculate_total_water_demand()
    # test_case.test_total_water_demand()
    test_case.test_water_demand_only_population()
    test_case.test_var_total_water_demand()
    test_case.test_waterdemand_pop_and_industry()
    test_case.test_water_demand_pop_and_agriculture()
    print("\nAll tests OK")
