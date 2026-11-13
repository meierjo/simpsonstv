import json
import tempfile
import unittest
from pathlib import Path

from tools.analyze_intros import (
    FINGERPRINT_RATE,
    analyze_candidates,
    choose_audio_prefix_candidate,
    fingerprint_prefix_end,
    fingerprint_similarity,
    nearest_black_boundary,
)
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

    def test_fingerprint_prefix_end_finds_sustained_divergence(self):
        shared_frames = int(30 * FINGERPRINT_RATE)
        tail_frames = int(10 * FINGERPRINT_RATE)
        left = ([0x12345678] * shared_frames) + ([0] * tail_frames)
        right = ([0x12345678] * shared_frames) + ([0xFFFFFFFF] * tail_frames)
        cue, score = fingerprint_prefix_end(left, right)
        self.assertAlmostEqual(cue, 30.0, delta=0.2)
        self.assertGreater(score, 0.95)

    def test_audio_prefix_cluster_ignores_lone_late_outlier(self):
        selected = choose_audio_prefix_candidate(
            [
                (50.0, 0.91, "S03E02"),
                (52.0, 0.90, "S03E03"),
                (99.0, 0.99, "S03E04"),
            ]
        )
        self.assertEqual(selected[0], 52.0)
        self.assertEqual(selected[2], 2)

    def test_audio_candidate_snaps_to_nearby_black_boundary(self):
        self.assertEqual(nearest_black_boundary(59.0, (49.2, 74.88)), 49.2)
        self.assertIsNone(nearest_black_boundary(59.0, (20.0, 90.0)))

    def test_invalid_chapter_uses_audio_prefix_as_intro_end(self):
        episodes = (self.episode("S05E01", 1), self.episode("S05E02", 2))
        shared_frames = int(30 * FINGERPRINT_RATE)
        tail_frames = int(10 * FINGERPRINT_RATE)
        candidates = analyze_candidates(
            episodes,
            {
                "S05E01": ([0xAAAAAAAA] * shared_frames) + ([0] * tail_frames),
                "S05E02": ([0xAAAAAAAA] * shared_frames)
                + ([0xFFFFFFFF] * tail_frames),
            },
            {"S05E01": 0.0, "S05E02": 0.0},
            black_starts={"S05E01": (29.8,), "S05E02": (29.9,)},
        )
        candidate = candidates["S05E01"]
        self.assertEqual(candidate["intro_end"], 29.8)
        self.assertEqual(candidate["chapter_end"], 0.0)
        self.assertEqual(candidate["detection_method"], "audio-prefix")
        self.assertAlmostEqual(candidate["raw_audio_intro_end"], 30.0, delta=0.2)


if __name__ == "__main__":
    unittest.main()
