import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from narrative import llm_gateway


class LlmGatewayTests(unittest.TestCase):
    def test_load_groq_settings_reads_environment(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "GROQ_API_KEY": "test-key",
                "GROQ_MODEL_NARRATIVE": "qwen-test",
                "GROQ_TIMEOUT_SECONDS_NARRATIVE": "41",
            },
            clear=True,
        ):
            settings = llm_gateway.load_groq_settings()

        self.assertEqual(settings.api_key, "test-key")
        self.assertEqual(settings.model, "qwen-test")
        self.assertEqual(settings.timeout, 41.0)

    def test_load_groq_settings_uses_fast_stage_defaults(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "GROQ_API_KEY": "test-key",
                "GROQ_MODEL": "qwen-global",
                "GROQ_TIMEOUT_SECONDS": "22",
            },
            clear=True,
        ):
            settings = llm_gateway.load_groq_settings(stage="fast")

        self.assertEqual(settings.api_key, "test-key")
        self.assertEqual(settings.model, llm_gateway.DEFAULT_GROQ_FAST_MODEL)
        self.assertEqual(settings.timeout, 22.0)

    def test_load_groq_settings_reads_stage_specific_overrides(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "GROQ_API_KEY": "test-key",
                "GROQ_MODEL_NARRATIVE": "qwen-narrative",
                "GROQ_MODEL_FAST": "llama-fast",
                "GROQ_TIMEOUT_SECONDS_NARRATIVE": "25",
                "GROQ_TIMEOUT_SECONDS_FAST": "9",
                "GROQ_MAX_TOKENS_NARRATIVE": "700",
                "GROQ_MAX_TOKENS_FAST": "150",
            },
            clear=True,
        ):
            default_settings = llm_gateway.load_groq_settings()
            narrative_settings = llm_gateway.load_groq_settings(stage="narrative")
            fast_settings = llm_gateway.load_groq_settings(stage="fast")

        self.assertEqual(default_settings.model, "qwen-narrative")
        self.assertEqual(default_settings.timeout, 25.0)
        self.assertEqual(default_settings.max_tokens, 700)
        self.assertEqual(narrative_settings.model, "qwen-narrative")
        self.assertEqual(narrative_settings.timeout, 25.0)
        self.assertEqual(narrative_settings.max_tokens, 700)
        self.assertEqual(fast_settings.model, "llama-fast")
        self.assertEqual(fast_settings.timeout, 9.0)
        self.assertEqual(fast_settings.max_tokens, 150)

    def test_call_groq_messages_uses_gateway_settings_and_json_mode(self) -> None:
        captured_kwargs: dict = {}

        def _create(**kwargs):
            captured_kwargs.update(kwargs)
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="  resposta  "))])

        client = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(
                    create=_create
                )
            )
        )

        settings = llm_gateway.GroqSettings(api_key="key", model="model-x", timeout=19.0)
        response = llm_gateway.call_groq_messages(
            [{"role": "user", "content": "teste"}],
            temperature=0.2,
            json_mode=True,
            settings=settings,
            client=client,
        )

        self.assertEqual(response, "resposta")
        self.assertEqual(captured_kwargs["model"], "model-x")
        self.assertEqual(captured_kwargs["response_format"], {"type": "json_object"})

    def test_call_groq_messages_wraps_provider_errors(self) -> None:
        class APIConnectionError(Exception):
            pass

        client = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(
                    create=lambda **_kwargs: (_ for _ in ()).throw(APIConnectionError("offline"))
                )
            )
        )

        with self.assertRaises(llm_gateway.LLMGatewayError) as captured:
            llm_gateway.call_groq_messages(
                [{"role": "user", "content": "teste"}],
                settings=llm_gateway.GroqSettings(api_key="key", model="model-x", timeout=19.0),
                client=client,
            )

        self.assertIn("Falha ao conectar na Groq", str(captured.exception))


if __name__ == "__main__":
    unittest.main()
