#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Draw a field map from a locked preset: the caller chooses only data, colour scale, title and captions.

    python plot_preset_map.py --preset scs_field --scale 平均有效波高 --input field.csv \
        --title "南海1986—2025年平均有效波高" --output-dir out [--caption-zh ...] [--caption-en ...]
    python plot_preset_map.py --list

Input CSV: columns lon, lat, value for every sea cell; a row with an empty value stays blank (e.g. too
few samples); cells absent from the CSV (land) are not drawn. The title is not drawn inside the image:
files are named <title>.png/.svg/.caption.txt/.tex, and the exact spec + input go to <output-dir>/_数据/.
Presets live in presets/<name>.json ("spec" = the look, "scales" = allowed colour scales). Changing a
preset changes every figure made from it: do it only on the user's explicit request and update
tests/preset_check.py together.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path

import pandas as pd

import plot_map

PRESET_DIR = Path(__file__).with_name("presets")
WINDOWS_FONTS = Path(r"C:\Windows\Fonts")


def load_preset(name: str) -> dict:
    path = PRESET_DIR / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"Unknown preset '{name}'; available: {available()}")
    return json.loads(path.read_text(encoding="utf-8"))


def available() -> list[str]:
    return sorted(p.stem for p in PRESET_DIR.glob("*.json"))


def build_spec(preset: str, scale: str, data_csv: Path, caption_zh: str = "", caption_en: str = "") -> dict:
    p = load_preset(preset)
    if scale not in p["scales"]:
        raise KeyError(f"Preset '{preset}' has no scale '{scale}'; available: {list(p['scales'])}. "
                       "A new scale changes the preset: ask the user first.")
    spec = copy.deepcopy(p["spec"])
    land = spec.get("map", {}).get("land", {})
    if land.get("source") not in (None, "none", "natural_earth"):
        land["source"] = str((PRESET_DIR / land["source"]).resolve())
    spec["field"].update(p["scales"][scale])
    spec["panels"] = [{"input": str(Path(data_csv).resolve())}]
    if caption_zh or caption_en:
        spec["caption"] = {"zh": caption_zh, "en": caption_en}
    return spec


def draw_preset(frame: pd.DataFrame | str | Path, out_dir: str | Path, *, preset: str, scale: str, title: str,
                caption_zh: str = "", caption_en: str = "", font_dir: str | Path | None = None) -> list[Path]:
    """Render one map. frame: DataFrame or CSV path with exactly the columns lon, lat, value."""
    frame = frame if isinstance(frame, pd.DataFrame) else pd.read_csv(frame)
    if set(frame.columns) != {"lon", "lat", "value"}:
        raise ValueError(f"input must have exactly the columns lon, lat, value; got {list(frame.columns)}")
    if any(c in title for c in '\\/:*?"<>|'):
        raise ValueError(f"title is used as the file name and may not contain \\/:*?\"<>|: {title}")
    out_dir = Path(out_dir)
    data_dir = out_dir / "_数据"
    data_dir.mkdir(parents=True, exist_ok=True)
    csv = data_dir / f"{title}.csv"
    frame[["lon", "lat", "value"]].to_csv(csv, index=False)
    spec = build_spec(preset, scale, csv, caption_zh, caption_en)
    (data_dir / f"{title}.spec.json").write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
    if font_dir is None and not os.environ.get("ACADEMIC_PLOT_FONT_DIR") and WINDOWS_FONTS.exists():
        font_dir = WINDOWS_FONTS
    return plot_map.draw_main(spec, out_dir / f"{title}.png", out_dir, font_dir=Path(font_dir) if font_dir else None)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", action="store_true", help="list presets and their scales")
    ap.add_argument("--preset")
    ap.add_argument("--scale")
    ap.add_argument("--input", type=Path, help="CSV with lon, lat, value")
    ap.add_argument("--title")
    ap.add_argument("--output-dir", type=Path)
    ap.add_argument("--caption-zh", default="")
    ap.add_argument("--caption-en", default="")
    ap.add_argument("--font-dir", type=Path, default=None)
    args = ap.parse_args()
    if args.list:
        for name in available():
            p = load_preset(name)
            print(f"{name}: scales = {', '.join(p['scales'])}\n  {p.get('description', '')}")
        return
    missing = [k for k in ("preset", "scale", "input", "title", "output_dir") if not getattr(args, k)]
    if missing:
        ap.error("missing " + ", ".join("--" + k.replace("_", "-") for k in missing))
    for path in draw_preset(args.input, args.output_dir, preset=args.preset, scale=args.scale, title=args.title,
                            caption_zh=args.caption_zh, caption_en=args.caption_en, font_dir=args.font_dir):
        print(path)


if __name__ == "__main__":
    main()
