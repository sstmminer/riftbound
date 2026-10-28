"""Create a small source bundle; exclude images, secrets, envs and training runs."""
import hashlib
from pathlib import Path
import subprocess
import tempfile
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
KEEP_HIGH_CODES = frozenset()


def main():
    directory = ROOT/"downloads"
    directory.mkdir(exist_ok=True)
    path = directory/"riftbound-simulator-0.3.0.zip"
    files = sorted({file for pattern in PATTERNS for file in ROOT.glob(pattern) if file.is_file()
                    and not (file.parent.name == "high"
                             and file.stem not in KEEP_HIGH_CODES)})
    with tempfile.TemporaryDirectory(prefix="riftbound-package-") as temp_name:
        temp = Path(temp_name)
        with ZipFile(path, "w", ZIP_DEFLATED) as archive:
            for file in files:
                relative = file.relative_to(ROOT)
                # Keep the source tree's RGB thumbnails intact for local GUI
                # use, but quantize the bundled previews to PNG8.  Full-color
                # originals remain in images/high and are excluded from the
                # lightweight distribution; the GUI falls back to thumbnails.
                if (relative.parts[:4] == ("riftbound", "data", "images", "OGN")
                        and file.suffix.lower() == ".png"):
                    preview = temp / relative.name
                    try:
                        subprocess.run(
                            ["convert", str(file), "-strip", "-colors", "256",
                             "-define", "png:compression-level=9", str(preview)],
                            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        )
                        archive.write(preview, Path("riftbound-simulator") / relative)
                        continue
                    except (FileNotFoundError, subprocess.CalledProcessError):
                        pass
                archive.write(file, Path("riftbound-simulator") / relative)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    (directory/"SHA256SUMS.txt").write_text(f"{digest}  {path.name}\n", encoding="utf-8")
    print(f"{path.name}: {len(files)} files, {path.stat().st_size} bytes, SHA256={digest}")


if __name__ == "__main__":
    main()
