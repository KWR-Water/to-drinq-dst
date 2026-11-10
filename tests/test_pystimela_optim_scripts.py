import contextlib
import importlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock


EXPECTED_OPTIM_SCRIPTS = {
    "chlorination_optim",
    "coag_floc_optim",
    "dual_filtration_optim",
    "filtration_optim",
    "gac_optim",
    "ozonation_optim",
}


_MODULE_CACHE: dict[str, object] = {}

OPTIMIZER_MODULE_BASE = "pystimela_optim.scripts"


def _load_script_module(script_name: str) -> object:
    module_name = f"{OPTIMIZER_MODULE_BASE}.{script_name}"
    if module_name not in _MODULE_CACHE:
        _MODULE_CACHE[module_name] = importlib.import_module(module_name)
    return _MODULE_CACHE[module_name]


def _runner_function_name(module: object) -> str:
    if hasattr(module, "_run_python_module"):
        return "_run_python_module"
    return "_run_python_script"


@contextlib.contextmanager
def _working_directory(path: Path):
    old_cwd = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(old_cwd)


class OptimScriptSmokeTests(unittest.TestCase):
    def test_optimizer_namespace_is_available(self):
        self.assertIsNotNone(importlib.util.find_spec(OPTIMIZER_MODULE_BASE))

    def test_optimizer_scripts_are_importable(self):
        for script_name in EXPECTED_OPTIM_SCRIPTS:
            with self.subTest(script=script_name):
                module = _load_script_module(script_name)
                self.assertIsNotNone(module)

    def test_each_optim_module_has_core_functions(self):
        for script_name in EXPECTED_OPTIM_SCRIPTS:
            with self.subTest(script=script_name):
                module = _load_script_module(script_name)

                self.assertTrue(hasattr(module, "main"))
                self.assertTrue(callable(module.main))
                self.assertTrue(hasattr(module, "capital_recovery_factor"))

                r_real = 0.05
                years = 10
                expected = (
                    r_real * (1 + r_real) ** years
                ) / ((1 + r_real) ** years - 1)
                self.assertAlmostEqual(
                    module.capital_recovery_factor(r_real, years), expected
                )

    def test_quality_inputs_from_json_supported_for_all_optim_scripts(self):
        payload = {
            "timestamps": [0.0, 60.0, 120.0],
            "wq_parameters": {
                "flow": {"value": 100.0},
                "temperature": {"value": 12.0},
                "conductivity": {"value": 250.0},
                "suspended_solids": {"value": 8.0},
                "uv254": {"value": 0.12},
                "ph": {"value": 7.1},
                "pH": {"value": 7.1},
                "doc": {"value": 3.2},
                "DOC": {"value": 3.2},
                "mnumber": {"value": 0.01},
                "ammonia": {"value": 0.05},
                "bromide": {"value": 0.02},
            },
        }

        for script_name in EXPECTED_OPTIM_SCRIPTS:
            with self.subTest(script=script_name):
                module = _load_script_module(script_name)
                quality_inputs = module.QualityInputs.from_json(payload)

                self.assertEqual(len(quality_inputs.timestamps), 3)
                self.assertEqual(quality_inputs.timestamps[0], 0.0)
                self.assertEqual(quality_inputs.timestamps[-1], 120.0)


class RunAllOptimizationsTests(unittest.TestCase):
    def test_main_raises_when_enabled_process_file_missing(self):
        module = _load_script_module("run_all_optimizations")

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            with _working_directory(tmp_path):
                with self.assertRaises(FileNotFoundError):
                    module.main([])

    def test_main_runs_single_enabled_process_end_to_end(self):
        module = _load_script_module("run_all_optimizations")
        run_function_name = _runner_function_name(module)

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            (tmp_path / "outputs").mkdir()
            (tmp_path / "inputs").mkdir()
            (tmp_path / "configs").mkdir()

            (tmp_path / "outputs" / "enabled_processes.json").write_text(
                json.dumps({"enabled": ["chlorination"]}),
                encoding="utf-8",
            )
            (tmp_path / "inputs" / "config_chlorination.csv").write_text(
                "name,value\nexample,1\n",
                encoding="utf-8",
            )
            (tmp_path / "configs" / "in_wq_params.json").write_text(
                json.dumps({"seed": "initial"}),
                encoding="utf-8",
            )

            def fake_run(script_path: str, *args: str) -> None:
                args_list = list(args)
                if "--out_json" in args_list:
                    out_json = Path(
                        args_list[
                            args_list.index("--out_json") + 1
                        ]
                    )
                    out_json.parent.mkdir(parents=True, exist_ok=True)
                    out_json.write_text(
                        json.dumps({"script": script_path}),
                        encoding="utf-8",
                    )

            with _working_directory(tmp_path):
                with mock.patch.object(
                    module,
                    run_function_name,
                    side_effect=fake_run,
                ) as run_mock:
                    module.main([])

            self.assertEqual(run_mock.call_count, 3)
            process_output_dirs = [
                path
                for path in (tmp_path / "outputs").iterdir()
                if path.is_dir()
            ]
            self.assertEqual(len(process_output_dirs), 1)

            run_dir = process_output_dirs[0]
            self.assertTrue((run_dir / "chlorination_results.json").exists())
            self.assertTrue((run_dir / "final_wq_params.json").exists())

    def test_main_skips_unknown_process_without_crashing(self):
        module = _load_script_module("run_all_optimizations")
        run_function_name = _runner_function_name(module)

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            (tmp_path / "outputs").mkdir()
            (tmp_path / "configs").mkdir()

            (tmp_path / "outputs" / "enabled_processes.json").write_text(
                json.dumps({"enabled": ["not-a-real-process"]}),
                encoding="utf-8",
            )
            (tmp_path / "configs" / "in_wq_params.json").write_text(
                json.dumps({"seed": "initial"}),
                encoding="utf-8",
            )

            with _working_directory(tmp_path):
                with mock.patch.object(
                    module,
                    run_function_name,
                ) as run_mock:
                    module.main([])

            run_mock.assert_not_called()
            process_output_dirs = [
                path
                for path in (tmp_path / "outputs").iterdir()
                if path.is_dir()
            ]
            self.assertEqual(len(process_output_dirs), 1)
            self.assertTrue(
                (process_output_dirs[0] / "final_wq_params.json").exists()
            )


if __name__ == "__main__":
    unittest.main()
