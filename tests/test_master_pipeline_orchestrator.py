import builtins
import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


class MasterPipelineOrchestratorTests(unittest.TestCase):
    def test_custom_runner_path_does_not_import_master_graph(self) -> None:
        module_path = BACKEND_DIR / "master_pipeline" / "orchestrator.py"
        spec = importlib.util.spec_from_file_location("test_master_pipeline_orchestrator", module_path)
        module = importlib.util.module_from_spec(spec)
        assert spec and spec.loader

        original_import = builtins.__import__

        def _guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "master_graph":
                raise AssertionError("custom orchestrator runner should not import master_graph")
            return original_import(name, globals, locals, fromlist, level)

        with patch("builtins.__import__", new=_guarded_import):
            spec.loader.exec_module(module)
            orchestrator = module.MasterOrchestrator(graph_runner=lambda state: {"ok": True, **state})

        self.assertEqual(orchestrator.invoke({"scene": "encounter_goblin"}), {"ok": True, "scene": "encounter_goblin"})


if __name__ == "__main__":
    unittest.main()
