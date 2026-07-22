# -*- coding: utf-8 -*-
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from webui.config_editor import EDITABLE_FIELDS


class OutlookTwConfigTests(unittest.TestCase):
    def test_email_config_declares_outlook_tw_defaults(self):
        source = Path("config/email.py").read_text(encoding="utf-8")
        self.assertIn('"outlook_tw"', source)
        self.assertIn('OUTLOOK_TW_API_BASE = "https://outlook.tw"', source)
        self.assertIn("OUTLOOK_TW_NAME_LENGTH = 8", source)
        self.assertIn("OUTLOOK_TW_DOMAIN_INDEX = 0", source)

    def test_webui_exposes_outlook_tw_fields(self):
        keys = {item["key"] for item in EDITABLE_FIELDS}
        self.assertIn("OUTLOOK_TW_API_BASE", keys)
        self.assertIn("OUTLOOK_TW_NAME_LENGTH", keys)
        self.assertIn("OUTLOOK_TW_DOMAIN_INDEX", keys)
        field = next(item for item in EDITABLE_FIELDS if item["key"] == "EMAIL_SOURCE")
        self.assertIn("outlook_tw", field["help"])
        self.assertIn("yahoos", field["help"])


class CodexAgentIdentityConfigTests(unittest.TestCase):
    def test_codex_config_declares_agent_identity_flag(self):
        source = Path("config/codex.py").read_text(encoding="utf-8")
        self.assertIn("ENABLE_CODEX_AGENT_IDENTITY: bool = False", source)

    def test_webui_exposes_agent_identity_toggle(self):
        field = next(item for item in EDITABLE_FIELDS if item["key"] == "ENABLE_CODEX_AGENT_IDENTITY")
        self.assertEqual(field["file"], "codex.py")
        self.assertEqual(field["type"], "bool")


class SaveAccountCodexAgentTests(unittest.TestCase):
    @patch("core.plan_check_service.enqueue_account_plan_check", return_value={"accepted": True})
    @patch("core.db.insert_account", return_value=42)
    def test_save_account_generates_agent_identity_when_enabled(self, insert_account, enqueue):
        from core import account_export

        fake_agent = MagicMock()
        with TemporaryDirectory() as tmp:
            batch_dir = Path(tmp) / "batch"
            batch_dir.mkdir()

            with patch.dict("sys.modules", {"codex_agent": fake_agent}), \
                 patch("core.account_export._append_batch_archive", return_value=batch_dir), \
                 patch("config.codex.ENABLE_CODEX_AGENT_IDENTITY", True), \
                 patch("config.codex.CODEX_OUTPUT_DIRNAME", "codex_accounts"), \
                 patch.object(account_export, "_PROJECT_ROOT", Path(tmp)):
                row_id = account_export.save_account_data(
                    email="user@outlook.tw",
                    access_token="eyJhbGci.fake.token",
                    email_source="outlook_tw",
                    batch_dir=batch_dir,
                )

            self.assertEqual(row_id, 42)
            fake_agent.create_codex_agent_identity.assert_called_once()
            kwargs = fake_agent.create_codex_agent_identity.call_args.kwargs
            self.assertEqual(kwargs["access_token"], "eyJhbGci.fake.token")
            self.assertTrue(str(kwargs["output_path"]).endswith("codex-agent-user@outlook.tw.json"))


if __name__ == "__main__":
    unittest.main()
