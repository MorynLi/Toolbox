#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate reusable multi-variable reference-vs-simulation validation plots as SVG."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from plot_common import (
    add_embedded_legend,
    audit_axis_range,
    break_circular,
    configure_fonts,
    make_figure_axes,
    resolve_geometry,
    save_main_figure,
)

__version__ = "1.2.0"

DEFAULT_STYLE: dict[str, Any] = {
    "reference_color": "#8B0000",
    "reference_linestyle": "--",
    "simulation_color": "#000000",
    "simulation_linestyle": "-",
    "reference_line_width": 1.6,
    "simulation_line_width": 1.8,
    "spine_width": 1.15,
    "tick_width": 1.0,
    "tick_length": 4.0,
    "tick_fontsize": 12,
    "axis_label_fontsize": 14,
    "panel_label_fontsize": 13,
}

REQUIRED_CONFIG_KEYS = {"layout", "x_axis", "panels"}
TIME_UNIT_SECONDS = {"s": 1.0, "min": 60.0, "h": 3600.0, "d": 86400.0}
PLOT_X = "__plot_x__"


def load_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        config = json.load(file)
    missing = REQUIRED_CONFIG_KEYS - config.keys()
    if missing:
        raise ValueError(f"Config missing required keys: {', '.join(sorted(missing))}")

    style = DEFAULT_STYLE.copy()
    style.update(config.get("style", {}))
    if "line_width" in config.get("style", {}):
        legacy_width = float(config["style"]["line_width"])
        style["reference_line_width"] = legacy_width
        style["simulation_line_width"] = legacy_width
    config["style"] = style
    return config


def prepare_x(data: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    output = data.copy()
    transform = config.get("time_transform")
    if transform:
        datetime_col = str(transform["datetime_col"])
        if datetime_col not in output.columns:
            raise ValueError(f"Input CSV missing datetime column: {datetime_col}")

        unit = str(transform.get("unit", "h"))
        if unit not in TIME_UNIT_SECONDS:
            raise ValueError(f"Unsupported time unit '{unit}'. Use one of: {', '.join(TIME_UNIT_SECONDS)}")

        times = pd.to_datetime(output[datetime_col], errors="raise")
        origin = pd.Timestamp(transform["origin"])
        output[PLOT_X] = (times - origin).dt.total_seconds() / TIME_UNIT_SECONDS[unit]
        return output

    x_col = str(config.get("x_col", "time_h"))
    if x_col not in output.columns:
        raise ValueError(f"Input CSV missing x column: {x_col}")
    output[PLOT_X] = pd.to_numeric(output[x_col], errors="raise")
    return output


def validate_inputs(data: pd.DataFrame, config: dict[str, Any]) -> None:
    rows = int(config["layout"]["rows"])
    cols = int(config["layout"]["cols"])
    panels = config["panels"]
    if rows <= 0 or cols <= 0:
        raise ValueError("layout.rows and layout.cols must be positive integers.")
    if not isinstance(panels, list) or not panels:
        raise ValueError("panels must be a non-empty list.")
    if len(panels) > rows * cols:
        raise ValueError("Panel count exceeds available subplot slots (rows × cols).")
    resolve_geometry(config["layout"])

    required: set[str] = set()
    for panel in panels:
        for key in ("reference_col", "simulation_col"):
            if key not in panel:
                raise ValueError(f"Each panel requires '{key}'.")
            required.add(str(panel[key]))
        if "y_axis" not in panel:
            raise ValueError("Each panel requires 'y_axis'.")
        for key in ("reference_valid", "simulation_valid"):
            rule = panel.get(key)
            if rule:
                required.add(str(rule["column"]))
    missing = required - set(data.columns)
    if missing:
        raise ValueError(f"Input CSV missing columns: {', '.join(sorted(missing))}")


def apply_validity(frame: pd.DataFrame, rule: dict[str, Any] | None) -> pd.DataFrame:
    if not rule:
        return frame
    column = str(rule["column"])
    values = rule.get("values")
    if not isinstance(values, list) or not values:
        raise ValueError("Validity rule 'values' must be a non-empty list.")
    return frame.loc[frame[column].isin(values)]


def panel_series(data: pd.DataFrame, panel: dict[str, Any], column_key: str, valid_key: str) -> pd.DataFrame:
    value_col = str(panel[column_key])
    frame = apply_validity(data, panel.get(valid_key))
    return frame[[PLOT_X, value_col]].dropna().sort_values(PLOT_X)


def plot_series(ax: plt.Axes, frame: pd.DataFrame, value_col: str, *, circular: bool, jump: float, **kwargs: Any) -> None:
    x = frame[PLOT_X].to_numpy()
    y = frame[value_col].to_numpy()
    if circular:
        x, y = break_circular(x, y, jump)
    ax.plot(x, y, **kwargs)


def draw_main(data: pd.DataFrame, config: dict[str, Any], output: Path) -> None:
    configure_fonts()
    data = prepare_x(data, config)
    validate_inputs(data, config)

    style = config["style"]
    layout = config["layout"]
    panels = config["panels"]
    rows = int(layout["rows"])
    cols = int(layout["cols"])

    fig, axes, fixed_geometry, geometry = make_figure_axes(rows, cols, layout)
    axes_flat = axes.ravel()
    x_axis = config["x_axis"]
    range_mode = str(config.get("range_guard", {}).get("mode", "warn"))

    for index, panel in enumerate(panels):
        ax = axes_flat[index]
        reference_col = str(panel["reference_col"])
        simulation_col = str(panel["simulation_col"])
        y_axis = panel["y_axis"]
        circular = bool(panel.get("circular", False))
        circular_jump = float(panel.get("circular_jump_deg", 180.0))

        reference = panel_series(data, panel, "reference_col", "reference_valid")
        simulation = panel_series(data, panel, "simulation_col", "simulation_valid")

        audit_axis_range(reference[reference_col].to_numpy(), y_axis["range"], name=f"panel {index+1} reference", mode=range_mode)
        audit_axis_range(simulation[simulation_col].to_numpy(), y_axis["range"], name=f"panel {index+1} simulation", mode=range_mode)

        plot_series(
            ax, reference, reference_col,
            circular=circular, jump=circular_jump,
            color=style["reference_color"],
            linewidth=style["reference_line_width"],
            linestyle=style["reference_linestyle"],
        )
        plot_series(
            ax, simulation, simulation_col,
            circular=circular, jump=circular_jump,
            color=style["simulation_color"],
            linewidth=style["simulation_line_width"],
            linestyle=style["simulation_linestyle"],
        )

        ax.set_xlim(*x_axis["range"])
        ax.set_xticks(x_axis["ticks"])
        ax.set_ylim(*y_axis["range"])
        ax.set_yticks(y_axis["ticks"])
        ax.set_ylabel(y_axis["label"], fontsize=style["axis_label_fontsize"])
        ax.grid(False)
        ax.tick_params(
            direction="in", top=True, right=True,
            labelsize=style["tick_fontsize"],
            width=style["tick_width"],
            length=style["tick_length"], pad=2,
        )
        for spine in ax.spines.values():
            spine.set_linewidth(style["spine_width"])

        row, _ = divmod(index, cols)
        show_x = row == rows - 1 or not layout.get("hide_x_label_nonlast_row", True)
        ax.set_xlabel(x_axis["label"] if show_x else "", fontsize=style["axis_label_fontsize"])
        if not show_x:
            ax.tick_params(labelbottom=False)

        panel_label = panel.get("panel_label")
        if panel_label:
            label_cfg = panel.get("panel_label_position", {})
            ax.text(
                label_cfg.get("x", 0.03), label_cfg.get("y", 0.97),
                str(panel_label), transform=ax.transAxes,
                ha="left", va="top", fontsize=style["panel_label_fontsize"],
            )

    for ax in axes_flat[len(panels):]:
        ax.set_visible(False)

    legend_cfg = config.get("legend", {})
    add_embedded_legend(
        fig,
        layout,
        geometry,
        labels=legend_cfg.get("labels", ["参考", "模拟"]),
        colors=[style["reference_color"], style["simulation_color"]],
        linestyles=[style["reference_linestyle"], style["simulation_linestyle"]],
        linewidths=[style["reference_line_width"], style["simulation_line_width"]],
        legend_cfg=legend_cfg,
    )

    save_main_figure(fig, output, fixed_geometry)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data = pd.read_csv(args.input)
    config = load_config(args.config)
    draw_main(data, config, args.output)


if __name__ == "__main__":
    main()
