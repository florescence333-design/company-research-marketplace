"""Extract the numbered top-level sections from the user-supplied master."""

import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "docs" / "020. 기업분석_Master Template.md"
OUTPUT = ROOT / "template" / "sections.json"
HEADING = re.compile(r"^#\s+(?:\*\*)?(\d+)\.\s*(.+?)\s*$", re.MULTILINE)


def extract_sections(markdown: str) -> list[dict[str, object]]:
    found = []
    for match in HEADING.finditer(markdown):
        number = int(match.group(1))
        title = match.group(2).strip().removesuffix("**").strip()
        found.append({"section_id": f"S{number:02d}", "title": title, "required": True})
    if [entry["section_id"] for entry in found] != [f"S{i:02d}" for i in range(1, 17)]:
        raise ValueError("Master Template must contain numbered sections 1–16 exactly once")
    return found


def main() -> None:
    raw = MASTER.read_bytes()
    document = {
        "schema_version": "v1-draft",
        "source_path": "docs/020. 기업분석_Master Template.md",
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "sections": extract_sections(raw.decode("utf-8-sig")),
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(document['sections'])} sections to {OUTPUT}")


if __name__ == "__main__":
    main()
