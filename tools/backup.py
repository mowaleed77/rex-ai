"""Backup helper: copy files into backups/<timestamp>/ keeping their folder layout.

Usage (from the project root):
    python tools/backup.py                      # back up the default "files we modify" list
    python tools/backup.py path/a.py path/b.py  # back up specific files
    python tools/backup.py --restore backups/20261105-0900   # copy a backup back over the project
"""
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_FILES = [
    "apps/agents_ui.py",
    "rex/agents/orchestrator.py",
    "rex/agents/marketing.py",
    "rex/agents/curriculum.py",
    "rex/agents/document.py",
    "rex/assistant/engine.py",
    "requirements.txt",
    "tests/test_marketing.py",
    "tests/test_orchestrator.py",
]


def backup(files=None) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = ROOT / "backups" / stamp
    copied = 0
    for rel in files or DEFAULT_FILES:
        src = ROOT / rel
        if not src.is_file():
            print(f"skip (not found): {rel}")
            continue
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)
        copied += 1
    print(f"Backed up {copied} file(s) to {dest.relative_to(ROOT)}")
    return dest


def restore(folder: str) -> None:
    src_root = (ROOT / folder).resolve()
    if not src_root.is_dir():
        sys.exit(f"Backup folder not found: {folder}")
    for src in src_root.rglob("*"):
        if src.is_file():
            target = ROOT / src.relative_to(src_root)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, target)
            print(f"restored {target.relative_to(ROOT)}")


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "--restore":
        restore(args[1] if len(args) > 1 else sys.exit("Give the backup folder to restore."))
    else:
        backup(args or None)
