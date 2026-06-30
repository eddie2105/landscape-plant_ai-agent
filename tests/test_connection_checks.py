import os
import unittest
from unittest.mock import Mock, patch


class ConnectionChecksTests(unittest.TestCase):
    def test_load_settings_reads_required_env_values_without_exposing_secrets(self):
        with patch.dict(
            os.environ,
            {
                "GOOGLE_SERVICE_ACCOUNT_FILE": "credentials/service_account.json",
                "PLANTS_SPREADSHEET_ID": "plants-id",
                "PLANTS_WORKSHEET_NAME": "plants",
                "DISPLAY_MATRIX_SPREADSHEET_ID": "display-id",
                "DISPLAY_MATRIX_WORKSHEET_NAME": "display_matrix",
                "OPENAI_API_KEY": "sk-test-secret",
                "OPENAI_MODEL": "gpt-4.1-mini",
            },
            clear=True,
        ):
            from connection_checks import load_settings, public_settings_summary

            settings = load_settings()
            summary = public_settings_summary(settings)

        self.assertEqual("gpt-4.1-mini", settings["OPENAI_MODEL"])
        self.assertEqual("sk-test-secret", settings["OPENAI_API_KEY"])
        self.assertEqual("present", summary["OPENAI_API_KEY"])
        self.assertNotIn("sk-test-secret", str(summary))

    def test_find_missing_settings_reports_empty_required_values(self):
        from connection_checks import find_missing_settings

        missing = find_missing_settings(
            {
                "GOOGLE_SERVICE_ACCOUNT_FILE": "credentials/service_account.json",
                "PLANTS_SPREADSHEET_ID": "",
                "PLANTS_WORKSHEET_NAME": "plants",
                "DISPLAY_MATRIX_SPREADSHEET_ID": None,
                "DISPLAY_MATRIX_WORKSHEET_NAME": "display_matrix",
                "OPENAI_API_KEY": "sk-test",
                "OPENAI_MODEL": "gpt-4.1-mini",
            }
        )

        self.assertEqual(
            ["PLANTS_SPREADSHEET_ID", "DISPLAY_MATRIX_SPREADSHEET_ID"],
            missing,
        )

    def test_check_google_sheets_reads_both_configured_worksheets(self):
        from connection_checks import check_google_sheets

        client = Mock()
        plants_sheet = client.open_by_key.return_value
        plants_worksheet = plants_sheet.worksheet.return_value
        plants_worksheet.get.return_value = [["plant_id"], ["001"]]

        result = check_google_sheets(
            {
                "GOOGLE_SERVICE_ACCOUNT_FILE": "credentials/service_account.json",
                "PLANTS_SPREADSHEET_ID": "plants-id",
                "PLANTS_WORKSHEET_NAME": "plants",
                "DISPLAY_MATRIX_SPREADSHEET_ID": "display-id",
                "DISPLAY_MATRIX_WORKSHEET_NAME": "display_matrix",
            },
            client=client,
        )

        self.assertEqual(
            [
                {"worksheet": "plants", "sample_rows": 2},
                {"worksheet": "display_matrix", "sample_rows": 2},
            ],
            result,
        )
        client.open_by_key.assert_any_call("plants-id")
        client.open_by_key.assert_any_call("display-id")

    def test_check_openai_lists_models_without_returning_secret(self):
        from connection_checks import check_openai

        openai_client = Mock()
        openai_client.models.list.return_value.data = [Mock(id="gpt-4.1-mini")]

        result = check_openai(
            {"OPENAI_API_KEY": "sk-test-secret", "OPENAI_MODEL": "gpt-4.1-mini"},
            client=openai_client,
        )

        self.assertEqual(
            {
                "model": "gpt-4.1-mini",
                "models_returned": 1,
                "first_model": "gpt-4.1-mini",
            },
            result,
        )
        self.assertNotIn("sk-test-secret", str(result))


if __name__ == "__main__":
    unittest.main()
