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
from matplotlib import font_manager, rcParams

__version__ = "1.1.0"

MM_PER_INCH = 25.4
STANDARD_GEOMETRY_PROFILE = "academic_mm_v1"
STANDARD_GEOMETRY_MM: dict[str, Any] = {
    "panel_size_mm": [90.0, 65.0],
    "gap_mm": [18.0, 15.0],
    "margin_mm": {"left": 22.0, "right": 6.0, "bottom": 18.0, "top": 6.0},
}

DEFAULT_STYLE: dict[str, Any] = {
    "reference_color": "#8B0000",
    "reference_linestyle": "--",
    "simulation_color": "#000000",
    "simulation_linestyle": "-",
    "line_width": 1.9,
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


def pick_font(candidates: list[str], fallback: str) -> str:
    installed = {font.name for font in font_manager.fontManager.ttflist}
    return next((name for name in candidates if name in installed), fallback)


def configure_fonts() -> None:
    latin = pick_font(
        ["Times New Roman", "Times New Roman PS MT", "Nimbus Roman", "Liberation Serif", "DejaVu Serif"],
        "DejaVu Serif",
    )
    chinese = pick_font(
        ["SimSun", "Songti SC", "STSong", "Noto Serif CJK SC", "Source Han Serif SC", "AR PL SungtiL GB"],
        "DejaVu Serif",
    )
    rcParams.update(
        {
            "font.family": [latin, chinese],
            "axes.unicode_minus": False,
            "svg.fonttype": "none",
            "xtick.direction": "in",
            "ytick.direction": "in",
            "xtick.top": True,
            "ytick.right": True,
        }
    )


def break_circular(x: np.ndarray, y: np.ndarray, jump: float = 180.0) -> tuple[np.ndarray, np.ndarray]:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if x.size == 0:
        return x, y
    if x.size != y.size:
        raise ValueError("Circular x/y arrays must have the same length.")

    breaks = np.zeros(y.size, dtype=bool)
    breaks[1:] = np.isnan(y[1:]) | np.isnan(y[:-1]) | (np.abs(np.diff(y)) > jump)
    if not breaks.any():
        return x, y

    out_size = x.size + int(breaks.sum())
    xo = np.empty(out_size, dtype=float)
    yo = np.empty(out_size, dtype=float)
    src_i = 0
    dst_i = 0
    for is_break in breaks:
        if is_break:
            xo[dst_i] = np.nan
            yo[dst_i] = np.nan
            dst_i += 1
        xo[dst_i] = x[src_i]
        yo[dst_i] = y[src_i]
        src_i += 1
        dst_i += 1
    return xo, yo


def load_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        config = json.load(file)

    missing = REQUIRED_CONFIG_KEYS - config.keys()
    if missing:
        raise ValueError(f"Config missing required keys: {', '.join(sorted(missing))}")

    style = DEFAULT_STYLE.copy()
    style.update(config.get("style", {}))
    config["style"] = style
    return config


def resolve_geometry(layout: dict[str, Any]) -> dict[str, Any] | None:
    geometry = layout.get("geometry")
    if geometry is None:
        return None
    if not isinstance(geometry, dict):
        raise ValueError("layout.geometry must be an object.")

    profile = str(geometry.get("profile", STANDARD_GEOMETRY_PROFILE))
    if profile != STANDARD_GEOMETRY_PROFILE:
        raise ValueError(f"Unsupported geometry profile '{profile}'.")

    panel_size = geometry.get("panel_size_mm", STANDARD_GEOMETRY_MM["panel_size_mm"])
    gap = geometry.get("gap_mm", STANDARD_GEOMETRY_MM["gap_mm"])
    if not isinstance(panel_size, list) or len(panel_size) != 2:
        raise ValueError("layout.geometry.panel_size_mm must be [width, height].")
    if not isinstance(gap, list) or len(gap) != 2:
        raise ValueError("layout.geometry.gap_mm must be [x, y].")

    margin = dict(STANDARD_GEOMETRY_MM["margin_mm"])
    margin_override = geometry.get("margin_mm", {})
    if not isinstance(margin_override, dict):
        raise ValueError("layout.geometry.margin_mm must be an object.")
    margin.update(margin_override)

    panel_w, panel_h = map(float, panel_size)
    gap_x, gap_y = map(float, gap)
    margin = {key: float(margin[key]) for key in ("left", "right", "bottom", "top")}
    if panel_w <= 0 or panel_h <= 0:
        raise ValueError("Panel width and height must be positive.")
    if gap_x < 0 or gap_y < 0 or any(value < 0 for value in margin.values()):
        raise ValueError("Gaps and margins must be non-negative.")

    return {
        "profile": profile,
        "panel_size_mm": [panel_w, panel_h],
        "gap_mm": [gap_x, gap_y],
        "margin_mm": margin,
    }


def make_figure_axes(rows: int, cols: int, layout: dict[str, Any]) -> tuple[plt.Figure, np.ndarray, bool]:
    geometry = resolve_geometry(layout)
    if geometry is None:
        figsize = layout.get("figsize_in", [7.2, 5.6])
        fig, axes = plt.subplots(rows, cols, figsize=figsize, squeeze=False)
        fig.subplots_adjust(**layout.get("subplot_adjust", {}))
        return fig, axes, False

    panel_w, panel_h = geometry["panel_size_mm"]
    gap_x, gap_y = geometry["gap_mm"]
    margin = geometry["margin_mm"]
    canvas_w = margin["left"] + cols * panel_w + (cols - 1) * gap_x + margin["right"]
    canvas_h = margin["bottom"] + rows * panel_h + (rows - 1) * gap_y + margin["top"]

    fig = plt.figure(figsize=(canvas_w / MM_PER_INCH, canvas_h / MM_PER_INCH))
    axes = np.empty((rows, cols), dtype=object)
    for row in range(rows):
        for col in range(cols):
            left_mm = margin["left"] + col * (panel_w + gap_x)
            bottom_mm = margin["bottom"] + (rows - 1 - row) * (panel_h + gap_y)
            axes[row, col] = fig.add_axes(
                [left_mm / canvas_w, bottom_mm / canvas_h, panel_w / canvas_w, panel_h / canvas_h]
            )
    return fig, axes, True


def save_main_figure(fig: plt.Figure, output: Path, fixed_geometry: bool) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    if fixed_geometry:
        fig.savefig(output, format="svg", facecolor="white")
    else:
        fig.savefig(output, format="svg", facecolor="white", bbox_inches="tight", pad_inches=0.03)
    plt.close(fig)


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

    fig, axes, fixed_geometry = make_figure_axes(rows, cols, layout)
    axes_flat = axes.ravel()
    x_axis = config["x_axis"]

    for index, panel in enumerate(panels):
        ax = axes_flat[index]
        reference_col = str(panel["reference_col"])
        simulation_col = str(panel["simulation_col"])
        y_axis = panel["y_axis"]
        circular = bool(panel.get("circular", False))
        circular_jump = float(panel.get("circular_jump_deg", 180.0))

        reference = panel_series(data, panel, "reference_col", "reference_valid")
        simulation = panel_series(data, panel, "simulation_col", "simulation_valid")

        plot_series(
            ax,
            reference,
            reference_col,
            circular=circular,
            jump=circular_jump,
            color=style["reference_color"],
            linewidth=style["line_width"],
            linestyle=style["reference_linestyle"],
        )
        plot_series(
            ax,
            simulation,
            simulation_col,
            circular=circular,
            jump=circular_jump,
            color=style["simulation_color"],
            linewidth=style["line_width"],
            linestyle=style["simulation_linestyle"],
        )

        ax.set_xlim(*x_axis["range"])
        ax.set_xticks(x_axis["ticks"])
        ax.set_ylim(*y_axis["range"])
        ax.set_yticks(y_axis["ticks"])
        ax.set_ylabel(y_axis["label"], fontsize=style["axis_label_fontsize"])
        ax.grid(False)
        ax.tick_params(
            direction="in",
            top=True,
            right=True,
            labelsize=style["tick_fontsize"],
            width=style["tick_width"],
            length=style["tick_length"],
            pad=2,
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
                label_cfg.get("x", 0.03),
                label_cfg.get("y", 0.97),
                str(panel_label),
                transform=ax.transAxes,
                ha="left",
                va="top",
                fontsize=style["panel_label_fontsize"],
            )

    for ax in axes_flat[len(panels) :]:
        ax.set_visible(False)

    save_main_figure(fig, output, fixed_geometry)


def draw_legend(config: dict[str, Any], output: Path) -> None:
    configure_fonts()
    style = config["style"]
    legend = config.get("legend", {})
    fig = plt.figure(figsize=legend.get("figsize_in", [3.2, 0.9]))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.axis("off")

    handles = [
        plt.Line2D([0], [0], color=style["reference_color"], linewidth=legend.get("line_width", 2.0), linestyle=style["reference_linestyle"]),
        plt.Line2D([0], [0], color=style["simulation_color"], linewidth=legend.get("line_width", 2.0), linestyle=style["simulation_linestyle"]),
    ]
    ax.legend(
        handles,
        legend.get("labels", ["参考", "模拟"]),
        loc="center",
        ncol=2,
        frameon=False,
        fontsize=legend.get("fontsize", 14),
        handlelength=legend.get("handlelength", 4.2),
        handletextpad=legend.get("handletextpad", 0.6),
        columnspacing=legend.get("columnspacing", 2.0),
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, format="svg", facecolor="white", bbox_inches="tight", pad_inches=0.03)
    plt.close(fig)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Prepared CSV with panel reference/simulation columns.")
    parser.add_argument("--config", type=Path, required=True, help="JSON plot configuration.")
    parser.add_argument("--output", type=Path, required=True, help="Main SVG output path.")
    parser.add_argument("--legend-output", type=Path, default=None, help="Optional standalone legend SVG path.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data = pd.read_csv(args.input)
    config = load_config(args.config)
    draw_main(data, config, args.output)
    if args.legend_output is not None:
        draw_legend(config, args.legend_output)


if __name__ == "__main__":
    main()
