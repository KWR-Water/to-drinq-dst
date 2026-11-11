import unittest

from drinq.utils.treatmentkpi import (
    TreatmentKPI,
    TreatmentDataclassMixin,
    CoagulationDynamicMixing,
    CascadeMixerCoagulationDosing,
    CoagulationInlineMixing,
    ChainScrapedSedimentation,
    RapidSandSingleMediumFiltration,
    RapidSandDoubleMediumFiltration,
    RapidSandPressurizedVesselFiltration,
    FlocculationDynamicMixing,
    LamellaClarifierSlope,
    LamellaClarifierHorizontal,
    SludgeBlanketClarifier,
    GranularActivatedCarbonFiltration,
    PowderedActivatedCarbonFiltration,
    AirFlotationDAF,
    Strainer,
    MicroStrainer,
    PelletSoftening,
    CationIonExchange,
    AnionicIEX,
    ChlorineDisinfection,
    ChloramineDisinfection,
    BaffledOzonationContactor,
    MembraneFiltration,
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
        self.wq_parameters = {
            'total suspended solids': {
                'input_parameter': 20.0,
                'target_parameter': 5.0,
            },
            'dissolved organic carbon': {
                'input_parameter': 3.0,
                'target_parameter': 2.0,
            },
            'pH': {'input_parameter': 7.2},
            'temperature': {'input_parameter': 18.0},
            'electrical conductivity': {'input_parameter': 41.4},
        }

    def test_init(self):
        mixer = CoagulationDynamicMixing(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            wq_parameters=self.wq_parameters,
            digest_parameter_list=['nominal dosing flow rate'],
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
            wq_parameters=self.wq_parameters,
            digest_parameter_list=['nominal dosing flow rate'],
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
            wq_parameters=self.wq_parameters,
            digest_parameter_list=['nominal dosing flow rate'],
        )
        area = mixer.footprint_area__m2
        self.assertGreater(area, 0.0)

    def test_pressure_head(self):
        mixer = CoagulationDynamicMixing(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            wq_parameters=self.wq_parameters,
        )
        headloss = mixer.hydraulic_headloss__bar
        self.assertGreater(headloss, 0.0)

    def test_kpi_dict(self):
        mixer = CoagulationDynamicMixing(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            wq_parameters=self.wq_parameters,
            digest_parameter_list=['nominal dosing flow rate']
        )
        kpi_results = mixer.get_kpi_dict()
        self.assertIn('footprint area', kpi_results)
        self.assertIn('head loss', kpi_results)
        self.assertIn('daily energy consumption', kpi_results)
        self.assertIn('CO2 equivalent emissions', kpi_results)
    
    def test_pressure_head(self):
        mixer = CoagulationDynamicMixing(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            wq_parameters=self.wq_parameters,
            digest_parameter_list=['nominal dosing flow rate'],
        )
        headloss = mixer.hydraulic_headloss__bar
        self.assertGreater(headloss, 0.0)

    def test_co2_emissions(self):
        mixer = CoagulationDynamicMixing(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            wq_parameters=self.wq_parameters,
            digest_parameter_list=['nominal dosing flow rate'],
        )
        emissions = mixer.co2_emissions__kg_co2_eq_per_m3
        self.assertGreater(emissions, 0.0)

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
    
    def test_kpi_dict(self):
        cascade_mixer = CascadeMixerCoagulationDosing(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
        )
        kpi_results = cascade_mixer.get_kpi_dict()
        self.assertIn('footprint area', kpi_results)
        self.assertIn('head loss', kpi_results)
        self.assertIn('daily energy consumption', kpi_results)
        self.assertIn('CO2 equivalent emissions', kpi_results)

    def test_footprint_area(self):
        cascade_mixer = CascadeMixerCoagulationDosing(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
        )
        area = cascade_mixer.footprint_area__m2
        self.assertGreater(area, 0.0)

    def test_daily_energy_consumption(self):
        cascade_mixer = CascadeMixerCoagulationDosing(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
        )
        energy = cascade_mixer.daily_energy_consumption__kwh
        self.assertGreater(energy, 0.0)
    
    def test_footprint_area_for_chemicals(self):
        cascade_mixer = CascadeMixerCoagulationDosing(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
        )
        energy = cascade_mixer.daily_energy_consumption__kwh
        self.assertGreater(energy, 0.0)
    
    def test_pressure_head(self):
        cascade_mixer = CascadeMixerCoagulationDosing(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
        )
        headloss = cascade_mixer.hydraulic_headloss__bar
        self.assertGreater(headloss, 0.0)

    def test_co2_emissions(self):
        cascade_mixer = CascadeMixerCoagulationDosing(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
        )
        emissions = cascade_mixer.co2_emissions__kg_co2_eq_per_m3
        self.assertGreater(emissions, 0.0)


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
    
    def test_pressure_head(self):
        strainer = Strainer(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            digest_parameter_list=['area'],
        )
        headloss = strainer.hydraulic_headloss__bar
        self.assertGreater(headloss, 0.0)

class TestCoagulationInlineMixing(unittest.TestCase):
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
        inline = CoagulationInlineMixing(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            digest_parameter_list=[],
        )
        self.assertTrue(inline.lanes == self.design_parameters['number of lanes'])
        self.assertTrue(inline.nominal_flow_m3perh == self.plant_kpis[
            'nominal flow rate'])

    def test_get_kpi(self):
        inline = CoagulationInlineMixing(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            digest_parameter_list=[],
        )
        result = inline.get_kpi('footprint area')
        self.assertEqual(
            result, inline.footprint_area__m2)
        result = inline.get_kpi('head loss')
        self.assertEqual(
            result, inline.hydraulic_headloss__bar)

    def test_footprint_area(self):
        inline = CoagulationInlineMixing(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            digest_parameter_list=[],
        )
        area = inline.footprint_area__m2
        self.assertGreater(area, 0.0)

    def test_pressure_head(self):
        inline = CoagulationInlineMixing(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            digest_parameter_list=[],
        )
        headloss = inline.hydraulic_headloss__bar
        self.assertGreater(headloss, 0.0)

    def test_daily_energy_consumption(self):
        inline = CoagulationInlineMixing(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            digest_parameter_list=[],
        )
        energy = inline.daily_energy_consumption__kwh
        self.assertGreater(energy, 0.0)

    def test_kpi_dict(self):
        inline = CoagulationInlineMixing(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            digest_parameter_list=[],
        )
        kpi_results = inline.get_kpi_dict()
        self.assertIn('footprint area', kpi_results)
        self.assertIn('head loss', kpi_results)
        self.assertIn('daily energy consumption', kpi_results)
        self.assertIn('CO2 equivalent emissions', kpi_results)
    
    def test_pressure_head(self):
        inline = CoagulationInlineMixing(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            digest_parameter_list=[],
        )
        headloss = inline.hydraulic_headloss__bar
        self.assertGreater(headloss, 0.0)

    def test_co2_emissions(self):
        inline = CoagulationInlineMixing(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            digest_parameter_list=[],
        )
        emissions = inline.co2_emissions__kg_co2_eq_per_m3
        self.assertGreater(emissions, 0.0)

class TestMicroStrainer(unittest.TestCase):
    def setUp(self):
        self.parameters = {
            'bar width': 0.6,
            'bar spacing': 0.02,
            'open area factor': 0.7,
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

    def test_init(self):
        m_strainer = MicroStrainer(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            digest_parameter_list=['area'],
        )
        self.assertTrue(m_strainer.nominal_flow_m3perh == self.plant_kpis['nominal flow rate'])  # noqa, E501
        self.assertTrue(m_strainer.open_area_factor  == self.parameters['open area factor'])  # noqa, E501

    def test_kpi_dict(self):
        m_strainer = MicroStrainer(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            digest_parameter_list=['area'],
        )
        kpi_results = m_strainer.get_kpi_dict()
        self.assertIn('footprint area', kpi_results)
        self.assertIn('head loss', kpi_results)
        self.assertIn('daily energy consumption', kpi_results)
        self.assertIn('CO2 equivalent emissions', kpi_results)

    def test_footprint_area(self):
        m_strainer = MicroStrainer(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            digest_parameter_list=['area'],
        )
        area = m_strainer.footprint_area__m2
        self.assertGreater(area, 0.0)

    def test_daily_energy_consumption(self):
        m_strainer = MicroStrainer(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            digest_parameter_list=['area'],
        )
        energy = m_strainer.daily_energy_consumption__kwh
        self.assertGreater(energy, 0.0)

    def test_pressure_head(self):
        m_strainer = MicroStrainer(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            digest_parameter_list=['area'],
        )
        headloss = m_strainer.hydraulic_headloss__bar
        self.assertGreater(headloss, 0.0)

class TestFlocculation(unittest.TestCase):
    def setUp(self):
        self.parameters = {
            'tank height': 4.0,
            'retention time (min)': 50.0,
            'mass density of chemical': 1.2,
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
        flocmixer = FlocculationDynamicMixing(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            digest_parameter_list=['volume'],
        )
        self.assertTrue(flocmixer.tank_height == self.parameters['tank height'])
        self.assertTrue(flocmixer.lanes == self.design_parameters['number of lanes'])
        self.assertTrue(flocmixer.nominal_flow_m3perh == self.plant_kpis[
            'nominal flow rate'])

    def test_get_kpi(self):
        flocmixer = FlocculationDynamicMixing(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            digest_parameter_list=['volume'],
        )
        result = flocmixer.get_kpi('footprint area')
        self.assertEqual(
            result, flocmixer.footprint_area__m2)
        result = flocmixer.get_kpi('head loss')
        self.assertEqual(
            result, flocmixer.hydraulic_headloss__bar)

    def test_footprint_area(self):
        flocmixer = FlocculationDynamicMixing(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            digest_parameter_list=['volume'],
        )
        area = flocmixer.footprint_area__m2
        self.assertGreater(area, 0.0)

    def test_pressure_head(self):
        flocmixer = FlocculationDynamicMixing(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            digest_parameter_list=['volume'],
        )
        headloss = flocmixer.hydraulic_headloss__bar
        self.assertGreater(headloss, 0.0)

    def test_daily_energy_consumption(self):
        flocmixer = FlocculationDynamicMixing(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            digest_parameter_list=['volume'],
        )
        energy = flocmixer.daily_energy_consumption__kwh
        self.assertGreater(energy, 0.0)

    def test_kpi_dict(self):
        flocmixer = FlocculationDynamicMixing(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            digest_parameter_list=['volume'],
        )
        kpi_results = flocmixer.get_kpi_dict()
        self.assertIn('footprint area', kpi_results)
        self.assertIn('head loss', kpi_results)
        self.assertIn('daily energy consumption', kpi_results)
        self.assertIn('CO2 equivalent emissions', kpi_results)
    
    def test_pressure_head(self):
        flocmixer = FlocculationDynamicMixing(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            digest_parameter_list=['volume'],
        )
        headloss = flocmixer.hydraulic_headloss__bar
        self.assertGreater(headloss, 0.0)

    def test_co2_emissions(self):
        flocmixer = FlocculationDynamicMixing(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            digest_parameter_list=['volume'],
        )
        emissions = flocmixer.co2_emissions__kg_co2_eq_per_m3
        self.assertGreater(emissions, 0.0)

class TestChlorineDisinfection(unittest.TestCase):
    def setUp(self):
        self.parameters = {
            'tank height': 6.0,
            'tank height chemical storage': 4.0,
            'target residual concentration (mg/l)': 1.0,
            'target concentration of dosing chemical': 10.0,
            'target_residual_concentration_mg_per_l': 0.5,
            'baffling factor': 1.0,
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
        self.wq_parameters = {
            'E. coli': {'input_parameter': 500.0},
            'trihalomethanes': {
                'input_parameter': 0.0,
                'target_parameter': 80.0,
            },
            'haloacetic acids': {
                'input_parameter': 0.0,
                'target_parameter': 40.0,
            },
        }

    def test_init(self):
        chlorine_disinfection = ChlorineDisinfection(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            wq_parameters=self.wq_parameters,
            digest_parameter_list=['volume'],
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
            wq_parameters=self.wq_parameters,
            digest_parameter_list=['volume'],
        )
        daily_mass_kg = chlorine_disinfection.daily_mass_of_chemicals__kg
        self.assertIsInstance(daily_mass_kg, dict)
        self.assertGreaterEqual(sum(daily_mass_kg.values()), 0.0)

    def test_get_kpi_dict(self):
        chlorine_disinfection = ChlorineDisinfection(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            wq_parameters=self.wq_parameters,
            chem_parameters=['chlorine'],
            digest_parameter_list=['volume'],
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
            'baffling factor': 1.0,
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
        self.wq_parameters = {
            'E. coli': {'input_parameter': 500.0},
            'trihalomethanes': {
                'input_parameter': 0.0,
                'target_parameter': 80.0,
            },
            'haloacetic acids': {
                'input_parameter': 0.0,
                'target_parameter': 40.0,
            },
        }

    def test_init(self):
        chloramine = ChloramineDisinfection(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            wq_parameters=self.wq_parameters,
            chem_parameters=['chloramine'],
            digest_parameter_list=['volume'],
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
            wq_parameters=self.wq_parameters,
            chem_parameters=['chloramine'],
            digest_parameter_list=['volume'],
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
        self.wq_parameters = {
            'E. coli': {'input_parameter': 500.0},
            'UV 254': {'input_parameter': 3.5},
            'bromate': {
                'input_parameter': 0.0,
                'target_parameter': 10.0,
            },
            'assimilable organic carbon': {'input_parameter': 30.0},
            'bromide': {'input_parameter': 0.048},
        }

    def test_init(self):
        ozone = BaffledOzonationContactor(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            wq_parameters=self.wq_parameters,
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
            wq_parameters=self.wq_parameters,
            chem_parameters=['ozone'],
            digest_parameter_list=['volume'],
        )
        kpi_results = ozone.get_kpi_dict()
        self.assertIn('footprint area', kpi_results)
        self.assertAlmostEqual(
            ozone.footprint_area__m2, 16.0, places=1)
        self.assertIn('daily mass of chemicals', kpi_results)
        self.assertEqual(
            ozone.daily_mass_of_chemicals__kg['ozone'],
            ozone.nominal_flow_m3perh * 24 * ozone.ozone_dosage_mgliter / 1000)
        self.assertIn('head loss', kpi_results)
        self.assertAlmostEqual(
            ozone.hydraulic_headloss__bar, 0.539, places=1)
        self.assertIn('CO2 equivalent emissions', kpi_results)
        self.assertAlmostEqual(
            ozone.co2_emissions__kg_co2_eq_per_m3, 0.0108, places=4)


class TestUVDisinfection(unittest.TestCase):
    def setUp(self):
        self.parameters = {
            'units per lane': 2,
            'UV dose': 40.0,
            'UV power intensity': 10.0,
            'tank height': 0.2,
            'UV power per m3':0.04,
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
        self.assertEqual(
            uv.units_per_lane, self.parameters['units per lane'] + 1)
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

class TestCIEX(unittest.TestCase):
    def setUp(self):
        self.parameters = {
            'units per lane': 2.5,
            'regeneration duration': 10.0,
            'tank height': 2,
            'storage time of chemicals (days)': 20,
            'chemical emission factor': 0.5,
            'mass density of chemical':1.2,
            'power efficiency of pump(s)': 80,
        }
        self.design_parameters = {
            'number of lanes': 2,
            'emission factor (electricity)': 0.45,
        }
        self.plant_kpis = {
            'nominal flow rate': 100.0,
        }

        self.wq_parameters = {
            'total hardness': {
                'input_parameter': 320.0,
                'target_parameter': 80.0,
            }
        }
        self.kpi_results = {
            'footprint area': 2.0,
            'footprint area for chemicals': 10.0,
            'daily energy consumption': 192.0,
            'daily mass of chemicals': 150,
            'chemical solution concentration': 0.0,
            'head loss': 0.11961322716039698,
            'power': 0.7705051688871006,
            'CO2 equivalent emissions': 0.02}

    def test_init(self):
        ciex = CationIonExchange(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            digest_parameter_list=['area'],
            wq_parameters=self.wq_parameters,
        )
        self.assertEqual(
            ciex.units_per_lane, self.parameters['units per lane'] + 1)
        self.assertEqual(ciex.tank_height_m, self.parameters['tank height'])
        self.assertEqual(ciex.nominal_flow_m3perh, self.plant_kpis['nominal flow rate'])

    def test_get_kpi_dict(self):
        ciex = CationIonExchange(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            digest_parameter_list=['area'],
            wq_parameters=self.wq_parameters,
        )
        kpi_results = ciex.get_kpi_dict()
        self.maxDiff = None
        self.assertIn('footprint area', kpi_results)
        self.assertIn('daily mass of chemicals', kpi_results)
        self.assertIn('head loss', kpi_results)
        self.assertIn('CO2 equivalent emissions', kpi_results)
        self.assertDictEqual(kpi_results, self.kpi_results)

        
class TestAIEX(unittest.TestCase):
    def setUp(self):
        self.parameters = {
            'units per lane': 2.5,
            'empty bed contact time': 4,
            'regeneration duration': 10.0,
            'bed height': 2,
            'resin volume exchange': 18,
            'storage time of chemicals (days)': 20,
            'chemical emission factor': 0.5,
            'mass density of chemical':1.2,
            'power efficiency of pump(s)': 80,
        }
        self.design_parameters = {
            'number of lanes': 2,
            'emission factor (electricity)': 0.45,
        }
        self.plant_kpis = {
            'nominal flow rate': 100.0,
        }

        self.wq_parameters = {
            'dissolved organic carbon': {
                'input_parameter': 20.0,
                'target_parameter': 3.0,
            }
        }
        self.kpi_results = {
            'footprint area': 16.0,
            'footprint area for chemicals': 0.0,
            'daily energy consumption': 169.34587293875427,
            'daily mass of chemicals': {},
            'chemical solution concentration': 0.0,
            'head loss': 1.9347512565300826,
            'power': 7.056078039114761,
            'CO2 equivalent emissions': 0.03175235117601643}

    def test_init(self):
        aiex = AnionicIEX(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            digest_parameter_list=['area'],
            wq_parameters=self.wq_parameters,
        )
        self.assertEqual(
            aiex.units_per_lane, self.parameters['units per lane'] + 1)
        self.assertEqual(aiex.bed_height_m, self.parameters['bed height'])
        self.assertEqual(aiex.nominal_flow_m3perh, self.plant_kpis['nominal flow rate'])

    def test_get_kpi_dict(self):
        aiex = AnionicIEX(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            digest_parameter_list=['area'],
            wq_parameters=self.wq_parameters,
        )
        kpi_results = aiex.get_kpi_dict()
        self.maxDiff = None
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

class TestPellet(unittest.TestCase):
    def setUp(self):
        self.parameters = {
            'tank height': 6.0,
            'tank height chemical storage': 4.0,
            'target residual concentration (mg/l)': 1.0,
            'target concentration of dosing chemical': 10.0,
            'target upflow velocity': 1.5,
            'static height of pellet bed': 2,
            'pellet porosity static': 0.4,
            'pellet porosity expanded': 0.6,
            'mass density of chemical': 1.2,
            'mass density of pellets': 2.7,
            'power efficiency of pump(s)': 0.8,
            'lime dosage mass fraction': 12.0,
            'units per lane': 5,
            'storage time of chemicals (days)': 20,
            'chemical emission factor': 0.00087,
        }
        self.design_parameters = {
            'number of lanes': 2,
            'emission factor (electricity)': 0.45,
        }
        self.wq_parameters = {
            'total hardness': {
                'input_parameter': 320.0,
                'target_parameter': 80.0,
            }
        }
        self.plant_kpis = {
            'nominal flow rate': 200.0,
        }

    def test_init(self):
        pellet = PelletSoftening(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            digest_parameter_list=['area'],
            wq_parameters=self.wq_parameters,
        )
        self.assertTrue(pellet.units_per_lane == self.parameters['units per lane'])  # noqa, E501
        self.assertTrue(pellet.nominal_flow_m3perh == self.plant_kpis['nominal flow rate'])  # noqa, E501

    def test_daily_mass_chemicals(self):
        pellet = PelletSoftening(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            digest_parameter_list=['area'],
            wq_parameters=self.wq_parameters
        )
        daily_mass_kg = pellet.daily_mass_of_chemicals__kg
        self.assertIsInstance(daily_mass_kg, dict)
        self.assertGreaterEqual(sum(daily_mass_kg.values()), 0.0)

    def test_get_kpi_dict(self):
        pellet = PelletSoftening(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            digest_parameter_list=['area'],
            wq_parameters=self.wq_parameters
        )
        kpi_results = pellet.get_kpi_dict()
        self.assertIn('footprint area', kpi_results)
        self.assertIn('daily mass of chemicals', kpi_results)
        self.assertIn('head loss', kpi_results)
        self.assertIn('CO2 equivalent emissions', kpi_results)

    # TODO: Add more tests for ChlorineDisinfection methods

class TestMembranes(unittest.TestCase):
    def setUp(self):
        self.parameters = {
            TPN['units_per_lane']: 3,
            TPN['membrane_recovery_rate']: 80,
            TPN['power_efficiency_of_pumps']: 80,
            TPN['pressure_head']: 5,
            TPN['membrane_flux']: 20,
            TPN['operating_membrane_area']: 40,
            TPN['membranes_per_vessel']: 100,
            TPN['vessel_footprint']: 3.0,
        }
        self.design_parameters = {
            'number of lanes': 2,
            'emission factor (electricity)': 0.45,
        }
        self.plant_kpis = {
            'nominal flow rate': 100.0,
        }


    def test_init(self):
        membrane = MembraneFiltration(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
        )
        self.assertEqual(
            membrane.units_per_lane,
            self.parameters[TPN['units_per_lane']],
        )
        self.assertEqual(
            membrane.nominal_flow_m3perh,
            self.plant_kpis['nominal flow rate'],
        )

    def test_get_kpi_dict(self):
        membrane = MembraneFiltration(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
        )
        kpi_results = membrane.get_kpi_dict()
        self.assertIn('footprint area', kpi_results)
        self.assertIn('daily mass of chemicals', kpi_results)
        self.assertIn('head loss', kpi_results)
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
            'tank height': 3.0,
            'retention time (min)': 600.0,
            'scraper power coefficient': 0.1,
            'units per lane': 3,
            'surface overflow rate': 5.0,
        }
        self.design_parameters = {
            'number of lanes': 2,
            'emission factor (electricity)': 0.45,
        }
        self.plant_kpis = {
            'nominal flow rate': 100.0,
        }
        self.wq_parameters = {
            'total suspended solids': {'input_parameter': 15.0},
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
            digest_parameter_list = ['area']
        )
        self.assertTrue(sedimentation.scraper_power_coeff_kw_m2 == self.parameters['scraper power coefficient'])  # noqa, E501
        self.assertTrue(sedimentation.retention_time_min == self.parameters['retention time (min)'])  # noqa, E501
        self.assertTrue(sedimentation.lanes == self.design_parameters['number of lanes'])  # noqa, E501
        self.assertTrue(sedimentation.nominal_flow_m3perh == self.plant_kpis['nominal flow rate'])  # noqa, E501

    def test_get_kpi(self):
        sedimentation = ChainScrapedSedimentation(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            wq_parameters=self.wq_parameters,
            digest_parameter_list = ['area']
        )
        result = sedimentation.get_kpi('footprint area')
        self.assertEqual(
            result, sedimentation.footprint_area__m2)
        result = sedimentation.get_kpi('head loss')
        self.assertEqual(
            result, sedimentation.hydraulic_headloss__bar)

    def test_footprint_area(self):
        sedimentation = ChainScrapedSedimentation(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            wq_parameters=self.wq_parameters,
            digest_parameter_list = ['area']
        )
        area = sedimentation.footprint_area__m2
        self.assertGreater(area, 0.0)

    def test_pressure_head(self):
        sedimentation = ChainScrapedSedimentation(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            wq_parameters=self.wq_parameters,
            digest_parameter_list = ['area']
        )
        headloss = sedimentation.hydraulic_headloss__bar
        self.assertGreater(headloss, 0.0)

    def test_daily_energy_consumption(self):
        sedimentation = ChainScrapedSedimentation(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            wq_parameters=self.wq_parameters,
            digest_parameter_list = ['area']
        )
        energy = sedimentation.daily_energy_consumption__kwh
        self.assertGreater(energy, 0.0)

    def test_kpi_dict(self):
        sedimentation = ChainScrapedSedimentation(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            wq_parameters=self.wq_parameters,
            digest_parameter_list = ['area']
        )
        kpi_results = sedimentation.get_kpi_dict()
        self.assertIn('footprint area', kpi_results)
        self.assertIn('head loss', kpi_results)
        self.assertIn('daily energy consumption', kpi_results)
        self.assertIn('CO2 equivalent emissions', kpi_results)
    
    def test_pressure_head(self):
        sedimentation = ChainScrapedSedimentation(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            wq_parameters=self.wq_parameters,
            digest_parameter_list = ['area']
        )
        headloss = sedimentation.hydraulic_headloss__bar
        self.assertGreater(headloss, 0.0)

    def test_co2_emissions(self):
        sedimentation = ChainScrapedSedimentation(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            wq_parameters=self.wq_parameters,
            digest_parameter_list = ['area']
        )
        emissions = sedimentation.co2_emissions__kg_co2_eq_per_m3
        self.assertGreater(emissions, 0.0)

class TestSludgeBlanketSedimentation(unittest.TestCase):
    def setUp(self):
        self.parameters = {
            'tank height': 3.0,
            'retention time (min)': 600.0,
            'scraper power coefficient': 0.1,
            'backwash filtration rate': 50,
            'backwash duration': 15,
            'backwash tank height' : 1,
            'sludge tank height': 5.0,
            'units per lane': 3,
            'surface overflow rate': 5.0,#
            'mass density of TSS': 30,
            'power efficiency of pump(s)': 0.8,
            'power density': 0.05
        }
        self.design_parameters = {
            'number of lanes': 2,
            'emission factor (electricity)': 0.45,
        }
        self.plant_kpis = {
            'nominal flow rate': 100.0,
        }
        self.wq_parameters = {
            'total suspended solids': {
                'input_parameter': 15.0,
                'target_parameter': 5.0,
            }}

    def test_init(self):
        sludge = SludgeBlanketClarifier(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            wq_parameters=self.wq_parameters,
            digest_parameter_list = ['area']
        )
        self.assertTrue(sludge.scraper_power_coeff_w_m2 == self.parameters['scraper power coefficient'])  # noqa, E501
        self.assertTrue(sludge.retention_time_min == self.parameters['retention time (min)'])  # noqa, E501
        self.assertTrue(sludge.lanes == self.design_parameters['number of lanes'])  # noqa, E501
        self.assertTrue(sludge.nominal_flow_m3perh == self.plant_kpis['nominal flow rate'])  # noqa, E501

    def test_get_kpi(self):
        sludge = SludgeBlanketClarifier(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            wq_parameters=self.wq_parameters,
            digest_parameter_list = ['area']
        )
        result = sludge.get_kpi('footprint area')
        self.assertEqual(
            result, sludge.footprint_area__m2)
        result = sludge.get_kpi('head loss')
        self.assertEqual(
            result, sludge.hydraulic_headloss__bar)

    def test_footprint_area(self):
        sludge = SludgeBlanketClarifier(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            wq_parameters=self.wq_parameters,
            digest_parameter_list = ['area']
        )
        area = sludge.footprint_area__m2
        self.assertGreater(area, 0.0)

    def test_pressure_head(self):
        sludge = SludgeBlanketClarifier(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            wq_parameters=self.wq_parameters,
            digest_parameter_list = ['area']
        )
        headloss = sludge.hydraulic_headloss__bar
        self.assertGreater(headloss, 0.0)

    def test_daily_energy_consumption(self):
        sludge = SludgeBlanketClarifier(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            wq_parameters=self.wq_parameters,
            digest_parameter_list = ['area']
        )
        energy = sludge.daily_energy_consumption__kwh
        self.assertGreater(energy, 0.0)

    def test_kpi_dict(self):
        sludge = SludgeBlanketClarifier(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            wq_parameters=self.wq_parameters,
            digest_parameter_list = ['area']
        )
        kpi_results = sludge.get_kpi_dict()
        self.assertIn('footprint area', kpi_results)
        self.assertIn('head loss', kpi_results)
        self.assertIn('daily energy consumption', kpi_results)
        self.assertIn('CO2 equivalent emissions', kpi_results)
    
    def test_pressure_head(self):
        sludge = SludgeBlanketClarifier(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            wq_parameters=self.wq_parameters,
            digest_parameter_list = ['area']
        )
        headloss = sludge.hydraulic_headloss__bar
        self.assertGreater(headloss, 0.0)

    def test_co2_emissions(self):
        sludge = SludgeBlanketClarifier(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            wq_parameters=self.wq_parameters,
            digest_parameter_list = ['area']
        )
        emissions = sludge.co2_emissions__kg_co2_eq_per_m3
        self.assertGreater(emissions, 0.0)

class TestLamellaSlope(unittest.TestCase):
    def setUp(self):
        LamellaClarifierSlope.flow_m3perh = property(  # type: ignore[attr-defined]
            lambda instance: instance.nominal_flow_m3perh
        )

        self.parameters = {
            'tank height': 4.0,
            'scraper power coefficient': 0.1,
            'retention time (min)': 60.0,
            'surface overflow rate': 20,
            'plate angle' : 60,
            'units per lane': 3,
            'sludge tank height': 5.0,
            'backwash filtration rate': 50,
            'backwash duration': 15,
            'backwash tank height' : 1,
            'mass density of TSS': 30,
            'power efficiency of pump(s)': 0.8

        }
        self.design_parameters = {
            'number of lanes': 2,
            'emission factor (electricity)': 0.45,
        }
        self.plant_kpis = {
            'nominal flow rate': 120.0,
        }
        self.wq_parameters = {
            'total suspended solids': {
                'input_parameter': 15.0,
                'target_parameter': 5.0,
            }}

    def test_init(self):
        lamellaslope = LamellaClarifierSlope(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            wq_parameters=self.wq_parameters,
            digest_parameter_list = ['area']
        )
        self.assertTrue(lamellaslope.scraper_power_coeff_kw_m2 == self.parameters['scraper power coefficient'])  # noqa, E501
        self.assertTrue(lamellaslope.lanes == self.design_parameters['number of lanes'])  # noqa, E501
        self.assertTrue(lamellaslope.flow_m3perh == self.plant_kpis['nominal flow rate'])  # noqa, E501

    def test_get_kpi(self):
        lamellaslope = LamellaClarifierSlope(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            wq_parameters=self.wq_parameters,
            digest_parameter_list = ['area']
        )
        result = lamellaslope.get_kpi('footprint area')
        self.assertEqual(
            result, lamellaslope.footprint_area__m2)
        result = lamellaslope.get_kpi('head loss')
        self.assertEqual(
            result, lamellaslope.hydraulic_headloss__bar)

    def test_footprint_area(self):
        lamellaslope = LamellaClarifierSlope(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            wq_parameters=self.wq_parameters,
            digest_parameter_list = ['area']
        )
        area = lamellaslope.footprint_area__m2
        self.assertGreater(area, 0.0)

    def test_pressure_head(self):
        lamellaslope = LamellaClarifierSlope(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            wq_parameters=self.wq_parameters,
            digest_parameter_list = ['area']
        )
        headloss = lamellaslope.hydraulic_headloss__bar
        self.assertGreater(headloss, 0.0)

    def test_daily_energy_consumption(self):
        lamellaslope = LamellaClarifierSlope(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            wq_parameters=self.wq_parameters,
            digest_parameter_list = ['area']
        )
        energy = lamellaslope.daily_energy_consumption__kwh
        self.assertGreater(energy, 0.0)

    def test_kpi_dict(self):
        lamellaslope = LamellaClarifierSlope(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            wq_parameters=self.wq_parameters,
            digest_parameter_list = ['area']
        )
        kpi_results = lamellaslope.get_kpi_dict()
        self.assertIn('footprint area', kpi_results)
        self.assertIn('head loss', kpi_results)
        self.assertIn('daily energy consumption', kpi_results)
        self.assertIn('CO2 equivalent emissions', kpi_results)
    
    def test_pressure_head(self):
        lamellaslope = LamellaClarifierSlope(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            wq_parameters=self.wq_parameters,
            digest_parameter_list = ['area']
        )
        headloss = lamellaslope.hydraulic_headloss__bar
        self.assertGreater(headloss, 0.0)

    def test_co2_emissions(self):
        lamellaslope = LamellaClarifierSlope(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            wq_parameters=self.wq_parameters,
            digest_parameter_list = ['area']
        )
        emissions = lamellaslope.co2_emissions__kg_co2_eq_per_m3
        self.assertGreater(emissions, 0.0)

class TestLamellahorizontal(unittest.TestCase):
    def setUp(self):
        LamellaClarifierHorizontal.flow_m3perh = property(  # type: ignore[attr-defined]
            lambda instance: instance.nominal_flow_m3perh
        )

        self.parameters = {
            'tank height': 4.0,
            'scraper power coefficient': 0.1,
            'retention time (min)': 60.0,
            'surface overflow rate': 20,
            'units per lane': 3,
            'sludge tank height': 5.0,
            'backwash filtration rate': 50,
            'backwash duration': 15,
            'backwash tank height' : 1,
            'mass density of TSS': 30,
            'power efficiency of pump(s)': 0.8

        }
        self.design_parameters = {
            'number of lanes': 2,
            'emission factor (electricity)': 0.45,
        }
        self.plant_kpis = {
            'nominal flow rate': 120.0,
        }
        self.wq_parameters = {
            'total suspended solids': {
                'input_parameter': 15.0,
                'target_parameter': 5.0,
            }}

    def test_init(self):
        lamella = LamellaClarifierHorizontal(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            wq_parameters=self.wq_parameters,
            digest_parameter_list = ['area']
        )
        self.assertTrue(lamella.scraper_power_coeff_kw_m2 == self.parameters['scraper power coefficient'])  # noqa, E501
        self.assertTrue(lamella.lanes == self.design_parameters['number of lanes'])  # noqa, E501
        self.assertTrue(lamella.nominal_flow_m3perh  == self.plant_kpis['nominal flow rate'])  # noqa, E501

    def test_get_kpi(self):
        lamella = LamellaClarifierHorizontal(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            wq_parameters=self.wq_parameters,
            digest_parameter_list = ['area']
        )
        result = lamella.get_kpi('footprint area')
        self.assertEqual(
            result, lamella.footprint_area__m2)
        result = lamella.get_kpi('head loss')
        self.assertEqual(
            result, lamella.hydraulic_headloss__bar)

    def test_footprint_area(self):
        lamella = LamellaClarifierHorizontal(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            wq_parameters=self.wq_parameters,
            digest_parameter_list = ['area']
        )
        area = lamella.footprint_area__m2
        self.assertGreater(area, 0.0)

    def test_pressure_head(self):
        lamella = LamellaClarifierHorizontal(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            wq_parameters=self.wq_parameters,
            digest_parameter_list = ['area']
        )
        headloss = lamella.hydraulic_headloss__bar
        self.assertGreater(headloss, 0.0)

    def test_daily_energy_consumption(self):
        lamella = LamellaClarifierHorizontal(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            wq_parameters=self.wq_parameters,
            digest_parameter_list = ['area']
        )
        energy = lamella.daily_energy_consumption__kwh
        self.assertGreater(energy, 0.0)

    def test_kpi_dict(self):
        lamella = LamellaClarifierHorizontal(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            wq_parameters=self.wq_parameters,
            digest_parameter_list = ['area']
        )
        kpi_results = lamella.get_kpi_dict()
        self.assertIn('footprint area', kpi_results)
        self.assertIn('head loss', kpi_results)
        self.assertIn('daily energy consumption', kpi_results)
        self.assertIn('CO2 equivalent emissions', kpi_results)
    
    def test_pressure_head(self):
        lamella = LamellaClarifierHorizontal(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            wq_parameters=self.wq_parameters,
            digest_parameter_list = ['area']
        )
        headloss = lamella.hydraulic_headloss__bar
        self.assertGreater(headloss, 0.0)

    def test_co2_emissions(self):
        lamella = LamellaClarifierHorizontal(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            wq_parameters=self.wq_parameters,
            digest_parameter_list = ['area']
        )
        emissions = lamella.co2_emissions__kg_co2_eq_per_m3
        self.assertGreater(emissions, 0.0)

class TestDAF(unittest.TestCase):
    def setUp(self):
        AirFlotationDAF.flow_m3perh = property(  # type: ignore[attr-defined]
            lambda instance: instance.nominal_flow_m3perh
        )

        self.parameters = {
            'tank height': 4.0,
            'air solids ratio': 0.05,
            'mass density of air' : 1204, 
            'retention time (min)': 60.0,
            'surface overflow rate': 20,
            'recirculation ratio' : 0.2,
            'units per lane': 3,
            'air_pressure_difference': 600,
            'backwash filtration rate': 50,
            'backwash duration': 15,
            'backwash tank height' : 1,
            'mass density of TSS': 30,
            'power efficiency': 0.8 

        }
        self.design_parameters = {
            'number of lanes': 2,
            'emission factor (electricity)': 0.45,
        }
        self.plant_kpis = {
            'nominal flow rate': 120.0,
        }
        self.wq_parameters = {
            'total suspended solids': {
                'input_parameter': 15.0,
                'target_parameter': 5.0,
            }}
    def test_init(self):
        daf = AirFlotationDAF(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            wq_parameters=self.wq_parameters,
            digest_parameter_list = ['area']
        )
        self.assertTrue(daf.lanes == self.design_parameters['number of lanes'])  # noqa, E501
        self.assertTrue(daf.flow_m3perh == self.plant_kpis['nominal flow rate'])  # noqa, E501

    def test_get_kpi(self):
        daf = AirFlotationDAF(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            wq_parameters=self.wq_parameters,
            digest_parameter_list = ['area']
        )
        result = daf.get_kpi('footprint area')
        self.assertEqual(
            result, daf.footprint_area__m2)
        result = daf.get_kpi('head loss')
        self.assertEqual(
            result, daf.hydraulic_headloss__bar)

    def test_footprint_area(self):
        daf = AirFlotationDAF(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            wq_parameters=self.wq_parameters,
            digest_parameter_list = ['area']
        )
        area = daf.footprint_area__m2
        self.assertGreater(area, 0.0)

    def test_pressure_head(self):
        daf = AirFlotationDAF(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            wq_parameters=self.wq_parameters,
            digest_parameter_list = ['area']
        )
        headloss = daf.hydraulic_headloss__bar
        self.assertGreater(headloss, 0.0)

    def test_daily_energy_consumption(self):
        daf = AirFlotationDAF(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            wq_parameters=self.wq_parameters,
            digest_parameter_list = ['area']
        )
        energy = daf.daily_energy_consumption__kwh
        self.assertGreater(energy, 0.0)

    def test_kpi_dict(self):
        daf = AirFlotationDAF(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            wq_parameters=self.wq_parameters,
            digest_parameter_list = ['area']
        )
        kpi_results = daf.get_kpi_dict()
        self.assertIn('footprint area', kpi_results)
        self.assertIn('head loss', kpi_results)
        self.assertIn('daily energy consumption', kpi_results)
        self.assertIn('CO2 equivalent emissions', kpi_results)
    
    def test_pressure_head(self):
        daf = AirFlotationDAF(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            wq_parameters=self.wq_parameters,
            digest_parameter_list = ['area']
        )
        headloss = daf.hydraulic_headloss__bar
        self.assertGreater(headloss, 0.0)

    def test_co2_emissions(self):
        daf = AirFlotationDAF(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            wq_parameters=self.wq_parameters,
            digest_parameter_list = ['area']
        )
        emissions = daf.co2_emissions__kg_co2_eq_per_m3
        self.assertGreater(emissions, 0.0)

class TestRSFSingle(unittest.TestCase):
    def setUp(self):
        self.parameters = {
            TPN['units_per_lane']: 2,
            TPN['filtration_rate']: 60,
            TPN['sand_porosity']: 0.4,
            TPN['sand_density']: 2800,
            TPN['sand_media_grain_size']:0.45,
            TPN['backwash_duration']: 30,
            TPN['backwash_tank_height']: 2,
            TPN['backwash_filtration_rate']: 120,
            TPN['power_efficiency_of_pumps']:70,
            TPN['sand_filter_bed_height']:2
        }
        self.design_parameters = {
            'number of lanes': 2,
            'emission factor (electricity)': 0.45,
        }
        self.plant_kpis = {
            'nominal flow rate': 100.0,
        }
        self.wq_parameters = {
            'total suspended solids': {
                'input_parameter': 15.0, 'target_parameter': 5.0}
                }
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
    
    def test_kpi_dict(self):
        rsf_single = RapidSandSingleMediumFiltration(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            wq_parameters=self.wq_parameters,
            digest_parameter_list=['filter area'],
        )
        kpi_results = rsf_single.get_kpi_dict()
        self.assertIn('footprint area', kpi_results)
        self.assertIn('head loss', kpi_results)
        self.assertIn('daily energy consumption', kpi_results)
        self.assertIn('CO2 equivalent emissions', kpi_results)

    def test_footprint_area(self):
        rsf_single = RapidSandSingleMediumFiltration(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            wq_parameters=self.wq_parameters,
            digest_parameter_list=['filter area'],
        )
        area = rsf_single.footprint_area__m2
        self.assertGreater(area, 0.0)
    
    def test_pressure_head(self):
        rsf_single = RapidSandSingleMediumFiltration(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            wq_parameters=self.wq_parameters,
            digest_parameter_list=['filter area'],
        )
        headloss = rsf_single.hydraulic_headloss__bar
        self.assertGreater(headloss, 0.0)
    
    def test_daily_energy_consumption(self):
        rsf_single = RapidSandSingleMediumFiltration(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            wq_parameters=self.wq_parameters,
            digest_parameter_list=['filter area'],
        )
        energy = rsf_single.daily_energy_consumption__kwh
        self.assertGreater(energy, 0.0)
    
    def test_co2_emissions(self):
        rsf_single = RapidSandSingleMediumFiltration(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            wq_parameters=self.wq_parameters,
            digest_parameter_list=['filter area'],
        )
        emissions = rsf_single.co2_emissions__kg_co2_eq_per_m3
        self.assertGreater(emissions, 0.0)

class TestRSFDouble(unittest.TestCase):
    def setUp(self):
        self.parameters = {
            TPN['units_per_lane']: 2,
            TPN['filtration_rate']: 60,
            TPN['backwash_tank_height']:0.5,
            TPN['backwash_filtration_rate']:30,
            TPN['sand_porosity']: 0.4,
            TPN['sand_density']: 2800,
            TPN['sand_media_grain_size']:0.45,
            TPN['backwash_duration']: 30,
            TPN['backwash_tank_height']: 2,
            TPN['power_efficiency_of_pumps']:70,
            TPN['sand_filter_bed_height']: 0.5,
            TPN['anthracite_filter_bed_height']:0.7,
            TPN['anthracite_porosity']: 0.6,
            TPN['anthracite_density']: 1400,
            TPN['anthracite_media_grain_size']: 0.8
        }
        self.design_parameters = {
            'number of lanes': 2,
            'emission factor (electricity)': 0.45,
        }
        self.plant_kpis = {
            'nominal flow rate': 100.0,
        }
        self.wq_parameters = {
            'total suspended solids': {
                'input_parameter': 15.0, 'target_parameter': 5.0}
        }
        
    def test_init(self):
        rsf_double = RapidSandDoubleMediumFiltration(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            wq_parameters=self.wq_parameters,
            digest_parameter_list=['filter area'],
        )
        self.assertTrue(rsf_double.units_per_lane == self.parameters[TPN['units_per_lane']])  # noqa, E501
        self.assertTrue(rsf_double.hydraulic_loading_rate_m3m2h == self.parameters[TPN['filtration_rate']])  # noqa, E501
    
    def test_kpi_dict(self):
        rsf_double = RapidSandDoubleMediumFiltration(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            wq_parameters=self.wq_parameters,
            digest_parameter_list=['filter area'],
        )
        kpi_results = rsf_double.get_kpi_dict()
        self.assertIn('footprint area', kpi_results)
        self.assertIn('head loss', kpi_results)
        self.assertIn('daily energy consumption', kpi_results)
        self.assertIn('CO2 equivalent emissions', kpi_results)

    
    def test_footprint_area(self):
        rsf_double = RapidSandDoubleMediumFiltration(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            wq_parameters=self.wq_parameters,
            digest_parameter_list=['filter area'],
        )
        area = rsf_double.footprint_area__m2
        self.assertGreater(area, 0.0)
    
    def test_pressure_head(self):
        rsf_double = RapidSandDoubleMediumFiltration(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            wq_parameters=self.wq_parameters,
            digest_parameter_list=['filter area'],
        )
        headloss = rsf_double.hydraulic_headloss__bar
        self.assertGreater(headloss, 0.0)
    
    def test_daily_energy_consumption(self):
        rsf_double = RapidSandDoubleMediumFiltration(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            wq_parameters=self.wq_parameters,
            digest_parameter_list=['filter area'],
        )
        energy = rsf_double.daily_energy_consumption__kwh
        self.assertGreater(energy, 0.0)

    def test_co2_emissions(self):
        rsf_double = RapidSandDoubleMediumFiltration(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            wq_parameters=self.wq_parameters,
            digest_parameter_list=['filter area'],
        )
        emissions = rsf_double.co2_emissions__kg_co2_eq_per_m3
        self.assertGreater(emissions, 0.0)

class TestRSFPress(unittest.TestCase):
    def setUp(self):
        self.parameters = {
            'units per lane': 2.5,
            'backwash duration': 30,
            'backwash tank height': 2.0,
            'backwash filtration rate': 2,
            'power efficiency of pump(s)': 80,
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
        rsf_press = RapidSandPressurizedVesselFiltration(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            wq_parameters=self.wq_parameters,
            digest_parameter_list=['filter area'],
        )
        self.assertEqual(
            rsf_press.units_per_lane,
            self.parameters[TPN['units_per_lane']] + 1,
        )
        #self.assertTrue(rsf_press.hydraulic_loading_rate_m3m2h == self.parameters[TPN['filtration_rate']])  # noqa, E501
    
    def test_get_kpi_dict(self):
        rsf_press = RapidSandPressurizedVesselFiltration(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            wq_parameters=self.wq_parameters,
            digest_parameter_list=['filter area'],
        )
        kpi_results = rsf_press.get_kpi_dict()
        self.maxDiff = None
        self.assertIn('footprint area', kpi_results)
        self.assertIn('daily mass of chemicals', kpi_results)
        self.assertIn('head loss', kpi_results)
        self.assertIn('CO2 equivalent emissions', kpi_results)
        self.assertDictEqual(kpi_results, self.kpi_results)

class TestGAC(unittest.TestCase):
    def setUp(self):
        self.parameters = {
            TPN['units_per_lane']: 1,
            TPN['filtration_rate']: 15,
            TPN['gac_porosity']: 0.5,
            TPN['mass_density_of_chemical']: 0.5,
            TPN['empty_bed_contact_time']: 15,
            TPN['grain_diameter']: 0.5,
            TPN['chemical_emission_factor']: 10.2,
            TPN['gac_regeneration_interval']: 182,
            TPN['regeneration_energy_per_kg_of_gac']: 5,
        }
        self.design_parameters = {
            'number of lanes': 2,
            'emission factor (electricity)': 0.45,
        }
        self.plant_kpis = {
            'nominal flow rate': 100.0,
        }
        self.wq_parameters = {
            'dissolved organic carbon': {
                'input_parameter': 3.0,
                'target_parameter': 1.0,
            }
        }

    def test_init(self):
        gac = GranularActivatedCarbonFiltration(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            wq_parameters=self.wq_parameters,
            digest_parameter_list=['volume'],
        )
        self.assertTrue(gac.units_per_lane == self.parameters[TPN['units_per_lane']])  # noqa, E501
        self.assertTrue(gac.hydraulic_loading_rate_m3m2h == self.parameters[TPN['filtration_rate']])  # noqa, E501
    
    def test_kpi_dict(self):
        gac = GranularActivatedCarbonFiltration(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            wq_parameters=self.wq_parameters,
            digest_parameter_list=['volume'],
        )
        kpi_results = gac.get_kpi_dict()
        self.assertIn('footprint area', kpi_results)
        self.assertIn('head loss', kpi_results)
        self.assertIn('daily energy consumption', kpi_results)
        self.assertIn('CO2 equivalent emissions', kpi_results)

    
    def test_footprint_area(self):
        gac = GranularActivatedCarbonFiltration(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            wq_parameters=self.wq_parameters,
            digest_parameter_list=['volume'],
        )
        area = gac.footprint_area__m2
        self.assertGreater(area, 0.0)
    
    def test_pressure_head(self):
        gac = GranularActivatedCarbonFiltration(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            wq_parameters=self.wq_parameters,
            digest_parameter_list=['volume'],
        )
        headloss = gac.hydraulic_headloss__bar
        self.assertGreater(headloss, 0.0)
    
    def test_daily_energy_consumption(self):
        gac = GranularActivatedCarbonFiltration(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            wq_parameters=self.wq_parameters,
            digest_parameter_list=['volume'],
        )
        energy = gac.daily_energy_consumption__kwh
        self.assertGreaterEqual(energy, 0.0)
    
    def test_co2_emissions(self):
        gac = GranularActivatedCarbonFiltration(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            wq_parameters=self.wq_parameters,
            digest_parameter_list=['volume'],
        )
        emissions = gac.co2_emissions__kg_co2_eq_per_m3
        self.assertGreaterEqual(emissions, 0.0)

class TestPAC(unittest.TestCase):
    def setUp(self):
        self.parameters = {
            TPN['units_per_lane']: 2,
            TPN['tank_height']: 3,
            TPN['filtration_rate']: 60,
            TPN['sand_porosity']: 0.4,
            TPN['gac_porosity']: 2800,
            TPN['empty_bed_contact_time']:0.45,
            TPN['grain_diameter']:0.5,
            TPN['chemical_emission_factor']: 0.012, 
            TPN['pac_dosage_concentration']: 12,
            TPN['slurry_tank_height']: 3,
            TPN['pac_slurry_concentration']: 1500,
            TPN['power_density']: 0.05, 
            TPN['mass_density_of_chemical']: 0.45,
            TPN['retention_time_min']: 30

        }
        self.design_parameters = {
            'number of lanes': 2,
            'emission factor (electricity)': 0.45,
        }
        self.plant_kpis = {
            'nominal flow rate': 100.0,
        }
        self.wq_parameters = {}

    def test_init(self):
        pac = PowderedActivatedCarbonFiltration(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            wq_parameters=self.wq_parameters,
            digest_parameter_list=['area'],
        )
        self.assertTrue(pac.units_per_lane == self.parameters[TPN['units_per_lane']])  # noqa, E501
    
    def test_kpi_dict(self):
        pac = PowderedActivatedCarbonFiltration(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            wq_parameters=self.wq_parameters,
            digest_parameter_list=['area'],
        )
        kpi_results = pac.get_kpi_dict()
        self.assertIn('footprint area', kpi_results)
        self.assertIn('head loss', kpi_results)
        self.assertIn('daily energy consumption', kpi_results)
        self.assertIn('CO2 equivalent emissions', kpi_results)

    
    def test_footprint_area(self):
        pac = PowderedActivatedCarbonFiltration(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            wq_parameters=self.wq_parameters,
            digest_parameter_list=['area'],
        )
        area = pac.footprint_area__m2
        self.assertGreater(area, 0.0)
    
    def test_pressure_head(self):
        pac = PowderedActivatedCarbonFiltration(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            wq_parameters=self.wq_parameters,
            digest_parameter_list=['area'],
        )
        headloss = pac.hydraulic_headloss__bar
        self.assertGreater(headloss, 0.0)
    
    def test_daily_energy_consumption(self):
        pac = PowderedActivatedCarbonFiltration(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            wq_parameters=self.wq_parameters,
            digest_parameter_list=['area'],
        )
        energy = pac.daily_energy_consumption__kwh
        self.assertGreater(energy, 0.0)
    
    def test_co2_emissions(self):
        pac = PowderedActivatedCarbonFiltration(
            parameters=self.parameters,
            design_parameters=self.design_parameters,
            plant_kpis=self.plant_kpis,
            wq_parameters=self.wq_parameters,
            digest_parameter_list=['area'],
        )
        emissions = pac.co2_emissions__kg_co2_eq_per_m3
        self.assertGreater(emissions, 0.0)

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



