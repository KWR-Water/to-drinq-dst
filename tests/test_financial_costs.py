import unittest
from drinq.api_calculation import KPI_CONSTRUCTION_COSTS, ConstructionCostsKPI
from drinq.utils.financial_costs import construction_costs_total


class TestConstructionCostsKPI(unittest.TestCase):
    def test_surcharge_percentages_are_applied_to_construction_costs(self):
        kpi = ConstructionCostsKPI(name=KPI_CONSTRUCTION_COSTS, value=None)
        result = kpi.calculate_value(
            construction_costs=1000,
            construction_costs_percentage=20,
            tail_costs_percentage=5,
            general_facilities_costs_percentage=10,
        )
        self.assertAlmostEqual(result, 1000 * 1.20 * 1.05 * 1.10, places=9)
        self.assertEqual(kpi.value, result)

    def test_default_surcharges(self):
        kpi = ConstructionCostsKPI(name=KPI_CONSTRUCTION_COSTS, value=None)
        result = kpi.calculate_value(construction_costs=1000)
        self.assertAlmostEqual(result, 1000 * 1.20 * 1.05 * 1.05, places=9)


class TestConstructionCostsTotal(unittest.TestCase):
    def test_construction_costs_total_default_percentages(self):
        # construction_costs = 1000, plc_costs = 200
        # default percentages: 20, 15, 5
        # factor = (1+0.2)*(1+0.15)*(1+0.05) = 1.2*1.15*1.05
        expected_factor = 1.2 * 1.15 * 1.05
        expected = (1000 + 200) * expected_factor
        result = construction_costs_total(1000, 200)
        self.assertAlmostEqual(result, expected, places=9)

    def test_construction_costs_total_custom_percentages(self):
        # construction_costs = 500, plc_costs = 100
        # percentages: 10, 5, 2
        expected_factor = (1 + 0.10) * (1 + 0.05) * (1 + 0.02)
        expected = (500 + 100) * expected_factor
        result = construction_costs_total(500, 100, 10, 5, 2)
        self.assertAlmostEqual(result, expected, places=9)

    def test_construction_costs_total_zero_costs(self):
        # All costs zero
        result = construction_costs_total(0, 0)
        self.assertEqual(result, 0)

    def test_construction_costs_total_negative_costs(self):
        # Negative costs should be handled mathematically
        result = construction_costs_total(-100, -50)
        expected_factor = 1.2 * 1.15 * 1.05
        expected = (-100 + -50) * expected_factor
        self.assertAlmostEqual(result, expected, places=9)

    def test_construction_costs_total_zero_percentages(self):
        # All percentages zero, factor should be 1
        result = construction_costs_total(1000, 500, 0, 0, 0)
        self.assertEqual(result, 1500)

    def test_construction_costs_total_large_values(self):
        # Test with large values
        result = construction_costs_total(1e6, 2e6, 50, 25, 10)
        expected_factor = (1 + 0.5) * (1 + 0.25) * (1 + 0.10)
        expected = (1e6 + 2e6) * expected_factor
        self.assertAlmostEqual(result, expected, places=9)