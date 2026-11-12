import json
import tempfile
import unittest
from pathlib import Path

from tools.analyze_intros import analyze_candidates, fingerprint_similarity
from tools.review_intro_cues import export_reviewed_cues, load_candidates, save_review
from tv.catalog import Episode


class IntroAnalysisTests(unittest.TestCase):
    def episode(self, episode_id, number):
        return Episode(episode_id, 5, number, episode_id, Path(episode_id + ".mp4"))

    def test_identical_fingerprints_are_high_confidence_peers(self):
        episodes = (self.episode("S05E01", 1), self.episode("S05E02", 2))
        fingerprint = [0x12345678] * 800
        candidates = analyze_candidates(
            episodes,
            {"S05E01": fingerprint, "S05E02": fingerprint},
            {"S05E01": 30.0, "S05E02": 31.0},
        )
        self.assertEqual(candidates["S05E01"]["confidence"], "high")
        self.assertEqual(candidates["S05E01"]["best_peer"], "S05E02")

    def test_unrelated_special_is_low_confidence(self):
        episodes = (self.episode("S05E01", 1), self.episode("S05E02", 2))
        candidates = analyze_candidates(
            episodes,
            {"S05E01": [0] * 800, "S05E02": [0xFFFFFFFF] * 800},
            {"S05E01": 30.0, "S05E02": 30.0},
        )
        self.assertEqual(candidates["S05E01"]["confidence"], "low")

    def test_review_saves_adjusted_cue_and_exports_only_approved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidates_path = root / "candidates.json"
            candidates_path.write_text(
                json.dumps(
                    {
                        "season": 5,
                        "episodes": {
                            "S05E01": {"intro_end": 30.0, "reviewed": False},
                            "S05E02": {"intro_end": 31.0, "reviewed": False},
                        },
                    }
                )
            )
            save_review(
                candidates_path,
                {"cue_S05E01": ["32.5"], "reviewed_S05E01": ["on"]},
            )
            saved = load_candidates(candidates_path)
            self.assertEqual(saved["episodes"]["S05E01"]["intro_end"], 32.5)
            self.assertTrue(saved["episodes"]["S05E01"]["reviewed"])
            self.assertFalse(saved["episodes"]["S05E02"]["reviewed"])

            output = root / "break-cues.json"
            count = export_reviewed_cues(candidates_path, output)
            self.assertEqual(count, 1)
            self.assertEqual(json.loads(output.read_text())["episode_cues"], {"S05E01": 32.5})

    def test_similarity_tolerates_one_frame_alignment_jitter(self):
        left = [1, 2, 3, 4] * 20
        right = [99] + left
        self.assertGreater(fingerprint_similarity(left, right, 5), 0.95)


if __name__ == "__main__":
    unittest.main()
