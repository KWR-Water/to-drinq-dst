import unittest

from drinq.utils.treatmentkpi import (
    TreatmentKPI,
    TreatmentDataclassMixin,
    CoagulationDynamicMixing,
    CascadeMixerCoagulationDosing,
    ChainScrapedSedimentation,
    RapidSandSingleMediumFiltration,
    Strainer,
    ChlorineDisinfection,
    ChloramineDisinfection,
    BaffledOzonationContactor,
    UVdisinfection,
    CleanWaterStorageTank,
    calculate_chemical_storage_area__m2,
    calculate_flow_per_lane
    )
from drinq.utils.treatmentkpi import TPN


class TestCoagulationDynamicMixing(unittest.TestCase):
    def setUp(self):
        self.parameters = {
            'tank height': 4.0,
            'tank height chemical storage': 3.0,
            'target concentration of dosing chemical': 20.0,
            'chemical dosing solution concentration (w/w%)': 10.0,
            'mass density of chemical': 1.2,
            'retention time (min)': 30.0,
            'storage time of chemicals (days)': 15,
            'mixer velocity gradient': 100.0,
            'power efficiency of mixer(s)': 0.8,
            'units per lane': 3,
            'chemical emission factor': 0.5,
        }
        self.design_parameters = {
            'number of lanes': 2,
            'emission factor (electricity)': 0.45,
        }
        self.plant_kpis = {
            'nominal flow rate': 100.0,
        }

    def test_init(self):
        mixer = CoagulationDynamicMixing(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            digest_parameter_list=[],
        )
        self.assertTrue(mixer.tank_height == self.parameters['tank height'])
        self.assertTrue(mixer.retention_time_min == self.parameters[
            'retention time (min)'])
        self.assertTrue(mixer.lanes == self.design_parameters['number of lanes'])
        self.assertTrue(mixer.nominal_flow_m3perh == self.plant_kpis[
            'nominal flow rate'])

    def test_get_kpi(self):
        mixer = CoagulationDynamicMixing(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
        )
        result = mixer.get_kpi('footprint area')
        self.assertEqual(
            result, mixer.footprint_area__m2)
        result = mixer.get_kpi('head loss')
        self.assertEqual(
            result, mixer.hydraulic_headloss__bar)

    def test_footprint_area(self):
        mixer = CoagulationDynamicMixing(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
        )
        area = mixer.footprint_area__m2
        self.assertGreater(area, 0.0)

    def test_pressure_head(self):
        mixer = CoagulationDynamicMixing(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            digest_parameter_list=None,
        )
        headloss = mixer.hydraulic_headloss__bar
        self.assertGreater(headloss, 0.0)

    def test_daily_energy_consumption(self):
        mixer = CoagulationDynamicMixing(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
        )
        energy = mixer.daily_energy_consumption__kwh
        self.assertGreater(energy, 0.0)

    def test_kpi_dict(self):
        mixer = CoagulationDynamicMixing(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            digest_parameter_list=None,
        )
        kpi_results = mixer.get_kpi_dict()
        self.assertIn('footprint area', kpi_results)
        self.assertIn('head loss', kpi_results)
        self.assertIn('daily energy consumption', kpi_results)
        self.assertIn('CO2 equivalent emissions', kpi_results)


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
            'target concentration of dosing chemical': 25.0,
            'power efficiency of mixer(s)': 0.85,
            'power': 1.2,
            'units per lane': 4,
            'storage time of chemicals (days)': 30,
            'chemical emission factor': 0.6,
        }
        self.design_parameters = {
            'number of lanes': 3,
            'emission factor (electricity)': 0.45,
        }
        self.plant_kpis = {
            'nominal flow rate': 150.0,
            }

    def test_init(self):
        cascade_mixer = CascadeMixerCoagulationDosing(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
        )
        self.assertTrue(cascade_mixer.tank_height == self.parameters['tank height'])  # noqa, E501
        self.assertTrue(cascade_mixer.retention_time_min == self.parameters['retention time (min)'])  # noqa, E501
        self.assertTrue(cascade_mixer.lanes == self.design_parameters['number of lanes'])  # noqa, E501
        self.assertTrue(cascade_mixer.nominal_flow_m3perh == self.plant_kpis['nominal flow rate'])  # noqa, E501


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
            'emission factor (electricity)': 0.45,
        }
        self.plant_kpis = {
            'nominal flow rate': 250.0,
        }
        self.kpi_results = {
            'footprint area': 0.0763888888888889,
            'footprint area for chemicals': 0.0,
            'daily energy consumption': 0.4166666666666667,
            'daily mass of chemicals': {},
            'chemical solution concentration': 0.0,
            'head loss': 0.0024991369980118462,
            'power': 0.017361111111111112,
            'CO2 equivalent emissions': 3.125e-05
        }

    def test_init(self):
        strainer = Strainer(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            digest_parameter_list=['area'],
        )
        self.assertTrue(strainer.bar_width == self.parameters['bar width'])  # noqa, E501
        self.assertTrue(strainer.bar_spacing == self.parameters['bar spacing'])  # noqa, E501
        self.assertTrue(strainer.nominal_flow_m3perh == self.plant_kpis['nominal flow rate'])  # noqa, E501

    def test_kpi_dict(self):
        strainer = Strainer(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            digest_parameter_list=['area'],
        )
        kpi_results = strainer.get_kpi_dict()
        self.assertIn('footprint area', kpi_results)
        self.assertIn('head loss', kpi_results)
        self.assertIn('daily energy consumption', kpi_results)
        self.assertIn('CO2 equivalent emissions', kpi_results)
        self.assertDictEqual(kpi_results, self.kpi_results)

    def test_footprint_area(self):
        strainer = Strainer(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            digest_parameter_list=['area'],
        )
        area = strainer.footprint_area__m2
        self.assertGreater(area, 0.0)

    def test_daily_energy_consumption(self):
        strainer = Strainer(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            digest_parameter_list=['area'],
        )
        energy = strainer.daily_energy_consumption__kwh
        self.assertGreater(energy, 0.0)


class TestChlorineDisinfection(unittest.TestCase):
    def setUp(self):
        self.parameters = {
            'tank height': 6.0,
            'tank height chemical storage': 4.0,
            'target residual concentration (mg/l)': 1.0,
            'target concentration of dosing chemical': 10.0,
            'chemical dosing solution concentration (w/w%)': 12.0,
            'power': 0.5,
            'retention time (min)': 40.0,
            'units per lane': 5,
            'storage time of chemicals (days)': 20,
            'chemical emission factor': 0.5,
        }
        self.design_parameters = {
            'number of lanes': 2,
            'emission factor (electricity)': 0.45,
        }
        self.plant_kpis = {
            'nominal flow rate': 200.0,
        }

    def test_init(self):
        chlorine_disinfection = ChlorineDisinfection(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
        )
        self.assertTrue(chlorine_disinfection.tank_height_m == self.parameters['tank height'])  # noqa, E501
        self.assertTrue(chlorine_disinfection.retention_time_min == self.parameters['retention time (min)'])  # noqa, E501
        self.assertTrue(chlorine_disinfection.units_per_lane == self.parameters['units per lane'])  # noqa, E501
        self.assertTrue(chlorine_disinfection.nominal_flow_m3perh == self.plant_kpis['nominal flow rate'])  # noqa, E501

    def test_daily_mass_chemicals(self):
        chlorine_disinfection = ChlorineDisinfection(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
        )
        daily_mass_kg = chlorine_disinfection.daily_mass_of_chemicals__kg
        self.assertIsInstance(daily_mass_kg, dict)
        self.assertGreaterEqual(sum(daily_mass_kg.values()), 0.0)

    def test_get_kpi_dict(self):
        chlorine_disinfection = ChlorineDisinfection(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            chem_parameters=['chlorine'],
        )
        kpi_results = chlorine_disinfection.get_kpi_dict()
        self.assertIn('footprint area', kpi_results)
        self.assertIn('daily mass of chemicals', kpi_results)
        self.assertIn('head loss', kpi_results)
        self.assertIn('CO2 equivalent emissions', kpi_results)

    # TODO: Add more tests for ChlorineDisinfection methods


class TestChloramineDisinfection(unittest.TestCase):
    def setUp(self):
        self.parameters = {
            'tank height': 6.0,
            'tank height chemical storage': 4.0,
            'target residual concentration (mg/l)': 1.0,
            'target concentration of dosing chemical': 10.0,
            'chemical dosing solution concentration (w/w%)': 12.0,
            'power': 0.5,
            'retention time (min)': 40.0,
            'units per lane': 5,
            'storage time of chemicals (days)': 20,
            'chemical emission factor': 0.5,
        }
        self.design_parameters = {
            'number of lanes': 2,
            'emission factor (electricity)': 0.45,
        }
        self.plant_kpis = {
            'nominal flow rate': 200.0,
        }

    def test_init(self):
        chloramine = ChloramineDisinfection(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            chem_parameters=['chloramine'],
        )
        self.assertEqual(
            chloramine.units_per_lane, self.parameters['units per lane'])
        self.assertEqual(
            chloramine.retention_time_min, self.parameters['retention time (min)'])
        self.assertEqual(
            chloramine.lanes, self.design_parameters['number of lanes'])

    def test_get_kpi_dict(self):
        chloramine = ChloramineDisinfection(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            chem_parameters=['chloramine'],
        )
        kpi_results = chloramine.get_kpi_dict()
        self.assertIn('footprint area', kpi_results)
        self.assertIn('daily mass of chemicals', kpi_results)
        self.assertIn('head loss', kpi_results)
        self.assertIn('CO2 equivalent emissions', kpi_results)


class TestBaffledOzonationContactor(unittest.TestCase):
    def setUp(self):
        self.parameters = {
            'tank height': 5.0,
            'units per lane': 2,
            'retention time (min)': 20.0,
            'target concentration of dosing chemical': 3.0,
            'energy consumption per kg ozone': 8.0,
            'chemical emission factor': 0.5,
        }
        self.design_parameters = {
            'number of lanes': 2,
            'emission factor (electricity)': 0.45,
        }
        self.plant_kpis = {
            'nominal flow rate': 160.0,
        }

    def test_init(self):
        ozone = BaffledOzonationContactor(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            chem_parameters=['ozone'],
        )
        self.assertEqual(ozone.tank_height_m, self.parameters['tank height'])
        self.assertEqual(ozone.units_per_lane,
                         self.parameters['units per lane'])
        self.assertEqual(ozone.retention_time_min,
                         self.parameters['retention time (min)'])
        self.assertEqual(ozone.nominal_flow_m3perh,
                         self.plant_kpis['nominal flow rate'])
        self.assertEqual(ozone.chemical_solution_concentration__mg_per_l,
                         ozone.ozone_dosage_mgliter)

    def test_get_kpi_dict(self):
        ozone = BaffledOzonationContactor(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            chem_parameters=['ozone'],
        )
        kpi_results = ozone.get_kpi_dict()
        self.assertIn('footprint area', kpi_results)
        self.assertAlmostEqual(
            ozone.footprint_area__m2, 27.0, places=1)
        self.assertIn('daily mass of chemicals', kpi_results)
        self.assertEqual(
            ozone.daily_mass_of_chemicals__kg['ozone'],
            ozone.nominal_flow_m3perh * 24 * ozone.ozone_dosage_mgliter / 1000)
        self.assertIn('head loss', kpi_results)
        self.assertAlmostEqual(
            ozone.hydraulic_headloss__bar, 0.539, places=1)
        self.assertIn('CO2 equivalent emissions', kpi_results)
        self.assertAlmostEqual(
            ozone.co2_emissions__kg_co2_eq_per_m3, 6.2208, places=2)


class TestUVDisinfection(unittest.TestCase):
    def setUp(self):
        self.parameters = {
            'units per lane': 2,
            'UV dose': 40.0,
            'UV power intensity': 10.0,
            'tank height': 0.2,
            'UV power per m3': 0.04,
        }
        self.design_parameters = {
            'number of lanes': 2,
            'emission factor (electricity)': 0.45,
        }
        self.plant_kpis = {
            'nominal flow rate': 180.0,
        }
        self.kpi_results = {
            'footprint area': 2.0,
            'footprint area for chemicals': 0.0,
            'daily energy consumption': 192.0,
            'daily mass of chemicals': {},
            'chemical solution concentration': 0.0,
            'head loss': 0.11961322716039698,
            'power': 8.0,
            'CO2 equivalent emissions': 0.02}

    def test_init(self):
        uv = UVdisinfection(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
        )
        self.assertEqual(uv.units_per_lane, self.parameters['units per lane'])
        self.assertEqual(uv.tank_height_m, self.parameters['tank height'])
        self.assertEqual(uv.nominal_flow_m3perh, self.plant_kpis['nominal flow rate'])
        self.assertGreater(uv.exposure_time_sec, 0.0)

    def test_get_kpi_dict(self):
        uv = UVdisinfection(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
        )
        kpi_results = uv.get_kpi_dict()
        self.assertIn('footprint area', kpi_results)
        self.assertIn('daily mass of chemicals', kpi_results)
        self.assertIn('head loss', kpi_results)
        self.assertIn('CO2 equivalent emissions', kpi_results)
        self.assertDictEqual(kpi_results, self.kpi_results)
        

class TestCleanWaterStorageTank(unittest.TestCase):
    def setUp(self):
        self.parameters = {
            'tank height': 4.0,
            'retention time (hr)': 12.0,
            'units per lane': 1,
        }
        self.design_parameters = {
            'number of lanes': 2,
            'emission factor (electricity)': 0.45,
        }
        self.plant_kpis = {
            'nominal flow rate': 100.0,
        }

    def test_init(self):
        storage = CleanWaterStorageTank(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
        )
        self.assertEqual(storage.tank_height_m, self.parameters['tank height'])
        self.assertEqual(storage.retention_time_hrs, self.parameters['retention time (hr)'])
        self.assertEqual(storage.units_per_lane, self.parameters['units per lane'])
        self.assertEqual(storage.nominal_flow_m3perh, self.plant_kpis['nominal flow rate'])

    def test_get_kpi_dict(self):
        storage = CleanWaterStorageTank(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
        )
        kpi_results = storage.get_kpi_dict()
        self.assertIn('footprint area', kpi_results)
        self.assertAlmostEqual(storage.footprint_area__m2, 300.0, places=1)
        self.assertIn('daily mass of chemicals', kpi_results)
        self.assertIn('head loss', kpi_results)
        self.assertAlmostEqual(storage.hydraulic_headloss__bar, 0.1, places=1)
        self.assertIn('CO2 equivalent emissions', kpi_results)


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
                self.plant_kpis = performance_indicators
                self.wq_parameters = wq_parameters
                self.__post_init__()
        params = {"a": 1}
        design = {"b": 2}
        perf = {"c": 3}
        wq = {"d": 4}
        dummy = Dummy(params, design, perf, wq)
        self.assertEqual(dummy.parameters, params)
        self.assertEqual(dummy.design_parameters, design)
        self.assertEqual(dummy.plant_kpis, perf)
        self.assertEqual(dummy.wq_parameters, wq)


class TestChainScrapedSedimentation(unittest.TestCase):
    def setUp(self):
        self.parameters = {
            'tank height': 4.0,
            'retention time (min)': 60.0,
            'scraper power coefficient': 0.1,
            'units per lane': 3,
            'surface overflow rate': 5.0,
        }
        self.design_parameters = {
            'number of lanes': 2,
            'emission factor (electricity)': 0.45,
        }
        self.plant_kpis = {
            'nominal flow rate': 120.0,
        }
        self.wq_parameters = {
            'input_parameter': {'total suspended solids (mg/l)': 150.0},
        }
        self.kpi_results = {
            'footprint area': 72.0,
            'footprint area for chemicals': 0.0,
            'daily energy consumption': 192.0,
            'daily mass of chemicals': {},
            'chemical solution concentration': 0.0,
            'head loss': 0.049033067954557606,
            'power': 8.0,
            'CO2 equivalent emissions': 0.030000000000000002
        }

    def test_init(self):
        sedimentation = ChainScrapedSedimentation(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            wq_parameters=self.wq_parameters,
        )
        self.assertTrue(sedimentation.scraper_power_coeff_kw_m2 == self.parameters['scraper power coefficient'])  # noqa, E501
        self.assertTrue(sedimentation.retention_time_min == self.parameters['retention time (min)'])  # noqa, E501
        self.assertTrue(sedimentation.lanes == self.design_parameters['number of lanes'])  # noqa, E501
        self.assertTrue(sedimentation.nominal_flow_m3perh == self.plant_kpis['nominal flow rate'])  # noqa, E501
    
    def test_get_kpi_dict(self):
        sedimentation = ChainScrapedSedimentation(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            wq_parameters=self.wq_parameters,
        )
        kpi_results = sedimentation.get_kpi_dict()
        self.assertDictEqual(kpi_results, self.kpi_results)


class TestRSFSingle(unittest.TestCase):
    def setUp(self):
        self.parameters = {
            TPN['units_per_lane']: 2,
            TPN['filtration_rate']: 10,
            TPN['sand_porosity']: 0.45,
            TPN['sand_density']: 2650,
            TPN['sand_media_grain_size']: 0.8,
            TPN['backwash_duration']: 10,
            TPN['backwash_tank_height']: 3.0,
            TPN['backwash_filtration_rate']: 45.0,
            TPN['power_efficiency_of_pumps']: 75.0,
            TPN['sand_filter_bed_height']: 1.5,
        }
        self.design_parameters = {
            'number of lanes': 2,
            'emission factor (electricity)': 0.45,
        }
        self.plant_kpis = {
            'nominal flow rate': 100.0,
        }
        self.wq_parameters = {}
        self.kpi_results = {
            'footprint area': 17.0,
            'footprint area for chemicals': 0.0,
            'daily energy consumption': 0.282015873015873,
            'daily mass of chemicals': {},
            'chemical solution concentration': 0.0,
            'head loss': 0.2840731037215019,
            'power': 2.9611666666666667,
            'CO2 equivalent emissions': 5.2877976190476194e-05
        }

    def test_init(self):
        rsf_single = RapidSandSingleMediumFiltration(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            wq_parameters=self.wq_parameters,
            digest_parameter_list=['filter area'],
        )
        self.assertTrue(rsf_single.units_per_lane == self.parameters[TPN['units_per_lane']])  # noqa, E501
        self.assertTrue(rsf_single.hydraulic_loading_rate_m3m2h == self.parameters[TPN['filtration_rate']])  # noqa, E501

    def test_get_kpi_dict(self):
        rsf_single = RapidSandSingleMediumFiltration(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            wq_parameters=self.wq_parameters,
            digest_parameter_list=['filter area'],
        )
        kpi_results = rsf_single.get_kpi_dict()
        self.assertDictEqual(kpi_results, self.kpi_results)

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


class TestCalculateChemicalStorageArea(unittest.TestCase):
    def test_basic_calculation(self):
        # daily_volume = 2 m3/day, storage_time = 10 days, tank_height = 2 m
        # Expected area = (2 * 10) / 2 = 10 m2
        area = calculate_chemical_storage_area__m2(
            daily_volume_m3perday=2.0,
            storage_time_days=10,
            tank_height_m=2.0
        )
        self.assertAlmostEqual(area, 10.0)

    def test_with_space_factor(self):
        # daily_volume = 1 m3/day, storage_time = 5 days, tank_height = 1 m, space_factor = 1.5
        # Expected area = 1.5 * (1 * 5) / 1 = 7.5 m2
        area = calculate_chemical_storage_area__m2(
            daily_volume_m3perday=1.0,
            storage_time_days=5,
            tank_height_m=1.0,
            space_factor=1.5
        )
        self.assertAlmostEqual(area, 7.5)

    def test_zero_tank_height_raises(self):
        with self.assertRaises(ValueError):
            calculate_chemical_storage_area__m2(
                daily_volume_m3perday=1.0,
                storage_time_days=5,
                tank_height_m=0.0
            )

    def test_negative_tank_height_raises(self):
        with self.assertRaises(ValueError):
            calculate_chemical_storage_area__m2(
                daily_volume_m3perday=1.0,
                storage_time_days=5,
                tank_height_m=-2.0
            )

    def test_zero_daily_volume(self):
        # Should return 0 area if daily volume is 0
        area = calculate_chemical_storage_area__m2(
            daily_volume_m3perday=0.0,
            storage_time_days=10,
            tank_height_m=2.0
        )
        self.assertEqual(area, 0.0)

    def test_zero_storage_time(self):
        # Should return 0 area if storage time is 0
        area = calculate_chemical_storage_area__m2(
            daily_volume_m3perday=2.0,
            storage_time_days=0.0,
            tank_height_m=2.0
        )
        self.assertEqual(area, 0.0)



