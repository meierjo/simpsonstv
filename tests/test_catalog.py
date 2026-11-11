import json
import tempfile
import unittest
from pathlib import Path

from tv.catalog import (
    expected_episode_ids,
    format_report,
    normalize_episode_id,
    parse_episode,
    scan_library,
)


class CatalogTests(unittest.TestCase):
    def test_normalizes_single_digit_episode_number(self):
        episode = parse_episode(Path("S03E1 Stark Raving Dad.mp4"))

        self.assertEqual(episode.episode_id, "S03E01")
        self.assertEqual(episode.title, "Stark Raving Dad")

    def test_parses_long_title_and_prefix(self):
        path = Path(
            "The Simpsons S05E10 Springfield (Or, How I Learned to Stop "
            "Worrying and Love Legalized Gambling).mp4"
        )

        episode = parse_episode(path)

        self.assertEqual(episode.episode_id, "S05E10")
        self.assertTrue(episode.title.startswith("Springfield"))

    def test_expected_catalog_contains_226_episodes(self):
        episode_ids = expected_episode_ids()

        self.assertEqual(len(episode_ids), 226)
        self.assertEqual(episode_ids[0], "S01E01")
        self.assertEqual(episode_ids[-1], "S10E23")

    def test_scan_reports_missing_duplicates_unexpected_and_unrecognized(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "S01E01 Simpsons Roasting on an Open Fire.mp4").touch()
            (root / "copy S01E01 duplicate.mkv").touch()
            (root / "S11E01 Future Episode.mp4").touch()
            (root / "commercial.mp4").touch()
            (root / "notes.txt").touch()

            report = scan_library(root)

        self.assertEqual(report.duplicate_ids, ("S01E01",))
        self.assertEqual(report.unexpected_ids, ("S11E01",))
        self.assertEqual(report.unique_episode_count, 1)
        self.assertIn("S01E02", report.missing_ids)
        self.assertEqual(len(report.unrecognized_paths), 1)
        self.assertIn("Status: NEEDS ATTENTION", format_report(report))

    def test_complete_synthetic_library_passes(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            for episode_id in expected_episode_ids():
                (root / (episode_id + " Test Episode.mp4")).touch()

            report = scan_library(root)

        self.assertTrue(report.is_complete)
        self.assertEqual(report.unique_episode_count, 226)
        self.assertEqual(report.missing_ids, ())
        self.assertIn("Status: COMPLETE", format_report(report))

    def test_normalize_episode_id(self):
        self.assertEqual(normalize_episode_id(4, 5), "S04E05")

    def test_starter_metadata_contains_all_treehouse_episodes(self):
        metadata_path = Path(__file__).resolve().parents[1] / "config" / "episodes.json"
        with metadata_path.open() as metadata_file:
            episodes = json.load(metadata_file)["episodes"]

        expected_ids = {
            "S02E03",
            "S03E07",
            "S04E05",
            "S05E05",
            "S06E06",
            "S07E06",
            "S08E01",
            "S09E04",
            "S10E04",
        }
        treehouse_ids = {
            episode_id
            for episode_id, metadata in episodes.items()
            if "treehouse-of-horror" in metadata["tags"]
        }
        self.assertEqual(treehouse_ids, expected_ids)


if __name__ == "__main__":
    unittest.main()

