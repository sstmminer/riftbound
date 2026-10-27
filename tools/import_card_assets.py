"""Import selected Origins artwork from the pinned archive.

The archive stores artwork by a content hash.  The simulator uses stable
``OGN-xxx`` filenames, so this tool resolves the archive metadata and creates
the portrait thumbnail, the rotated exhausted-state image, and the original
high-resolution hover image for explicitly requested cards.

It accepts either a checked-out archive directory (containing ``data`` and
``images``) or a Git ref such as ``origin/archive-download``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]


def _archive_bytes(ref: str, path: str) -> bytes:
    result = subprocess.run(
        ["git", "show", f"{ref}:{path}"],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
    )
    return result.stdout


def _read_metadata(archive_root: Path | None, ref: str) -> list[dict]:
    if archive_root is not None:
        return json.loads((archive_root / "data/cards.json").read_text(encoding="utf-8"))
    return json.loads(_archive_bytes(ref, "data/cards.json"))


def _source_image(archive_root: Path | None, ref: str, local_path: str, temp: Path) -> Path:
    if archive_root is not None:
        source = archive_root / local_path
        if not source.is_file():
            raise FileNotFoundError(source)
        return source
    destination = temp / Path(local_path).name
    destination.write_bytes(_archive_bytes(ref, local_path))
    return destination


def _convert(source: Path, destination: Path, *arguments: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            ["convert", str(source), *arguments, str(destination)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        # A checked-out source image remains usable by Tk even when ImageMagick
        # is unavailable; it is preferable to a missing asset.
        shutil.copyfile(source, destination)


def _is_portrait_png(path: Path) -> bool:
    """Read PNG dimensions without adding a Pillow runtime dependency."""

    with path.open("rb") as stream:
        header = stream.read(24)
    if header[:8] != b"\x89PNG\r\n\x1a\n" or len(header) < 24:
        return False
    width, height = struct.unpack(">II", header[16:24])
    return height > width


def import_assets(codes: list[str], *, archive_root: Path | None = None,
                  ref: str = "origin/archive-download",
                  data_dir: Path = ROOT / "riftbound/data") -> list[str]:
    rows = {
        row["official_card_id"]: row
        for row in _read_metadata(archive_root, ref)
        if row.get("official_card_id", "").startswith("ogn-")
    }
    images = data_dir / "images" / "OGN"
    high = data_dir / "images" / "high"
    manifest_path = data_dir / "card_images.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_cards = manifest.setdefault("cards", {})
    imported: list[str] = []
    with tempfile.TemporaryDirectory(prefix="riftbound-assets-") as temp_name:
        temp = Path(temp_name)
        for code in codes:
            code = code.upper()
            if not code.startswith("OGN-"):
                code = f"OGN-{int(code):03d}"
            number = int(code.split("-", 1)[1])
            official = f"ogn-{number:03d}-298"
            row = rows.get(official)
            if row is None:
                raise ValueError(f"archive has no Origins card {code}")
            source = _source_image(archive_root, ref, row["local_image_path"], temp)
            portrait = images / f"{code}.png"
            high_path = high / f"{code}.png"
            _convert(source, portrait, "-resize", "360x")
            high_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, high_path)
            # All unit/legend/rune portrait assets need the rotated exhausted
            # state.  Landscape battlefields are intentionally left alone.
            if source.stat().st_size and source.suffix.lower() == ".png" and _is_portrait_png(source):
                _convert(portrait, images / f"{code}-horizontal.png", "-rotate", "90")
            manifest_cards[code] = f"images/OGN/{code}.png"
            imported.append(code)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return imported


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("codes", nargs="+", help="OGN-xxx card codes")
    parser.add_argument("--archive-root", type=Path,
                        help="checked-out archive-download directory")
    parser.add_argument("--git-ref", default="origin/archive-download",
                        help="Git ref containing data/cards.json and images")
    parser.add_argument("--data-dir", type=Path, default=ROOT / "riftbound/data")
    args = parser.parse_args()
    imported = import_assets(args.codes, archive_root=args.archive_root,
                             ref=args.git_ref, data_dir=args.data_dir)
    print(f"Imported {len(imported)} assets: {', '.join(imported)}")


if __name__ == "__main__":
    main()
