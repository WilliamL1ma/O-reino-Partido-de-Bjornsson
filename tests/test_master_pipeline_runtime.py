import sys
import unittest
from pathlib import Path
from unittest.mock import patch


BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from master_pipeline.runtime import LLMStageInvoker


class LLMStageInvokerTests(unittest.TestCase):
    def test_invoke_uses_fast_profile_for_mechanics(self) -> None:
        with (
            patch("master_pipeline.runtime.load_groq_settings", return_value=object()) as load_settings,
            patch("master_pipeline.runtime.call_groq_messages", return_value="{}") as call_messages,
        ):
            response = LLMStageInvoker().invoke(
                [{"role": "user", "content": "teste"}],
                temperature=0.15,
                stage="mechanics",
            )

        self.assertEqual(response, "{}")
        load_settings.assert_called_once_with(stage="fast")
        self.assertIs(call_messages.call_args.kwargs["settings"], load_settings.return_value)

    def test_invoke_uses_narrative_profile_for_narrative_stage(self) -> None:
        with (
            patch("master_pipeline.runtime.load_groq_settings", return_value=object()) as load_settings,
            patch("master_pipeline.runtime.call_groq_messages", return_value="{}") as call_messages,
        ):
            response = LLMStageInvoker().invoke(
                [{"role": "user", "content": "teste"}],
                temperature=0.7,
                stage="narrative",
            )

        self.assertEqual(response, "{}")
        load_settings.assert_called_once_with(stage="narrative")
        self.assertIs(call_messages.call_args.kwargs["settings"], load_settings.return_value)


if __name__ == "__main__":
    unittest.main()
