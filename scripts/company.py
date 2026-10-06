"""Run the small, reproducible company-analysis path (v0.1)."""

import argparse
import json
import shutil
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from validate_bundle import validate_bundle


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ticker")
    parser.add_argument("--engine", choices=("claude", "gpt"), required=True)
    parser.add_argument("--sample", action="store_true", help="Copy visibly synthetic RKLB example")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    ticker = args.ticker.upper()
    if not args.sample:
        parser.error("Real SEC collection is not connected yet; use --sample for the stage-2 smoke test")
    if ticker != "RKLB":
        parser.error("The synthetic sample currently supports RKLB only")
    run_id = f"sample-{ticker.lower()}-{uuid.uuid4().hex[:12]}"
    output = args.output or ROOT / "runs" / ticker / args.engine / run_id
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        parser.error(f"Output directory is not empty: {output}")
    for source in (ROOT / "examples" / "sample-rklb").glob("*.json"):
        shutil.copy2(source, output / source.name)
    meta_path = output / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta.update(run_id=run_id, engine=args.engine, generated_at=datetime.now(timezone.utc).isoformat())
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for filename in ("metrics.json", "decision.json"):
        path = output / filename
        data = json.loads(path.read_text(encoding="utf-8"))
        data["run_id"] = run_id
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    errors = validate_bundle(output)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print(str(output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
