from __future__ import annotations

import os
import re
import tempfile
import unittest
from pathlib import Path

from dotenv import dotenv_values

import app as app_module
import tools

STATIC_DIR = Path(app_module.__file__).resolve().parent / "static"


def index_html() -> str:
    return app_module.app.test_client().get("/").get_data(as_text=True)


def config_fields(body: dict) -> dict:
    return {field["key"]: field for group in body["groups"] for field in group["fields"]}


class SettingsPageTests(unittest.TestCase):
    def test_every_element_bound_by_javascript_exists(self):
        source = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
        ids = re.findall(r'document\.getElementById\("([^"]+)"\)', source)

        self.assertTrue(ids)
        html = index_html()
        missing = [element_id for element_id in ids if f'id="{element_id}"' not in html]
        self.assertEqual(missing, [])

    def test_settings_dialog_is_present_and_hidden_by_default(self):
        html = index_html()

        self.assertIn('id="settingsBtn"', html)
        self.assertRegex(html, r'id="settingsOverlay"[^>]*\bhidden\b')

    def test_settings_dialog_has_the_form_the_javascript_drives(self):
        html = index_html()

        for element_id in (
            "settingsClose",
            "settingsCancel",
            "settingsForm",
            "settingsScroll",
            "settingsStatus",
            "settingsSave",
        ):
            self.assertIn(f'id="{element_id}"', html)


class ConfigTestCase(unittest.TestCase):
    def setUp(self):
        self.client = app_module.app.test_client()

        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.env_path = Path(self._tmp.name) / ".env"

        self._original_env_path = app_module.ENV_PATH
        app_module.ENV_PATH = self.env_path
        self.addCleanup(self._restore_env_path)

        self._original_environment = {
            key: os.environ.get(key) for key in app_module._config_fields()
        }
        self.addCleanup(self._restore_environment)

        self._original_http_timeout = tools.HTTP_TIMEOUT
        self.addCleanup(self._restore_tools)

    def _restore_env_path(self):
        app_module.ENV_PATH = self._original_env_path

    def _restore_environment(self):
        for key, value in self._original_environment.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def _restore_tools(self):
        tools.HTTP_TIMEOUT = self._original_http_timeout

    def get_config(self) -> dict:
        return self.client.get("/api/config").get_json()

    def save(self, values: dict):
        return self.client.post("/api/config", json={"values": values})

    def saved_env(self) -> dict:
        return dotenv_values(self.env_path)


class GetConfigTests(ConfigTestCase):
    def test_lists_groups_and_field_metadata(self):
        body = self.get_config()

        self.assertTrue(body["editable"])
        self.assertEqual(body["env_path"], str(self.env_path))
        self.assertEqual(
            [group["name"] for group in body["groups"]],
            ["Web search", "Model", "Server"],
        )

        fields = config_fields(body)
        self.assertEqual(fields["BRAVE_API_KEY"]["type"], "secret")
        self.assertEqual(fields["FLASK_DEBUG"]["type"], "bool")
        self.assertEqual(fields["MAX_SOURCES"]["type"], "int")
        self.assertEqual(fields["MAX_SOURCES"]["min"], 1)
        self.assertEqual(fields["MAX_SOURCES"]["max"], 10)

    def test_values_come_from_environment_then_defaults(self):
        os.environ["MAX_SOURCES"] = "7"
        os.environ.pop("HTTP_TIMEOUT", None)

        fields = config_fields(self.get_config())

        self.assertEqual(fields["MAX_SOURCES"]["value"], "7")
        self.assertEqual(fields["HTTP_TIMEOUT"]["value"], "10")

    def test_restart_flags_match_the_configured_groups(self):
        fields = config_fields(self.get_config())

        self.assertTrue(fields["N_CTX"]["restart"])
        self.assertTrue(fields["FLASK_RUN_PORT"]["restart"])
        self.assertFalse(fields["MAX_TOKENS"]["restart"])
        self.assertFalse(fields["MAX_SOURCES"]["restart"])

    def test_env_exists_flag_tracks_the_env_file(self):
        self.assertFalse(self.get_config()["env_exists"])

        self.env_path.write_text("MAX_SOURCES='4'\n", encoding="utf-8")

        self.assertTrue(self.get_config()["env_exists"])


class NormalizeSettingTests(unittest.TestCase):
    def setUp(self):
        self.fields = app_module._config_fields()

    def normalize(self, key: str, raw):
        return app_module._normalize_setting(self.fields[key], raw)

    def test_bool_truthy_variants(self):
        for raw in ("1", "true", "YES", " on "):
            self.assertEqual(self.normalize("FLASK_DEBUG", raw), (None, "1"), raw)

    def test_bool_falsy_variants(self):
        for raw in ("0", "false", "no", "off", ""):
            self.assertEqual(self.normalize("FLASK_DEBUG", raw), (None, "0"), raw)

    def test_bool_invalid(self):
        self.assertEqual(
            self.normalize("FLASK_DEBUG", "maybe"), ("must be a boolean", "maybe")
        )

    def test_int_is_trimmed_and_normalized(self):
        self.assertEqual(self.normalize("MAX_SOURCES", " 5 "), (None, "5"))

    def test_int_not_a_number(self):
        error, _ = self.normalize("MAX_SOURCES", "abc")
        self.assertEqual(error, "must be a whole number")

    def test_int_out_of_range(self):
        for raw in ("0", "99"):
            error, _ = self.normalize("MAX_SOURCES", raw)
            self.assertIn("between 1 and 10", error)

    def test_text_cannot_be_empty_except_the_secret(self):
        self.assertEqual(self.normalize("MODEL_FILE", "   "), ("cannot be empty", ""))
        self.assertEqual(self.normalize("BRAVE_API_KEY", ""), (None, ""))

    def test_text_too_long(self):
        error, _ = self.normalize("MODEL_FILE", "x" * 201)
        self.assertIn("too long", error)


class SaveConfigTests(ConfigTestCase):
    def test_saves_to_env_file_and_updates_environment(self):
        response = self.save({"MAX_SOURCES": "5"})

        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["saved"], ["MAX_SOURCES"])
        self.assertFalse(body["restart_required"])
        self.assertEqual(body["restart_keys"], [])

        self.assertEqual(self.saved_env()["MAX_SOURCES"], "5")
        self.assertEqual(os.environ["MAX_SOURCES"], "5")

    def test_reports_keys_that_need_a_restart(self):
        response = self.save({"N_CTX": "2048", "MAX_SOURCES": "4"})

        body = response.get_json()
        self.assertTrue(body["restart_required"])
        self.assertEqual(body["restart_keys"], ["N_CTX"])

    def test_normalizes_booleans_and_integers_before_writing(self):
        response = self.save({"FLASK_DEBUG": "yes", "MAX_SOURCES": " 6 "})

        self.assertEqual(response.status_code, 200)
        saved = self.saved_env()
        self.assertEqual(saved["FLASK_DEBUG"], "1")
        self.assertEqual(saved["MAX_SOURCES"], "6")

    def test_round_trips_through_get_config(self):
        self.save({"MAX_SOURCES": "8"})

        self.assertEqual(config_fields(self.get_config())["MAX_SOURCES"]["value"], "8")

    def test_applies_http_timeout_immediately(self):
        self.save({"HTTP_TIMEOUT": "22"})

        self.assertEqual(tools.HTTP_TIMEOUT, 22.0)

    def test_unknown_key_is_rejected(self):
        response = self.save({"NOPE": "1"})

        self.assertEqual(response.status_code, 400)
        self.assertIn("Unknown setting", response.get_json()["error"])

    def test_empty_or_missing_values_are_rejected(self):
        for payload in ({}, {"values": {}}, {"values": []}, {"values": "nope"}):
            response = self.client.post("/api/config", json=payload)
            self.assertEqual(response.status_code, 400, payload)

    def test_non_json_body_is_rejected(self):
        response = self.client.post("/api/config", data="not json")

        self.assertEqual(response.status_code, 400)

    def test_invalid_int_is_rejected_with_the_label(self):
        response = self.save({"MAX_SOURCES": "abc"})

        self.assertEqual(response.status_code, 400)
        self.assertIn("Max sources", response.get_json()["error"])

    def test_out_of_range_int_is_rejected(self):
        self.assertEqual(self.save({"MAX_SOURCES": "999"}).status_code, 400)

    def test_invalid_bool_is_rejected_with_the_label(self):
        response = self.save({"FLASK_DEBUG": "perhaps"})

        self.assertEqual(response.status_code, 400)
        self.assertIn("Debug mode", response.get_json()["error"])

    def test_empty_text_rejected_but_empty_secret_allowed(self):
        self.assertEqual(self.save({"MODEL_FILE": ""}).status_code, 400)
        self.assertEqual(self.save({"BRAVE_API_KEY": ""}).status_code, 200)

    def test_validation_error_writes_nothing(self):
        response = self.save({"MAX_SOURCES": "5", "N_CTX": "nope"})

        self.assertEqual(response.status_code, 400)
        self.assertFalse(self.env_path.exists())

    def test_editing_disabled_when_dotenv_is_missing(self):
        original = app_module.set_key
        app_module.set_key = None
        self.addCleanup(setattr, app_module, "set_key", original)

        response = self.save({"MAX_SOURCES": "5"})

        self.assertEqual(response.status_code, 503)


if __name__ == "__main__":
    unittest.main()
