import json
import unittest
from pathlib import Path

from ai_mouse_lab import __version__

ROOT = Path(__file__).resolve().parents[1]


class ProductContractTests(unittest.TestCase):
    def test_active_app_contains_no_free_record_or_legacy_wrapper(self):
        source = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertNotIn("Free Record", source)
        self.assertNotIn("free_record", source.lower())
        self.assertNotIn("app_v1", source)
        self.assertNotIn("LegacyApp", source)

    def test_all_version_sources_match(self):
        version_file = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        metadata = json.loads((ROOT / "turbo-project.json").read_text(encoding="utf-8"))
        self.assertEqual(__version__, version_file)
        self.assertEqual(__version__, metadata["version"])

    def test_turbo_metadata_describes_aim_lab_only_scope(self):
        metadata = json.loads((ROOT / "turbo-project.json").read_text(encoding="utf-8"))
        notes = str(metadata.get("notes", "")).lower()
        self.assertIn("aim lab", notes)
        self.assertNotIn("free record", notes)


if __name__ == "__main__":
    unittest.main()
