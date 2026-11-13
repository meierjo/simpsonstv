import tempfile
import unittest
from pathlib import Path

from tv.wifi import (
    derive_psk,
    import_wifi_request,
    parse_wifi_request,
    render_wpa_supplicant,
)


class WifiImportTests(unittest.TestCase):
    def test_request_preserves_spaces_and_equals_in_values(self):
        request = parse_wifi_request(
            "country=us\nssid=Brother's WiFi\npassword=correct=horse battery\n"
        )

        self.assertEqual(request.country, "US")
        self.assertEqual(request.ssid, "Brother's WiFi")
        self.assertEqual(request.password, "correct=horse battery")

    def test_unknown_duplicate_missing_and_short_values_are_rejected(self):
        invalid_requests = (
            "country=US\nssid=Network\npassword=long enough\nexecute=yes\n",
            "country=US\nssid=One\nssid=Two\npassword=long enough\n",
            "country=US\nssid=Network\n",
            "country=USA\nssid=Network\npassword=long enough\n",
            "country=US\nssid=Network\npassword=short\n",
        )
        for text in invalid_requests:
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_wifi_request(text)

    def test_psk_matches_wpa_reference_vector(self):
        self.assertEqual(
            derive_psk("IEEE", "password"),
            "f42c6fc52df0ebef9ebb4b90b38a5f90"
            "2e83fe1b135a70e23aed762e9710a12e",
        )

    def test_render_escapes_ssid_and_never_contains_password(self):
        request = parse_wifi_request(
            'country=US\nssid=The "Best" \\\\ WiFi\npassword=do not retain me\n'
        )

        rendered = render_wpa_supplicant(request)

        self.assertIn('ssid="The \\"Best\\" \\\\\\\\ WiFi"', rendered)
        self.assertNotIn("do not retain me", rendered)
        self.assertRegex(rendered, r"psk=[0-9a-f]{64}")

    def test_success_backs_up_once_replaces_config_and_removes_request(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            request_path = root / "boot" / "simpsonstv-wifi.txt"
            config_path = root / "etc" / "wpa_supplicant.conf"
            backup_path = root / "etc" / "recovery.conf"
            result_path = root / "boot" / "simpsonstv-wifi-result.txt"
            request_path.parent.mkdir()
            config_path.parent.mkdir()
            request_path.write_text(
                "country=US\nssid=New Network\npassword=new password\n"
            )
            config_path.write_text("original config\n")

            import_wifi_request(
                request_path, config_path, backup_path, result_path
            )

            self.assertFalse(request_path.exists())
            self.assertEqual(backup_path.read_text(), "original config\n")
            self.assertIn('ssid="New Network"', config_path.read_text())
            self.assertNotIn("new password", config_path.read_text())
            self.assertIn("status=success", result_path.read_text())
            self.assertNotIn("new password", result_path.read_text())

            request_path.write_text(
                "country=US\nssid=Second Network\npassword=second password\n"
            )
            import_wifi_request(
                request_path, config_path, backup_path, result_path
            )
            self.assertEqual(backup_path.read_text(), "original config\n")


if __name__ == "__main__":
    unittest.main()
