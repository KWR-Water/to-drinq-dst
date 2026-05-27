import csv
import json
from pathlib import Path

from django.test import TestCase as DjangoTestCase

from drinq.models import (
    Technology,
    TechnologyProperty,
    TechnologyPropertyJunction,
    WaterqualityParameter,
    WaterqualityParameterTechnologyJunction,
)
from drinq.utils.treatmentkpi import (
    BaffledOzonationContactor,
    CascadeMixerCoagulationDosing,
    ChainScrapedSedimentation,
    ChloramineDisinfection,
    ChlorineDisinfection,
    CleanWaterStorageTank,
    CoagulationDynamicMixing,
    INPUT_WQPARAMETER_KEY,
    RapidSandSingleMediumFiltration,
    Strainer,
    TARGET_WQPARAMETER_KEY,
    UVdisinfection,
    TPN,
)


class TestTechnologyKwargsFromDatabaseDefaults(DjangoTestCase):
    @classmethod
    def setUpTestData(cls):
        cls._load_default_snapshots()

    def setUp(self):
        self.design_parameters = {
            'number of lanes': 2,
            'emission factor (electricity)': 0.45,
        }
        self.plant_kpis = {
            'nominal flow rate': 100.0,
        }

    @classmethod
    def _load_default_snapshots(cls):
        if (
            TechnologyPropertyJunction.objects.exists()
            and WaterqualityParameterTechnologyJunction.objects.exists()
        ):
            return

        base_dir = (
            Path(__file__).resolve().parents[1]
            / 'research'
            / 'data'
            / 'database_tables'
        )

        with (base_dir / 'technology.csv').open(
            mode='r', encoding='utf-8-sig', newline=''
        ) as file_obj:
            for row in csv.DictReader(file_obj):
                Technology.objects.update_or_create(
                    id=int(row['id']),
                    defaults={
                        'name': row['name'],
                        'description': row.get('description') or None,
                    },
                )

        with (base_dir / 'technologyproperty.csv').open(
            mode='r', encoding='utf-8-sig', newline=''
        ) as file_obj:
            for row in csv.DictReader(file_obj):
                TechnologyProperty.objects.update_or_create(
                    id=int(row['id']),
                    defaults={
                        'name': row['name'],
                        'unit': row.get('unit') or None,
                        'description': row.get('description') or None,
                    },
                )

        with (base_dir / 'waterqualityparameter.csv').open(
            mode='r', encoding='utf-8-sig', newline=''
        ) as file_obj:
            for row in csv.DictReader(file_obj):
                WaterqualityParameter.objects.update_or_create(
                    id=int(row['id']),
                    defaults={
                        'name': row['name'],
                        'description': row.get('description') or None,
                        'unit': row.get('unit') or None,
                    },
                )

        with (base_dir / 'technology_property.csv').open(
            mode='r', encoding='utf-8-sig', newline=''
        ) as file_obj:
            for row in csv.DictReader(file_obj):
                TechnologyPropertyJunction.objects.update_or_create(
                    id=int(row['id']),
                    defaults={
                        'technology_id': int(row['technology']),
                        'property_id': int(row['property']),
                        'default_value': float(row['defaultvalue']),
                        'is_designparameter': bool(
                            int(row['is_designparameter'])
                        ),
                        'is_digested': bool(int(row['is_digested'])),
                    },
                )

        with (base_dir / 'waterqualityparameter_technology.csv').open(
            mode='r', encoding='utf-8-sig', newline=''
        ) as file_obj:
            wq_junction = WaterqualityParameterTechnologyJunction.objects
            for row in csv.DictReader(file_obj):
                wq_parameter_id = int(row['waterqualityparameter'])
                technology_id = int(row['technology'])
                if not WaterqualityParameter.objects.filter(
                    id=wq_parameter_id
                ).exists():
                    continue
                if not Technology.objects.filter(id=technology_id).exists():
                    continue
                wq_junction.update_or_create(
                    id=int(row['id']),
                    defaults={
                        'waterqualityparameter_id': wq_parameter_id,
                        'technology_id': technology_id,
                        'is_inputparameter': bool(
                            int(row['is_inputparameter'])
                        ),
                        'is_targetparameter': bool(
                            int(row['is_targetparameter'])
                        ),
                        'default_value': float(row['default_value']),
                    },
                )

    def _build_kwargs_from_defaults(self, technology):
        parameters = {
            row.property.name: row.default_value
            for row in TechnologyPropertyJunction.objects.filter(
                technology=technology
            ).select_related('property')
        }
        input_values = {
            row.waterqualityparameter.name: row.default_value
            for row in WaterqualityParameterTechnologyJunction.objects.filter(
                technology=technology,
                is_inputparameter=True,
                is_targetparameter=False,
            ).select_related('waterqualityparameter')
        }
        target_values = {
            row.waterqualityparameter.name: row.default_value
            for row in WaterqualityParameterTechnologyJunction.objects.filter(
                technology=technology,
                is_inputparameter=False,
                is_targetparameter=True,
            ).select_related('waterqualityparameter')
        }
        wq_parameters = {
            INPUT_WQPARAMETER_KEY: input_values,
            TARGET_WQPARAMETER_KEY: target_values,
        }
        return parameters, wq_parameters

    def _technology_cases(self):
        return [
            {
                'class_': CoagulationDynamicMixing,
                'technology_id': 40,
                'probe_parameter': 'retention time (min)',
                'required_parameters': [
                    'tank height',
                    'tank height chemical storage',
                    'target concentration of dosing chemical',
                    'chemical dosing solution concentration (w/w%)',
                    'mass density of chemical',
                    'retention time (min)',
                    'storage time of chemicals (days)',
                    'mixer velocity gradient',
                    'power efficiency of mixer(s)',
                    'units per lane',
                    'chemical emission factor',
                ],
            },
            {
                'class_': CascadeMixerCoagulationDosing,
                'technology_id': 4,
                'probe_parameter': 'weir coefficient',
                'required_parameters': [
                    'tank height',
                    'weir height',
                    'weir coefficient',
                    'head loss coefficient',
                    'retention time (min)',
                    'number of cascade stages',
                    'tank height chemical storage',
                    'chemical dosing solution concentration (w/w%)',
                    'power for dosing (kW)',
                    'target concentration of dosing chemical',
                    'power efficiency of mixer(s)',
                    'units per lane',
                    'storage time of chemicals (days)',
                    'chemical emission factor',
                ],
            },
            {
                'class_': Strainer,
                'technology_id': 2,
                'probe_parameter': 'bar spacing',
                'required_parameters': [
                    'bar width',
                    'bar spacing',
                    'blockage factor',
                    'velocity bar screen',
                    'head loss coefficient',
                ],
                'digest_parameter_list': ['area'],
            },
            {
                'class_': ChlorineDisinfection,
                'technology_id': 27,
                'probe_parameter': 'units per lane',
                'required_parameters': [
                    'tank height',
                    'tank height chemical storage',
                    'target residual concentration (mg/l)',
                    'target concentration of dosing chemical',
                    'chemical dosing solution concentration (w/w%)',
                    'power',
                    'retention time (min)',
                    'units per lane',
                    'storage time of chemicals (days)',
                    'chemical emission factor',
                ],
                'chem_parameters': ['chlorine'],
            },
            {
                'class_': ChloramineDisinfection,
                'technology_id': 39,
                'probe_parameter': 'retention time (min)',
                'required_parameters': [
                    'tank height',
                    'tank height chemical storage',
                    'target residual concentration (mg/l)',
                    'target concentration of dosing chemical',
                    'chemical dosing solution concentration (w/w%)',
                    'power',
                    'retention time (min)',
                    'units per lane',
                    'storage time of chemicals (days)',
                    'chemical emission factor',
                ],
                'chem_parameters': ['chloramine'],
            },
            {
                'class_': BaffledOzonationContactor,
                'technology_id': 31,
                'probe_parameter': 'energy consumption per kg ozone',
                'required_parameters': [
                    'tank height',
                    'units per lane',
                    'retention time (min)',
                    'target concentration of dosing chemical',
                    'energy consumption per kg ozone',
                    'chemical emission factor',
                ],
                'chem_parameters': ['ozone'],
            },
            {
                'class_': UVdisinfection,
                'technology_id': 32,
                'probe_parameter': 'UV dose',
                'required_parameters': [
                    'units per lane',
                    'UV dose',
                    'UV power intensity',
                    'tank height',
                    'UV power per m3',
                ],
            },
            {
                'class_': CleanWaterStorageTank,
                'technology_id': 43,
                'probe_parameter': 'retention time (hr)',
                'required_parameters': [
                    'tank height',
                    'retention time (hr)',
                    'units per lane',
                ],
            },
            {
                'class_': ChainScrapedSedimentation,
                'technology_id': 7,
                'probe_parameter': 'surface overflow rate',
                'required_parameters': [
                    'retention time (min)',
                    'scraper power coefficient',
                    'units per lane',
                    'surface overflow rate',
                ],
            },
            {
                'class_': RapidSandSingleMediumFiltration,
                'technology_id': 18,
                'probe_parameter': TPN['sand_porosity'],
                'required_parameters': [
                    TPN['units_per_lane'],
                    TPN['filtration_rate'],
                    TPN['sand_porosity'],
                    TPN['sand_density'],
                    TPN['sand_media_grain_size'],
                    TPN['backwash_duration'],
                    TPN['backwash_tank_height'],
                    TPN['backwash_filtration_rate'],
                    TPN['power_efficiency_of_pumps'],
                    TPN['sand_filter_bed_height'],
                ],
                'digest_parameter_list': ['filter area'],
            },
        ]

    def _collect_missing_required_properties(self):
        rows = []
        for case in self._technology_cases():
            technology = Technology.objects.filter(
                id=case['technology_id']
            ).first()
            if technology is None:
                rows.append(
                    {
                        'technology_id': case['technology_id'],
                        'technology_name': None,
                        'technology_class': case['class_'].__name__,
                        'missing_property': '<<missing technology row>>',
                        'source_table': 'technology',
                    }
                )
                continue

            parameters, _ = self._build_kwargs_from_defaults(technology)
            for parameter_name in case['required_parameters']:
                if parameter_name not in parameters:
                    rows.append(
                        {
                            'technology_id': technology.id,
                            'technology_name': technology.name,
                            'technology_class': case['class_'].__name__,
                            'missing_property': parameter_name,
                            'source_table': 'technology_property'
                        }
                    )
        return rows

    def _write_missing_properties_report(self, rows):
        report_dir = Path(__file__).resolve().parent / 'reports'
        report_dir.mkdir(parents=True, exist_ok=True)

        json_path = report_dir / 'missing_required_properties.json'
        csv_path = report_dir / 'missing_required_properties.csv'

        json_path.write_text(
            json.dumps(rows, indent=2),
            encoding='utf-8',
        )

        with csv_path.open(mode='w', encoding='utf-8', newline='') as file_obj:
            writer = csv.DictWriter(
                file_obj,
                fieldnames=[
                    'technology_id',
                    'technology_name',
                    'technology_class',
                    'missing_property',
                    'source_table',
                ],
            )
            writer.writeheader()
            writer.writerows(rows)

        return json_path, csv_path

    def test_kwargs_from_db_defaults_are_queryable_per_technology(self):
        technology_cases = self._technology_cases()

        for case in technology_cases:
            with self.subTest(technology_class=case['class_'].__name__):
                technology = Technology.objects.filter(
                    id=case['technology_id']
                ).first()
                self.assertIsNotNone(
                    technology,
                    f"Technology id {case['technology_id']} does not exist.",
                )
                self.assertTrue(
                    TechnologyPropertyJunction.objects.filter(
                        technology=technology
                    ).exists(),
                    (
                        "No property defaults exist for technology "
                        f"{technology.name}."
                    ),
                )
                self.assertIsNotNone(
                    technology,
                    f"No defaults found for {case['class_'].__name__}.",
                )

                parameters, wq_parameters = self._build_kwargs_from_defaults(
                    technology
                )

                missing_defaults = [
                    parameter_name
                    for parameter_name in case['required_parameters']
                    if parameter_name not in parameters
                ]
                self.assertEqual(
                    missing_defaults,
                    [],
                    (
                        f"Missing required defaults for technology "
                        f"{technology.name}: {missing_defaults}"
                    ),
                )

                instance = case['class_'](
                    parameters=parameters,
                    design_parameters=self.design_parameters,
                    plant_kpis=self.plant_kpis,
                    wq_parameters=wq_parameters,
                    chem_parameters=case.get('chem_parameters'),
                    digest_parameter_list=case.get('digest_parameter_list'),
                )

                probe_name = case['probe_parameter']
                self.assertIn(probe_name, parameters)
                self.assertEqual(
                    instance.parameters[probe_name],
                    parameters[probe_name],
                )
                self.assertEqual(
                    instance.design_parameters['number of lanes'],
                    self.design_parameters['number of lanes'],
                )
                self.assertEqual(
                    instance.plant_kpis['nominal flow rate'],
                    self.plant_kpis['nominal flow rate'],
                )

    def test_export_missing_required_properties_report(self):
        rows = self._collect_missing_required_properties()
        json_path, csv_path = self._write_missing_properties_report(rows)

        self.assertTrue(json_path.exists())
        self.assertTrue(csv_path.exists())
