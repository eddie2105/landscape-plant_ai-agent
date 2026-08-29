import unittest
from unittest.mock import Mock, patch

from 景觀植物AI系統.資料.matrix_loader import load_google_sheet


class MatrixLoaderTests(unittest.TestCase):
    def test_json_service_account_is_used_without_reading_a_local_key_file(self):
        client = Mock()
        worksheet = client.open_by_key.return_value.worksheet.return_value
        worksheet.get_all_records.return_value = [{"plant_id": 17, "chinese_name": "測試植物"}]
        credential_json = '{"type": "service_account", "project_id": "demo"}'

        with patch(
            "景觀植物AI系統.資料.matrix_loader.gspread.service_account_from_dict",
            return_value=client,
        ) as from_dict, patch(
            "景觀植物AI系統.資料.matrix_loader.gspread.service_account"
        ) as from_file:
            result = load_google_sheet(
                "sheet-id",
                "display_matrix_merged",
                "credentials/service_account.json",
                credential_json,
            )

        from_dict.assert_called_once_with({"type": "service_account", "project_id": "demo"})
        from_file.assert_not_called()
        client.open_by_key.assert_called_once_with("sheet-id")
        self.assertEqual("17", result.loc[0, "plant_id"])


if __name__ == "__main__":
    unittest.main()
