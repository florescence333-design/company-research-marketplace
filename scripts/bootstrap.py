"""Prepare an isolated company-analysis workspace from the installed plugin.

Run with ``uv run --no-project --python 3.14 <plugin>/scripts/bootstrap.py``.
Only uv and Node.js/npm need to be installed in advance; uv provisions Python.
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo")


def copy_runtime(destination: Path) -> None:
    """Copy public runtime files, never analysis data or local credentials."""
    if destination == PLUGIN_ROOT or PLUGIN_ROOT in destination.parents:
        raise ValueError("작업 폴더는 설치된 플러그인 폴더 밖에 두세요")
    marker = destination / ".company-plugin-workspace"
    if destination.exists() and any(destination.iterdir()) and not marker.is_file():
        raise ValueError(f"비어 있지 않은 다른 폴더를 덮어쓰지 않습니다: {destination}")

    required = ["requirements-dev.txt", "template", "schemas", "examples/sample-rklb",
                "scripts", "site/package.json", "site/package-lock.json", "site/astro.config.mjs",
                "site/src", "site/functions", "site/scripts", "site/test",
                "docs/020. 기업분석_Master Template.md"]
    missing = [item for item in required if not (PLUGIN_ROOT / item).exists()]
    if missing:
        raise ValueError("플러그인 설치 파일 누락: " + ", ".join(missing))

    destination.mkdir(parents=True, exist_ok=True)
    marker.write_text("company-analysis workspace\n", encoding="utf-8")
    for relative in required:
        source = PLUGIN_ROOT / relative
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, target, dirs_exist_ok=True, ignore=IGNORE)
        else:
            shutil.copy2(source, target)
    gitignore = PLUGIN_ROOT / ".gitignore"
    if gitignore.is_file():
        shutil.copy2(gitignore, destination / ".gitignore")


def run(command: list[str], cwd: Path) -> None:
    subprocess.run(command, cwd=cwd, check=True)


def prepare(destination: Path) -> Path:
    destination = destination.resolve()
    copy_runtime(destination)
    uv = shutil.which("uv")
    npm = shutil.which("npm.cmd" if sys.platform == "win32" else "npm")
    if not uv:
        raise RuntimeError("uv가 없습니다. Windows: winget install --id astral-sh.uv -e")
    if not npm:
        raise RuntimeError("npm이 없습니다. Windows: winget install --id OpenJS.NodeJS.LTS -e")
    python = destination / ".venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    if not python.is_file():
        run([uv, "venv", "--python", "3.14", str(destination / ".venv")], destination)
    run([uv, "pip", "install", "--python", str(python), "-r", str(destination / "requirements-dev.txt")], destination)
    run([npm, "ci", "--prefix", str(destination / "site")], destination)
    print(f"WORKSPACE={destination}")
    print(f"PYTHON={python}")
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, default=Path.cwd() / ".company-research")
    args = parser.parse_args()
    try:
        prepare(args.destination)
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"준비 실패: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
