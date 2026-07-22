# -*- coding: utf-8 -*-
import unittest
from unittest.mock import MagicMock, patch

from config import email as email_config
from core import email_provider, outlook_tw_client


class OutlookTwClientTests(unittest.TestCase):
    def setUp(self):
        outlook_tw_client._CONTEXT_CACHE.clear()

    @patch("core.outlook_tw_client._request")
    def test_pick_account_uses_faker_local_and_create(self, request_mock):
        request_mock.return_value = {
            "email": "nicholas1797@outlook.tw",
            "expires": 1784699659656,
            "anonymous": True,
        }

        with patch.object(outlook_tw_client, "generate_local_part", return_value="nicholas1797"), \
             patch.object(outlook_tw_client._email_cfg, "OUTLOOK_TW_API_BASE", "https://outlook.tw", create=True), \
             patch.object(outlook_tw_client._email_cfg, "OUTLOOK_TW_DOMAIN_INDEX", 0, create=True):
            account = outlook_tw_client.pick_account()

        self.assertEqual(account.email, "nicholas1797@outlook.tw")
        self.assertEqual(account.local, "nicholas1797")
        self.assertEqual(
            outlook_tw_client.get_account_context("nicholas1797@outlook.tw").email,
            "nicholas1797@outlook.tw",
        )
        request_mock.assert_called_once_with(
            "POST",
            "/api/create",
            json={"local": "nicholas1797", "domainIndex": 0},
        )

    def test_generate_local_part_is_name_plus_4_digits(self):
        with patch.object(outlook_tw_client._FAKER, "first_name", return_value="Mary-Jane"):
            local = outlook_tw_client.generate_local_part()
        self.assertRegex(local, r"^maryjane\d{4}$")

    @patch("core.outlook_tw_client.time.sleep")
    @patch("core.outlook_tw_client._get")
    def test_fetch_latest_otp_from_list_and_detail(self, get_mock, sleep_mock):
        get_mock.side_effect = [
            [
                {
                    "id": 10001,
                    "sender": "noreply@openai.com",
                    "subject": "Your ChatGPT code",
                    "received_at": "2099-01-01 12:00:00",
                    "content": "preview",
                }
            ],
            {
                "id": 10001,
                "sender": "noreply@openai.com",
                "subject": "Your ChatGPT code",
                "received_at": "2099-01-01 12:00:00",
                "content": "Your verification code is 654321",
                "html_content": "<p>654321</p>",
            },
        ]

        with patch.object(outlook_tw_client._email_cfg, "OUTLOOK_TW_API_BASE", "https://outlook.tw", create=True), \
             patch.object(outlook_tw_client._email_cfg, "OTP_MAX_WAIT", 10, create=True), \
             patch.object(outlook_tw_client._email_cfg, "OTP_POLL_INTERVAL", 1, create=True), \
             patch.object(outlook_tw_client._email_cfg, "OTP_SETTLE_SECONDS", 0, create=True):
            code = outlook_tw_client.fetch_latest_otp("abc12345@outlook.tw", after_ts=0)

        self.assertEqual(code, "654321")
        sleep_mock.assert_not_called()


class EmailProviderOutlookTwTests(unittest.TestCase):
    def test_parse_sources_keeps_outlook_tw(self):
        self.assertEqual(
            email_provider.parse_email_sources("outlook,outlook_tw,gptmail"),
            ["outlook", "outlook_tw", "gptmail"],
        )

    @patch("core.outlook_tw_client.pick_account")
    def test_acquire_email_uses_outlook_tw(self, pick_account):
        pick_account.return_value.email = "fresh@outlook.tw"
        with patch("core.email_provider.parse_email_sources", return_value=["outlook_tw"]):
            self.assertEqual(email_provider.acquire_email(), "fresh@outlook.tw")

    @patch("core.outlook_tw_client.get_account_context", return_value=object())
    def test_resolve_email_source(self, get_context):
        self.assertEqual(email_provider.resolve_email_source("fresh@outlook.tw"), "outlook_tw")
        get_context.assert_called_once_with("fresh@outlook.tw")

    @patch("core.outlook_tw_client.fetch_latest_otp", return_value="112233")
    @patch("core.email_provider.resolve_email_source", return_value="outlook_tw")
    def test_wait_for_otp(self, resolve, fetch_latest_otp):
        with patch.object(email_config, "USE_EMAIL_SERVICE", True):
            self.assertEqual(email_provider.wait_for_otp("fresh@outlook.tw", after_ts=1.0), "112233")
        fetch_latest_otp.assert_called_once_with("fresh@outlook.tw", after_ts=1.0)


if __name__ == "__main__":
    unittest.main()
