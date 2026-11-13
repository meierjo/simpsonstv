import json
import tempfile
import unittest
from pathlib import Path

from tools.preview_intro_break import build_pilot


class IntroPreviewTests(unittest.TestCase):
    def test_pilot_resolves_reviewed_episode_and_matching_commercial(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "videos").mkdir()
            (root / "videos" / "S05E10 Test.mp4").touch()
            (root / "config").mkdir()
            (root / "commercials" / "v2" / "1993").mkdir(parents=True)
            (root / "commercials" / "v2" / "manifests").mkdir()
            commercial = root / "commercials" / "v2" / "1993" / "ad.mp4"
            commercial.touch()
            (root / "config" / "episodes.json").write_text('{"episodes": {}}')
            (root / "config" / "broadcast_years.json").write_text(
                '{"seasons": {"5": [[10, 1993], [22, 1994]]}}'
            )
            (root / "config" / "break_cues.json").write_text(
                '{"episode_cues": {"S05E10": 33.066}, "season_defaults": {}}'
            )
            (root / "config" / "commercials.json").write_text(
                '{"root": "commercials/v2", "recent_limit": 12}'
            )
            (root / "commercials" / "v2" / "manifests" / "1993.json").write_text(
                json.dumps(
                    {
                        "year": 1993,
                        "clips": [
                            {
                                "file": "1993/ad.mp4",
                                "approved": True,
                                "kind": "commercial",
                            }
                        ],
                    }
                )
            )

            episode, cue, preroll = build_pilot("S05E10", root)

            self.assertEqual(episode.episode_id, "S05E10")
            self.assertEqual(cue, 33.066)
            self.assertEqual([clip.path for clip in preroll], [commercial.resolve()])


if __name__ == "__main__":
    unittest.main()
