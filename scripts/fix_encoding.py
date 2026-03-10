"""
One-time script to repair mojibake in existing JSON data files.

Mojibake occurs when UTF-8 bytes are decoded as Latin-1/ISO-8859-1, producing
strings like "JÃ¼rgen" instead of "Jürgen". This script uses ftfy to detect
and fix all such corrupted strings in-place.

Usage:
    python scripts/fix_encoding.py
"""

import json
import ftfy
from pathlib import Path

DATA_FILES = [
    "data/people.json",
    "data/raw_events.json",
    "data/research.json",
    "data/general.json",
]


def fix_value(value):
    """Recursively fix encoding in any string within a JSON structure."""
    if isinstance(value, str):
        return ftfy.fix_text(value)
    if isinstance(value, list):
        return [fix_value(v) for v in value]
    if isinstance(value, dict):
        return {k: fix_value(v) for k, v in value.items()}
    return value


def fix_file(path: Path) -> int:
    """Fix encoding in a single JSON file. Returns number of changed values."""
    if not path.exists():
        print(f"  Skipping {path} (not found)")
        return 0

    original = path.read_text(encoding="utf-8")
    data = json.loads(original)
    fixed_data = fix_value(data)
    fixed = json.dumps(fixed_data, ensure_ascii=False, indent=4)

    if fixed == original:
        print(f"  {path}: no changes needed")
        return 0

    path.write_text(fixed, encoding="utf-8")
    # Count changed strings by comparing lengths as a rough proxy
    diff = abs(len(fixed) - len(original))
    print(f"  {path}: repaired (delta {diff:+d} chars)")
    return 1


def main():
    print("Repairing encoding in JSON data files...")
    root = Path(__file__).parent.parent
    changed = 0
    for rel_path in DATA_FILES:
        changed += fix_file(root / rel_path)
    print(f"\nDone. {changed} file(s) updated.")


if __name__ == "__main__":
    main()
