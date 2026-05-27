import csv
import json
import ast
import inspect
import textwrap
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
    AirFlotationDAF,
    AnionicIEX,
    BaffledOzonationContactor,
    CascadeMixerCoagulationDosing,
    CationIonExchange,
    ChainScrapedSedimentation,
    ChloramineDisinfection,
    ChlorineDisinfection,
    CleanWaterStorageTank,
    CoagulationDynamicMixing,
    CoagulationInlineMixing,
    FlocculationDynamicMixing,
    GranularActivatedCarbonFiltration,
    INPUT_WQPARAMETER_KEY,
    LamellaClarifierHorizontal,
    LamellaClarifierSlope,
    MembraneFiltration,
    MicroStrainer,
    PelletSoftening,
    PowderedActivatedCarbonFiltration,
    RapidSandDoubleMediumFiltration,
    RapidSandPressurizedVesselFiltration,
    RapidSandSingleMediumFiltration,
    SludgeBlanketClarifier,
    Strainer,
    TARGET_WQPARAMETER_KEY,
    UVAOP,
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

    def _resolve_parameter_subscript_key(self, slice_node):
        if isinstance(slice_node, ast.Constant) and isinstance(
            slice_node.value, str
        ):
            return slice_node.value

        if isinstance(slice_node, ast.Subscript):
            if (
                isinstance(slice_node.value, ast.Name)
                and slice_node.value.id == 'TPN'
            ):
                tpn_key = self._resolve_parameter_subscript_key(
                    slice_node.slice
                )
                if isinstance(tpn_key, str) and tpn_key in TPN:
                    return TPN[tpn_key]

        return None

    def _extract_parameter_key_from_subscript(self, subscript_node):
        container = subscript_node.value
        is_parameters_container = (
            isinstance(container, ast.Name) and container.id == 'parameters'
        ) or (
            isinstance(container, ast.Attribute)
            and isinstance(container.value, ast.Name)
            and container.value.id == 'self'
            and container.attr == 'parameters'
        )

        if not is_parameters_container:
            return None

        return self._resolve_parameter_subscript_key(subscript_node.slice)

    def _required_parameters_for_class(self, class_):
        required_parameter_names = set()

        methods_to_scan = ['__init__', '__post_init__']
        for method_name in methods_to_scan:
            method = getattr(class_, method_name, None)
            if method is None:
                continue

            try:
                source_code = inspect.getsource(method)
            except (TypeError, OSError):
                continue

            syntax_tree = ast.parse(textwrap.dedent(source_code))
            for node in ast.walk(syntax_tree):
                if isinstance(node, ast.Subscript):
                    parameter_key = self._extract_parameter_key_from_subscript(
                        node
                    )
                    if isinstance(parameter_key, str):
                        required_parameter_names.add(parameter_key)

        return sorted(required_parameter_names)

    def _technology_cases(self):
        base_cases = [
            {
                'class_': MicroStrainer,
                'technology_id': 3,
                'probe_parameter': 'velocity bar screen',
                'validate_instantiation': False,
            },
            {
                'class_': CoagulationInlineMixing,
                'technology_id': 33,
                'probe_parameter': 'retention time (min)',
                'validate_instantiation': False,
            },
            {
                'class_': FlocculationDynamicMixing,
                'technology_id': 52,
                'probe_parameter': 'retention time (min)',
                'validate_instantiation': False,
            },
            {
                'class_': AnionicIEX,
                'technology_id': 16,
                'probe_parameter': 'units per lane',
                'validate_instantiation': False,
            },
            {
                'class_': MembraneFiltration,
                'technology_id': 26,
                'probe_parameter': 'units per lane',
                'validate_instantiation': False,
            },
            {
                'class_': SludgeBlanketClarifier,
                'technology_id': 45,
                'probe_parameter': 'retention time (min)',
                'validate_instantiation': False,
            },
            {
                'class_': AirFlotationDAF,
                'technology_id': 8,
                'probe_parameter': 'retention time (min)',
                'validate_instantiation': False,
            },
            {
                'class_': LamellaClarifierSlope,
                'technology_id': 6,
                'probe_parameter': 'retention time (min)',
                'validate_instantiation': False,
            },
            {
                'class_': LamellaClarifierHorizontal,
                'technology_id': 5,
                'probe_parameter': 'retention time (min)',
                'validate_instantiation': False,
            },
            {
                'class_': RapidSandDoubleMediumFiltration,
                'technology_id': 19,
                'probe_parameter': 'units per lane',
                'validate_instantiation': False,
            },
            {
                'class_': RapidSandPressurizedVesselFiltration,
                'technology_id': 21,
                'probe_parameter': 'units per lane',
                'validate_instantiation': False,
            },
            {
                'class_': GranularActivatedCarbonFiltration,
                'technology_id': 14,
                'probe_parameter': 'retention time (min)',
                'validate_instantiation': False,
            },
            {
                'class_': PowderedActivatedCarbonFiltration,
                'technology_id': 15,
                'probe_parameter': 'retention time (min)',
                'validate_instantiation': False,
            },
            {
                'class_': UVAOP,
                'technology_id': 38,
                'probe_parameter': 'target concentration of dosing chemical',
                'validate_instantiation': False,
            },
            {
                'class_': PelletSoftening,
                'technology_id': 23,
                'probe_parameter': 'units per lane',
                'validate_instantiation': False,
            },
            {
                'class_': CationIonExchange,
                'technology_id': 17,
                'probe_parameter': 'units per lane',
                'validate_instantiation': False,
            },
            {
                'class_': CoagulationDynamicMixing,
                'technology_id': 40,
                'probe_parameter': 'retention time (min)',
            },
            {
                'class_': CascadeMixerCoagulationDosing,
                'technology_id': 4,
                'probe_parameter': 'weir coefficient',
            },
            {
                'class_': Strainer,
                'technology_id': 2,
                'probe_parameter': 'bar spacing',
                'digest_parameter_list': ['area'],
            },
            {
                'class_': ChlorineDisinfection,
                'technology_id': 27,
                'probe_parameter': 'units per lane',
                'chem_parameters': ['chlorine'],
            },
            {
                'class_': ChloramineDisinfection,
                'technology_id': 39,
                'probe_parameter': 'retention time (min)',
                'chem_parameters': ['chloramine'],
            },
            {
                'class_': BaffledOzonationContactor,
                'technology_id': 31,
                'probe_parameter': 'energy consumption per kg ozone',
                'chem_parameters': ['ozone'],
            },
            {
                'class_': UVdisinfection,
                'technology_id': 32,
                'probe_parameter': 'UV dose',
            },
            {
                'class_': CleanWaterStorageTank,
                'technology_id': 43,
                'probe_parameter': 'retention time (hr)',
            },
            {
                'class_': ChainScrapedSedimentation,
                'technology_id': 7,
                'probe_parameter': 'surface overflow rate',
            },
            {
                'class_': RapidSandSingleMediumFiltration,
                'technology_id': 18,
                'probe_parameter': TPN['sand_porosity'],
                'digest_parameter_list': ['filter area'],
            },
        ]

        generated_cases = []
        for case in base_cases:
            generated_case = dict(case)
            generated_case['required_parameters'] = (
                self._required_parameters_for_class(case['class_'])
            )
            generated_cases.append(generated_case)

        return generated_cases

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

    def _api_calculation_technologies(self):
        return [
            {'class_': MicroStrainer, 'technology_id': 3},
            {'class_': Strainer, 'technology_id': 2},
            {'class_': CoagulationDynamicMixing, 'technology_id': 40},
            {'class_': CoagulationDynamicMixing, 'technology_id': 44},
            {'class_': CoagulationInlineMixing, 'technology_id': 33},
            {'class_': CoagulationInlineMixing, 'technology_id': 50},
            {'class_': CascadeMixerCoagulationDosing, 'technology_id': 4},
            {'class_': CascadeMixerCoagulationDosing, 'technology_id': 51},
            {'class_': FlocculationDynamicMixing, 'technology_id': 52},
            {'class_': AnionicIEX, 'technology_id': 16},
            {'class_': MembraneFiltration, 'technology_id': 26},
            {'class_': MembraneFiltration, 'technology_id': 29},
            {'class_': MembraneFiltration, 'technology_id': 36},
            {'class_': MembraneFiltration, 'technology_id': 37},
            {'class_': SludgeBlanketClarifier, 'technology_id': 45},
            {'class_': ChainScrapedSedimentation, 'technology_id': 7},
            {'class_': AirFlotationDAF, 'technology_id': 8},
            {'class_': LamellaClarifierSlope, 'technology_id': 6},
            {'class_': LamellaClarifierHorizontal, 'technology_id': 5},
            {'class_': RapidSandSingleMediumFiltration, 'technology_id': 18},
            {'class_': RapidSandDoubleMediumFiltration, 'technology_id': 19},
            {
                'class_': RapidSandPressurizedVesselFiltration,
                'technology_id': 21,
            },
            {'class_': GranularActivatedCarbonFiltration, 'technology_id': 14},
            {'class_': PowderedActivatedCarbonFiltration, 'technology_id': 15},
            {'class_': UVAOP, 'technology_id': 38},
            {'class_': BaffledOzonationContactor, 'technology_id': 31},
            {'class_': PelletSoftening, 'technology_id': 23},
            {'class_': CationIonExchange, 'technology_id': 17},
            {'class_': ChlorineDisinfection, 'technology_id': 27},
            {'class_': ChloramineDisinfection, 'technology_id': 39},
            {'class_': UVdisinfection, 'technology_id': 32},
            {'class_': CleanWaterStorageTank, 'technology_id': 43},
        ]

    def _collect_missing_default_values_for_api_calculation(self):
        prop_rows = []
        wq_rows = []

        for case in self._api_calculation_technologies():
            technology = Technology.objects.filter(
                id=case['technology_id']
            ).first()
            class_name = case['class_'].__name__

            if technology is None:
                prop_rows.append(
                    {
                        'technology_id': case['technology_id'],
                        'technology_name': None,
                        'technology_class': class_name,
                        'missing_property': '<<missing technology row>>',
                        'source_table': 'technology',
                    }
                )
                wq_rows.append(
                    {
                        'technology_id': case['technology_id'],
                        'technology_name': None,
                        'technology_class': class_name,
                        'missing_wq_parameter': '<<missing technology row>>',
                        'source_table': 'technology',
                    }
                )
                continue

            techprop_qs = TechnologyPropertyJunction.objects.filter(
                technology=technology
            )
            if not techprop_qs.exists():
                prop_rows.append(
                    {
                        'technology_id': technology.id,
                        'technology_name': technology.name,
                        'technology_class': class_name,
                        'missing_property': '<<no technology_property rows>>',
                        'source_table': 'technology_property',
                    }
                )
            else:
                for prop_row in techprop_qs.select_related('property'):
                    if prop_row.default_value is None:
                        prop_rows.append(
                            {
                                'technology_id': technology.id,
                                'technology_name': technology.name,
                                'technology_class': class_name,
                                'missing_property': prop_row.property.name,
                                'source_table': 'technology_property',
                            }
                        )

            wq_qs = WaterqualityParameterTechnologyJunction.objects.filter(
                technology=technology
            )
            if not wq_qs.exists():
                wq_rows.append(
                    {
                        'technology_id': technology.id,
                        'technology_name': technology.name,
                        'technology_class': class_name,
                        'missing_wq_parameter': (
                            '<<no waterqualityparameter_technology rows>>'
                        ),
                        'source_table': 'waterqualityparameter_technology',
                    }
                )
            else:
                for wq_row in wq_qs.select_related('waterqualityparameter'):
                    if wq_row.default_value is None:
                        wq_rows.append(
                            {
                                'technology_id': technology.id,
                                'technology_name': technology.name,
                                'technology_class': class_name,
                                'missing_wq_parameter': (
                                    wq_row.waterqualityparameter.name
                                ),
                                'source_table': (
                                    'waterqualityparameter_technology'
                                ),
                            }
                        )
        return prop_rows, wq_rows

    def _write_missing_wq_report(self, rows):
        report_dir = Path(__file__).resolve().parent / 'reports'
        report_dir.mkdir(parents=True, exist_ok=True)

        json_path = report_dir / 'missing_wq_defaults.json'
        csv_path = report_dir / 'missing_wq_defaults.csv'

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
                    'missing_wq_parameter',
                    'source_table',
                ],
            )
            writer.writeheader()
            writer.writerows(rows)

        return json_path, csv_path

    def _write_missing_autogenerated_required_report(self, rows):
        report_dir = Path(__file__).resolve().parent / 'reports'
        report_dir.mkdir(parents=True, exist_ok=True)

        sorted_rows = sorted(
            rows,
            key=lambda row: (
                row['technology_id'],
                row['technology_class'],
                row['missing_property'],
            ),
        )

        json_path = report_dir / 'missing_autogenerated_required.json'
        csv_path = report_dir / 'missing_autogenerated_required.csv'

        json_path.write_text(
            json.dumps(sorted_rows, indent=2),
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
            writer.writerows(sorted_rows)

        return json_path, csv_path

    def test_kwargs_from_db_defaults_are_queryable_per_technology(self):
        technology_cases = self._technology_cases()
        missing_required_rows = []

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

                if missing_defaults:
                    for parameter_name in sorted(missing_defaults):
                        missing_required_rows.append(
                            {
                                'technology_id': technology.id,
                                'technology_name': technology.name,
                                'technology_class': case['class_'].__name__,
                                'missing_property': parameter_name,
                                'source_table': 'technology_property',
                            }
                        )

                self.assertEqual(
                    missing_defaults,
                    [],
                    (
                        f"Missing required defaults for technology "
                        f"{technology.name}: {missing_defaults}"
                    ),
                )

                probe_name = case['probe_parameter']
                if probe_name in case['required_parameters']:
                    self.assertIn(probe_name, parameters)

                if case.get('validate_instantiation', True):
                    instance = case['class_'](
                        parameters=parameters,
                        design_parameters=self.design_parameters,
                        plant_kpis=self.plant_kpis,
                        wq_parameters=wq_parameters,
                        chem_parameters=case.get('chem_parameters'),
                        digest_parameter_list=case.get(
                            'digest_parameter_list'
                        ),
                    )

                    if probe_name in parameters:
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

        if missing_required_rows:
            json_path, csv_path = (
                self._write_missing_autogenerated_required_report(
                    missing_required_rows
                )
            )
            self.fail(
                (
                    'Missing auto-generated required defaults were found. '
                    f'Review {json_path} and {csv_path} for cleanup tracking.'
                )
            )

    def test_export_missing_required_properties_report(self):
        rows = self._collect_missing_required_properties()
        json_path, csv_path = self._write_missing_properties_report(rows)

        self.assertTrue(json_path.exists())
        self.assertTrue(csv_path.exists())

    def test_export_api_calculation_default_reports(self):
        prop_rows, wq_rows = (
            self._collect_missing_default_values_for_api_calculation()
        )
        prop_json, prop_csv = self._write_missing_properties_report(prop_rows)
        wq_json, wq_csv = self._write_missing_wq_report(wq_rows)

        self.assertTrue(prop_json.exists())
        self.assertTrue(prop_csv.exists())
        self.assertTrue(wq_json.exists())
        self.assertTrue(wq_csv.exists())
