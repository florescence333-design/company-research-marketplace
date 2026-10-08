"""Check that every shipped skill and plugin descriptor is readable by hosts."""

import json
import subprocess
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
BOM = b"\xef\xbb\xbf"


def plugin_metadata_paths():
    """Use Git's index so ignored development copies do not affect releases."""
    result = subprocess.run(
        ["git", "-c", f"safe.directory={ROOT}", "ls-files", "-z"],
        cwd=ROOT, check=True, capture_output=True,
    )
    tracked = [Path(raw.decode("utf-8")) for raw in result.stdout.split(b"\0") if raw]
    skills = [path for path in tracked if path.name == "SKILL.md" and "skills" in path.parts]
    descriptors = [path for path in tracked if path.name in {"plugin.json", "marketplace.json"}]
    return skills, descriptors


class PluginMetadataTests(unittest.TestCase):
    def test_all_skill_frontmatter_and_json_descriptors_have_no_bom(self):
        skills, descriptors = plugin_metadata_paths()
        self.assertTrue(skills, "No tracked SKILL.md files found")
        self.assertTrue(descriptors, "No tracked plugin descriptors found")

        for path in skills + descriptors:
            with self.subTest(path=str(path)):
                content = (ROOT / path).read_bytes()
                self.assertFalse(content.startswith(BOM), f"{path}: UTF-8 BOM is not allowed")
                if path in descriptors:
                    self.assertTrue(content.startswith(b"{"), f"{path}: JSON must begin with {{")
                    json.loads(content.decode("utf-8"))
                    continue

                self.assertTrue(
                    content.startswith((b"---\n", b"---\r\n")),
                    f"{path}: frontmatter must start with ---",
                )
                lines = content.decode("utf-8").splitlines()
                self.assertIn("---", lines[1:], f"{path}: frontmatter has no closing ---")
                closing = lines.index("---", 1)
                metadata = yaml.safe_load("\n".join(lines[1:closing]))
                self.assertIsInstance(metadata, dict, f"{path}: frontmatter must be a mapping")
                for field in ("name", "description"):
                    self.assertIsInstance(metadata.get(field), str, f"{path}: {field} must be text")
                    self.assertTrue(metadata[field].strip(), f"{path}: {field} must not be empty")
                self.assertLessEqual(len(metadata["description"]), 1024, f"{path}: description too long")


if __name__ == "__main__":
    unittest.main()
