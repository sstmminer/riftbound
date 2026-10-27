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

# GitHub's regular file limit is 100 MB.  Keep the legacy high-resolution
# hover assets in the lightweight bundle and let newly added cards use their
# bundled clear thumbnails; source checkouts still contain every high image.
OMIT_HIGH_CODES = frozenset({
    "OGN-053", "OGN-069", "OGN-083", "OGN-087", "OGN-096", "OGN-104",
    "OGN-132", "OGN-136", "OGN-137", "OGN-169", "OGN-172", "OGN-213",
    "OGN-220", "OGN-249", "OGN-255", "OGN-277", "OGN-280", "OGN-288",
    "OGN-290", "OGN-295", "OGN-298",
    "OGN-035", "OGN-043", "OGN-130", "OGN-134", "OGN-173", "OGN-216",
    "OGN-238", "OGN-241", "OGN-275", "OGN-283", "OGN-296",
})


def main():
    directory = ROOT/"downloads"
    directory.mkdir(exist_ok=True)
    path = directory/"riftbound-simulator-0.3.0.zip"
    files = sorted({file for pattern in PATTERNS for file in ROOT.glob(pattern) if file.is_file()
                    and not (file.parent.name == "high"
                             and file.stem in OMIT_HIGH_CODES)})
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        for file in files:
            archive.write(file, Path("riftbound-simulator")/file.relative_to(ROOT))
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    (directory/"SHA256SUMS.txt").write_text(f"{digest}  {path.name}\n", encoding="utf-8")
    print(f"{path.name}: {len(files)} files, {path.stat().st_size} bytes, SHA256={digest}")


if __name__ == "__main__":
    main()
