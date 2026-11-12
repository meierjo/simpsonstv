import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class ServiceTests(unittest.TestCase):
    def test_console_service_blanks_tty1_and_hides_cursor(self):
        service = (REPOSITORY_ROOT / "systemd" / "tvconsole.service").read_text()
        self.assertIn("TTYPath=/dev/tty1", service)
        self.assertIn("--cursor off --clear all", service)
        self.assertIn("Before=tvplayer.service", service)

    def test_player_waits_for_console_blanking(self):
        service = (REPOSITORY_ROOT / "systemd" / "tvplayer.service").read_text()
        self.assertIn("After=local-fs.target tvconsole.service", service)


if __name__ == "__main__":
    unittest.main()
