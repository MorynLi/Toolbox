#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Minimal regression smoke tests for academic_plot."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from plot_common import resolve_x_window, x_tick_labels_visible
from style import _runs, label_text, load_profile, width_geometry


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, cwd=ROOT, check=True)


def unit_rules() -> None:
    axis = {"tick_label_policy": "bottom"}
    assert x_tick_labels_visible(0, 4, axis) is False
    assert x_tick_labels_visible(3, 4, axis) is True
    assert x_tick_labels_visible(0, 1, axis) is True

    window = resolve_x_window(
        [np.array([6, 12, 18, 72]), np.array([12, 24, 48, 66])],
        {"mode": "common_valid", "rebase_to_zero": True},
    )
    assert window == (12.0, 66.0, True)


def cli_smoke(tmp: Path) -> None:
    rows = []
    for station in ["A1", "A2", "A3", "A4"]:
        for x, y in [(0.0, 3), (3.1, 6), (7.25, 9), (12.0, 7)]:
            rows.append({"station": station, "time_h": x, "reference": y, "simulation": np.nan})
        for x, y in [(0.0, 2.5), (3.0, 5.8), (7.0, 9.2), (12.0, 7.2)]:
            rows.append({"station": station, "time_h": x, "reference": np.nan, "simulation": y})

    csv_path = tmp / "input.csv"
    pd.DataFrame(rows).to_csv(csv_path, index=False)
    cfg = {
        "stations": ["A1", "A2", "A3", "A4"],
        "layout": {
            "rows": 4,
            "cols": 1,
            "geometry": {
                "profile": "academic_mm_v1",
                "panel_size_mm": [90, 50],
                "gap_mm": [0, 8],
                "margin_mm": {"left": 22, "right": 8, "bottom": 16, "top": 12}
            }
        },
        "station_col": "station",
        "x_col": "time_h",
        "reference_col": "reference",
        "simulation_col": "simulation",
        "x_axis": {
            "range": [0, 12],
            "ticks": [0, 3, 6, 9, 12],
            "label": "时间(h)",
            "tick_label_policy": "bottom",
            "origin_timestamp": {"enabled": True, "text": "2014-09-15 00:00", "fontsize": 9},
            "bottom_band": {"y_mm": 8.5}
        },
        "y_axis": {"range": [0, 15], "ticks": [0, 5, 10, 15], "label": "Y"},
        "range_guard": {"mode": "error"}
    }
    cfg_path = tmp / "config.json"
    cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    run([
        "python", str(ROOT / "plot_validation.py"),
        "--input", str(csv_path),
        "--config", str(cfg_path),
        "--output", str(tmp / "out.svg")
    ])


def profile_rules() -> None:
    zh, en = load_profile("thesis_zh"), load_profile("journal_en")
    hs = {"quantity": {"zh": "有效波高", "en": "Significant wave height"}, "symbol": "H_s", "unit": "m"}
    assert label_text(hs, zh) == "有效波高 $H_s$/m"
    assert label_text(hs, en) == "$H_s$ (m)"
    assert label_text({"quantity": "风速", "symbol": "V", "unit": "m/s"}, zh) == "风速 $V$/(m/s)"
    assert label_text({"quantity": {"en": "Time"}, "unit": "h"}, en) == "Time (h)"
    assert label_text("plain", zh) == "plain"
    assert _runs("有效波高 $H_s$/m") == ["有效波高 ", "$H_s$/m"]
    assert _runs("$H_s$ (m)") == ["$H_s$ (m)"]

    geo = width_geometry({"width": "full", "panel_aspect": 0.5}, 2, 2, zh)
    margin, gap = geo["margin_mm"], geo["gap_mm"]
    total = margin["left"] + margin["right"] + 2 * geo["panel_size_mm"][0] + gap[0]
    assert abs(total - zh["widths_mm"]["full"]) < 1e-9


def svg_size(path: Path) -> tuple[str, str]:
    head = path.read_text(encoding="utf-8")[:600]
    import re
    return re.search(r'width="([^"]+)"', head).group(1), re.search(r'height="([^"]+)"', head).group(1)


def profile_smoke(tmp: Path) -> None:
    """Same config + different data must give an identical canvas; outputs + caption written."""
    cfg = {
        "profile": "thesis_zh",
        "stations": ["A1", "A2"],
        "layout": {"rows": 2, "cols": 1, "geometry": {"profile": "academic_mm_v1", "width": "full", "panel_aspect": 0.3}},
        "x_col": "time_h", "reference_col": "reference", "simulation_col": "simulation",
        "x_axis": {"range": [0, 12], "ticks": [0, 6, 12], "label": {"quantity": "时间", "unit": "h"}},
        "y_axis": {"range": [0, 1500], "ticks": [0, 500, 1000, 1500], "label": {"quantity": "有效波高", "symbol": "H_s", "unit": "m"}},
        "range_guard": {"mode": "error"},
        "caption": {"zh": "测试", "en": "Test"},
    }
    (tmp / "p.json").write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
    sizes = []
    for scale in (1, 100):
        rows = [{"station": s, "time_h": t, "reference": scale * (t + 1), "simulation": scale * t} for s in ["A1", "A2"] for t in range(13)]
        pd.DataFrame(rows).to_csv(tmp / f"p{scale}.csv", index=False)
        run(["python", str(ROOT / "plot_validation.py"), "--input", str(tmp / f"p{scale}.csv"),
             "--config", str(tmp / "p.json"), "--output", str(tmp / f"p{scale}.svg"), "--draft"])
        for ext in ("svg", "pdf", "png", "tex"):
            assert (tmp / f"p{scale}.{ext}").exists(), ext
        sizes.append(svg_size(tmp / f"p{scale}.svg"))
    assert sizes[0] == sizes[1], sizes


def map_smoke(tmp: Path) -> None:
    lon, lat = np.arange(105, 121.01, 0.5), np.arange(8, 25.01, 0.5)
    xx, yy = np.meshgrid(lon, lat)
    value = 1.2 + 0.4 * np.sin(xx / 4) * np.cos(yy / 5)
    pd.DataFrame({"lon": xx.ravel(), "lat": yy.ravel(), "value": value.ravel()}).to_csv(tmp / "f.csv", index=False)
    land = {"type": "Polygon", "coordinates": [[[105, 20], [110, 25], [105, 25], [105, 20]]]}
    (tmp / "land.geojson").write_text(json.dumps(land), encoding="utf-8")
    cfg = {
        "profile": "thesis_zh",
        "layout": {"rows": 1, "cols": 2, "geometry": {"profile": "academic_mm_v1", "width": "full"}},
        "map": {"extent": [105, 121, 8, 25], "xticks": [106, 110, 114, 118], "yticks": [10, 15, 20, 25], "land": {"source": "land.geojson"}},
        "panels": [{"input": "f.csv"}, {"input": "f.csv"}],
        "field": {"levels": {"start": 0.5, "stop": 2.0, "step": 0.1}, "ticks": [0.5, 1.0, 1.5, 2.0],
                  "label": {"quantity": "有效波高", "symbol": "H_s", "unit": "m"}},
    }
    (tmp / "m.json").write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
    run(["python", str(ROOT / "plot_map.py"), "--config", str(tmp / "m.json"), "--output", str(tmp / "m.svg"), "--draft"])

    # Edge ticks on adjacent panels collide: the text QC must refuse the figure.
    cfg["map"]["xticks"] = [105, 110, 115, 120]
    cfg["layout"]["cols"] = 3
    cfg["panels"] = [{"input": "f.csv"}] * 3
    (tmp / "bad.json").write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
    bad = subprocess.run(["python", str(ROOT / "plot_map.py"), "--config", str(tmp / "bad.json"),
                          "--output", str(tmp / "bad.svg"), "--draft"], cwd=ROOT, capture_output=True, text=True)
    assert bad.returncode != 0 and "Text layout QC failed" in bad.stderr, bad.stderr[-500:]

    # Data outside the colour levels must fail, not be clipped silently.
    cfg["map"]["xticks"] = [106, 110, 114, 118]
    cfg["field"]["levels"] = {"start": 0.5, "stop": 1.2, "step": 0.1}
    (tmp / "range.json").write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
    bad = subprocess.run(["python", str(ROOT / "plot_map.py"), "--config", str(tmp / "range.json"),
                          "--output", str(tmp / "range.svg"), "--draft"], cwd=ROOT, capture_output=True, text=True)
    assert bad.returncode != 0 and "exceeds levels" in bad.stderr, bad.stderr[-500:]


def main() -> None:
    unit_rules()
    profile_rules()
    with tempfile.TemporaryDirectory(prefix="academic_plot_smoke_") as td:
        cli_smoke(Path(td))
        profile_smoke(Path(td))
        map_smoke(Path(td))
    print("academic_plot smoke tests passed")


if __name__ == "__main__":
    main()
