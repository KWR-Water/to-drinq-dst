import unittest

from drinq.api_treatmentkpi import (
    TreatmentKPI,
    TreatmentDataclassMixin,
    CoagulationDynamicMixing,
    CascadeMixerCoagulationDosing,
    ChainScrapedSedimentation,
    Strainer,
    ChlorineDisinfection,
    ChloramineDisinfection)


class TestCoagulationDynamicMixing(unittest.TestCase):
    def setUp(self):
        self.parameters = {
            'tank height': 4.0,
            'tank height chemical storage': 3.0,
            'target concentration of dosing chemical (mg/l)': 20.0,
            'chemical dosing solution concentration (w/w%)': 10.0,
            'mass density of chemical (g/cm3)': 1.2,
            'retention time (min)': 30.0,
            'storage time of chemicals (days)': 15,
            'mixer velocity gradient': 100.0,
            'power efficiency of mixer(s)': 0.8,
        }
        self.design_parameters = {
            'number of lanes': 2,
            'units per lane': 3,
        }
        self.performance_indicators = {
            'nominal flow rate (m3/hr)': 100.0,
        }

    def test_init(self):
        mixer = CoagulationDynamicMixing(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            performance_indicators=self.performance_indicators,
        )
        self.assertTrue(mixer.tank_height == self.parameters['tank height'])
        self.assertTrue(mixer.retention_time_min == self.parameters[
            'retention time (min)'])
        self.assertTrue(mixer.lanes == self.design_parameters['number of lanes'])
        self.assertTrue(mixer.nominal_flow_m3hr == self.performance_indicators[
            'nominal flow rate (m3/hr)'])

    def test_get_kpi(self):
        mixer = CoagulationDynamicMixing(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            performance_indicators=self.performance_indicators,
        )
        result = mixer.get_kpi('footprint area')
        self.assertEqual(
            result, mixer.footprint_area__m2())
        result = mixer.get_kpi('hydraulic headloss')
        self.assertEqual(
            result, mixer.hydraulic_headloss__bar())

    def test_footprint_area(self):
        mixer = CoagulationDynamicMixing(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            performance_indicators=self.performance_indicators,
        )
        area = mixer.footprint_area__m2()
        self.assertAlmostEqual(area, 15.0, places=1)

    def test_hydraulic_headloss(self):
        mixer = CoagulationDynamicMixing(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            performance_indicators=self.performance_indicators,
        )
        headloss = mixer.hydraulic_headloss__bar()
        self.assertAlmostEqual(headloss, 5.01, places=2)

    def test_daily_energy_consumption(self):
        mixer = CoagulationDynamicMixing(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            performance_indicators=self.performance_indicators,
        )
        energy = mixer.daily_energy_consumption__kwh()
        self.assertAlmostEqual(energy, 1501.7, places=1)

    def test_kpi_dict(self):
        mixer = CoagulationDynamicMixing(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            performance_indicators=self.performance_indicators,
        )
        kpi_results = mixer.get_kpi_dict()
        self.assertIn('footprint area', kpi_results)
        self.assertIn('hydraulic headloss', kpi_results)
        self.assertIn('daily energy consumption', kpi_results)
        self.assertIn('co2 emissions', kpi_results)


class TestCascadeMixerCoagulationDosing(unittest.TestCase):
    def setUp(self):
        self.parameters = {
            'tank height': 5.0,
            'weir height': 1.0,
            'weir coefficient': 0.6,
            'head loss coefficient': 0.5,
            'retention time (min)': 20.0,
            'number of cascade stages': 3,
            'tank height chemical storage': 4.0,
            'chemical dosing solution concentration (w/w%)': 15.0,
            'power for dosing (kW)': 0.75,
            'target concentration of dosing chemical (mg/l)': 25.0,
            'power efficiency of mixer(s)': 0.85,
            'power': 1.2,
        }
        self.design_parameters = {
            'number of lanes': 3,
            'units per lane': 4,
            'storage time of chemicals (days)': 30,
        }
        self.performance_indicators = {
            'nominal flow rate (m3/hr)': 150.0,
            }

    def test_init(self):
        cascade_mixer = CascadeMixerCoagulationDosing(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            performance_indicators=self.performance_indicators,
        )
        self.assertTrue(cascade_mixer.tank_height == self.parameters['tank height'])  # noqa, E501
        self.assertTrue(cascade_mixer.retention_time_min == self.parameters['retention time (min)'])  # noqa, E501
        self.assertTrue(cascade_mixer.lanes == self.design_parameters['number of lanes'])  # noqa, E501
        self.assertTrue(cascade_mixer.nominal_flow_m3hr == self.performance_indicators['nominal flow rate (m3/hr)'])  # noqa, E501


class TestStrainer(unittest.TestCase):
    def setUp(self):
        self.parameters = {
            'bar width': 0.6,
            'bar spacing': 0.02,
            'blockage factor': 0.7,
            'velocity bar screen': 1.0,
            'head loss coefficient': 0.5,
        }
        self.design_parameters = {
            'number of lanes': 2,
        }
        self.performance_indicators = {
            'nominal flow rate (m3/hr)': 250.0,
        }

    def test_init(self):
        strainer = Strainer(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            performance_indicators=self.performance_indicators,
        )
        self.assertTrue(strainer.bar_width == self.parameters['bar width'])  # noqa, E501
        self.assertTrue(strainer.bar_spacing == self.parameters['bar spacing'])  # noqa, E501
        self.assertTrue(strainer.nominal_flow_m3perh == self.performance_indicators['nominal flow rate (m3/hr)'])  # noqa, E501

    def test_kpi_dict(self):
        strainer = Strainer(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            performance_indicators=self.performance_indicators,
        )
        kpi_results = strainer.get_kpi_dict()
        self.assertIn('footprint area', kpi_results)
        self.assertIn('hydraulic headloss', kpi_results)
        self.assertIn('daily energy consumption', kpi_results)
        self.assertIn('co2 emissions', kpi_results)

    def test_footprint_area(self):
        strainer = Strainer(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            performance_indicators=self.performance_indicators,
        )
        area = strainer.footprint_area__m2()
        self.assertAlmostEqual(area, 7.893, places=2)

    def test_daily_energy_consumption(self):
        strainer = Strainer(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            performance_indicators=self.performance_indicators,
        )
        energy = strainer.daily_energy_consumption__kwh()
        self.assertAlmostEqual(energy, 0.4167, places=2)

class TestChlorineDisinfection(unittest.TestCase):
    def setUp(self):
        self.parameters = {
            'tank height': 6.0,
            'tank height chemical storage': 4.0,
            'target residual concentration (mg/l)': 1.0,
            'target concentration of dosing chemical (mg/l)': 10.0,
            'chemical dosing solution concentration (w/w%)': 12.0,
            'power': 0.5,
            'retention time (min)': 40.0,
        }
        self.design_parameters = {
            'number of lanes': 2,
            'units per lane': 5,
            'chemical storage time (days)': 20,
        }
        self.performance_indicators = {
            'nominal flow rate (m3/hr)': 200.0,
        }

    def test_init(self):
        chlorine_disinfection = ChlorineDisinfection(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            performance_indicators=self.performance_indicators,
        )
        self.assertTrue(chlorine_disinfection.tank_height_m == self.parameters['tank height'])
        self.assertTrue(chlorine_disinfection.retention_time_min == self.parameters['retention time (min)'])  # noqa, E501
        self.assertTrue(chlorine_disinfection.units_per_lane == self.design_parameters['units per lane'])  # noqa, E501
        self.assertTrue(chlorine_disinfection.nominal_flow_m3perh == self.performance_indicators['nominal flow rate (m3/hr)'])  # noqa, E501

    def test_daily_mass_chemicals(self):
        chlorine_disinfection = ChlorineDisinfection(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            performance_indicators=self.performance_indicators,
        )
        daily_mass_kg = chlorine_disinfection.daily_mass_of_chemicals__kg()
        self.assertAlmostEqual(daily_mass_kg, 2.4, places=1)

    # TODO: Add more tests for ChlorineDisinfection methods


class DummyTreatmentKPI(TreatmentKPI):
    def get_kpi(self, kpi_name: str) -> float:
        return 42.0
    def __repr__(self):
        return "DummyTreatmentKPI()"
    def get_kpi_dict(self) -> dict:
        return {"dummy": 42.0}
    @property
    def footprint_area__m2(self) -> float:
        return 1.0
    @property
    def footprint_area_for_chemicals__m2(self) -> float:
        return 2.0
    @property
    def daily_energy_consumption__kwh(self) -> float:
        return 3.0
    @property
    def daily_mass_of_chemicals__kg(self) -> float:
        return 4.0
    @property
    def hydraulic_headloss__bar(self) -> float:
        return 5.0
    @property
    def power__kw(self) -> float:
        return 6.0


class TestTreatmentDataclassMixin(unittest.TestCase):
    def test_post_init_assigns_attributes(self):
        class Dummy(TreatmentDataclassMixin):
            def __init__(
                    self,
                    parameters,
                    design_parameters,
                    performance_indicators,
                    wq_parameters=None):
                self.parameters = parameters
                self.design_parameters = design_parameters
                self.performance_indicators = performance_indicators
                self.wq_parameters = wq_parameters
                self.__post_init__()
        params = {"a": 1}
        design = {"b": 2}
        perf = {"c": 3}
        wq = {"d": 4}
        dummy = Dummy(params, design, perf, wq)
        self.assertEqual(dummy.parameters, params)
        self.assertEqual(dummy.design_parameters, design)
        self.assertEqual(dummy.performance_indicators, perf)
        self.assertEqual(dummy.wq_parameters, wq)


class TestChainScrapedSedimentation(unittest.TestCase):
    def setUp(self):
        self.parameters = {
            'tank height': 4.0,
            'retention time (min)': 60.0,
            'scraper power coefficient': 0.1,
        }
        self.design_parameters = {
            'number of lanes': 2,
            'units per lane': 3,
            'overflow rate (m3/m2/h)': 5.0,
        }
        self.performance_indicators = {
            'nominal flow rate (m3/hr)': 120.0,
        }
        self.wq_parameters = {
            'total suspended solids (mg/l)': 150.0,
        }

    def test_init(self):
        sedimentation = ChainScrapedSedimentation(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            performance_indicators=self.performance_indicators,
            wq_parameters=self.wq_parameters,
        )
        self.assertTrue(sedimentation.scraper_power_per_m2 == self.parameters['scraper power coefficient'])  # noqa, E501
        self.assertTrue(sedimentation.retention_time_min == self.parameters['retention time (min)'])  # noqa, E501
        self.assertTrue(sedimentation.lanes == self.design_parameters['number of lanes'])  # noqa, E501
        self.assertTrue(sedimentation.flow_m3perh == self.performance_indicators['nominal flow rate (m3/hr)'])  # noqa, E501


class TestTreatmentKPIAbstract(unittest.TestCase):
    def setUp(self):
        class IncompleteKPI(TreatmentKPI):
            pass
        with self.assertRaises(TypeError):
            IncompleteKPI(
                parameters={},
                design_parameters={},
                performance_indicators={},
            )
        self.IncompleteKPI = IncompleteKPI

    def test_abstract_methods_raise(self):
        with self.assertRaises(TypeError):
            instance = object.__new__(self.IncompleteKPI)
        # kpi = object.__new__(self.IncompleteKPI)
        # with self.assertRaises(NotImplementedError):
        #     instance.get_kpi("any")


