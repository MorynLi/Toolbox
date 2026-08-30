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


def main() -> None:
    unit_rules()
    with tempfile.TemporaryDirectory(prefix="academic_plot_smoke_") as td:
        cli_smoke(Path(td))
    print("academic_plot smoke tests passed")


if __name__ == "__main__":
    main()
