import tempfile
import unittest
from pathlib import Path

from tools.rename_episodes import apply_rename_plan, build_rename_plan
from tv.naming import canonical_episode_filename


class NamingTests(unittest.TestCase):
    def test_canonical_name_normalizes_id_and_preserves_punctuation(self):
        path = Path(
            "The Simpsons S05E10 Springfield (Or, How I Learned to Stop "
            "Worrying and Love Legalized Gambling).mp4"
        )

        filename = canonical_episode_filename(path)

        self.assertEqual(
            filename,
            "S05E10 - Springfield (Or, How I Learned to Stop Worrying and "
            "Love Legalized Gambling).mp4",
        )

    def test_metadata_title_takes_precedence(self):
        filename = canonical_episode_filename(
            Path("S03E7 old title.mkv"),
            {"S03E07": {"title": "Treehouse of Horror II"}},
        )

        self.assertEqual(filename, "S03E07 - Treehouse of Horror II.mp4")

    def test_rename_is_previewed_then_applied(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            original = root / "S03E1 Stark Raving Dad.mp4"
            original.touch()

            plan = build_rename_plan(root, {})

            self.assertEqual(len(plan), 1)
            self.assertTrue(original.exists())
            self.assertFalse(plan[0].destination.exists())

            apply_rename_plan(plan)

            self.assertFalse(original.exists())
            self.assertTrue((root / "S03E01 - Stark Raving Dad.mp4").exists())

    def test_rename_refuses_duplicate_episode_ids(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "S01E1 First.mp4").touch()
            (root / "copy S01E01 First.mkv").touch()

            with self.assertRaises(ValueError):
                build_rename_plan(root, {})


if __name__ == "__main__":
    unittest.main()

