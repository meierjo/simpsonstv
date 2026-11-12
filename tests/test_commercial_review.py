import json
import tempfile
import unittest
from pathlib import Path

from tools.review_commercials import load_manifest, render_review, reset_conservative, save_selections


class CommercialReviewTests(unittest.TestCase):
    def make_library(self, directory):
        root = Path(directory)
        (root / "manifests").mkdir()
        manifest_path = root / "manifests" / "1994-test.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "year": 1994,
                    "status": "approved",
                    "clips": [
                        {
                            "sequence": 1,
                            "file": "1994/one.mp4",
                            "duration": 30.0,
                            "kind": "commercial",
                            "approved": True,
                        },
                        {
                            "sequence": 2,
                            "file": "1994/two.mp4",
                            "duration": 45.0,
                            "kind": "long-form-candidate",
                            "approved": True,
                        },
                        {
                            "sequence": 3,
                            "file": "1994/bumper.mp4",
                            "duration": 10.0,
                            "kind": "sponsor-bumper",
                            "approved": True,
                        },
                    ],
                }
            )
        )
        return root, manifest_path

    def test_saved_keep_choices_update_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            root, path = self.make_library(directory)
            kept = save_selections(path, ["2"])
            manifest = load_manifest(path)
            self.assertEqual(kept, 1)
            self.assertEqual(
                [clip["approved"] for clip in manifest["clips"]],
                [False, True, False],
            )
            self.assertEqual(manifest["status"], "needs-review")

    def test_conservative_reset_keeps_normal_spots_and_bumpers(self):
        with tempfile.TemporaryDirectory() as directory:
            root, path = self.make_library(directory)
            manifests, kept = reset_conservative(root)
            manifest = load_manifest(path)
            self.assertEqual((manifests, kept), (1, 2))
            self.assertEqual(
                [clip["approved"] for clip in manifest["clips"]],
                [True, False, True],
            )

    def test_review_page_has_persistent_keep_form(self):
        with tempfile.TemporaryDirectory() as directory:
            root, path = self.make_library(directory)
            document = render_review(root, path)
            self.assertIn("Save this year", document)
            self.assertIn("name='keep'", document)
            self.assertIn("/save/1994-test.json", document)


if __name__ == "__main__":
    unittest.main()
