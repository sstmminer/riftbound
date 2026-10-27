"""Create a small source bundle; exclude images, secrets, envs and training runs."""
import hashlib
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = ["README.md", "pyproject.toml", ".gitignore", ".python-version", "riftbound/*.py",
            "riftbound/data/*.json", "riftbound/data/images/*.png", "riftbound/data/images/OGN/*.png",
            "riftbound/data/images/high/*.png",
            "tests/*.py", "tools/*.py", "docs/*.md",
            "docs/*.json", "examples/*.json", ".github/workflows/*.yml"]

# GitHub's regular file limit is 100 MB.  The source tree contains every
# high-resolution hover asset; the lightweight bundle keeps a curated set and
# falls back to the clear thumbnail for the remaining cards.
KEEP_HIGH_CODES = frozenset({
    "OGN-001", "OGN-003", "OGN-027", "OGN-030", "OGN-039", "OGN-065",
    "OGN-066", "OGN-088", "OGN-131", "OGN-142", "OGN-148", "OGN-159",
    "OGN-171", "OGN-210", "OGN-215", "OGN-217", "OGN-219", "OGN-232",
    "OGN-234", "OGN-247", "OGN-251", "OGN-253", "OGN-265",
})


def main():
    directory = ROOT/"downloads"
    directory.mkdir(exist_ok=True)
    path = directory/"riftbound-simulator-0.3.0.zip"
    files = sorted({file for pattern in PATTERNS for file in ROOT.glob(pattern) if file.is_file()
                    and not (file.parent.name == "high"
                             and file.stem not in KEEP_HIGH_CODES)})
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        for file in files:
            archive.write(file, Path("riftbound-simulator")/file.relative_to(ROOT))
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    (directory/"SHA256SUMS.txt").write_text(f"{digest}  {path.name}\n", encoding="utf-8")
    print(f"{path.name}: {len(files)} files, {path.stat().st_size} bytes, SHA256={digest}")


if __name__ == "__main__":
    main()
