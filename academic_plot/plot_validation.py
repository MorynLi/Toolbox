#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate reusable multi-station reference-vs-simulation validation plots as SVG."""

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

DEFAULT_STYLE: dict[str, Any] = {
    "observed_color": "#8B0000",
    "observed_linestyle": "--",
    "simulated_color": "#000000",
    "simulated_linestyle": "-",
    "line_width": 1.9,
    "spine_width": 1.15,
    "tick_width": 1.0,
    "tick_length": 4.0,
    "tick_fontsize": 12,
    "axis_label_fontsize": 14,
    "station_fontsize": 13,
}

REQUIRED_CONFIG_KEYS = {"stations", "layout", "x_axis", "y_axis"}


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


def series_columns(config: dict[str, Any]) -> tuple[str, str]:
    """Resolve new reference/simulation names while preserving legacy observed/simulated configs."""
    reference_col = config.get("reference_col", config.get("observed_col", "observed"))
    simulation_col = config.get("simulation_col", config.get("simulated_col", "simulated"))
    return str(reference_col), str(simulation_col)


def validity_columns(config: dict[str, Any]) -> set[str]:
    columns: set[str] = set()
    for key in ("reference_valid", "simulation_valid"):
        rule = config.get(key)
        if rule:
            columns.add(str(rule["column"]))
    return columns


def validate_inputs(data: pd.DataFrame, config: dict[str, Any]) -> None:
    reference_col, simulation_col = series_columns(config)
    columns = {
        str(config.get("station_col", "station")),
        str(config.get("x_col", "time_h")),
        reference_col,
        simulation_col,
        *validity_columns(config),
    }
    missing = columns - set(data.columns)
    if missing:
        raise ValueError(f"Input CSV missing columns: {', '.join(sorted(missing))}")

    rows = int(config["layout"]["rows"])
    cols = int(config["layout"]["cols"])
    if rows <= 0 or cols <= 0:
        raise ValueError("layout.rows and layout.cols must be positive integers.")
    if len(config["stations"]) > rows * cols:
        raise ValueError("Station count exceeds available subplot slots (rows × cols).")


def apply_validity(frame: pd.DataFrame, rule: dict[str, Any] | None) -> pd.DataFrame:
    if not rule:
        return frame
    column = str(rule["column"])
    values = rule.get("values")
    if values is None:
        raise ValueError("Validity rule requires a non-empty 'values' list.")
    if not isinstance(values, list) or not values:
        raise ValueError("Validity rule 'values' must be a non-empty list.")
    return frame.loc[frame[column].isin(values)]


def plot_series(ax: plt.Axes, x: np.ndarray, y: np.ndarray, *, circular: bool, jump: float, **kwargs: Any) -> None:
    if circular:
        x, y = break_circular(x, y, jump)
    ax.plot(x, y, **kwargs)


def draw_main(data: pd.DataFrame, config: dict[str, Any], output: Path) -> None:
    configure_fonts()
    validate_inputs(data, config)

    style = config["style"]
    stations = config["stations"]
    rows = int(config["layout"]["rows"])
    cols = int(config["layout"]["cols"])
    figsize = config["layout"].get("figsize_in", [10.6, 7.55])

    fig, axes = plt.subplots(rows, cols, figsize=figsize, squeeze=False)
    axes_flat = axes.ravel()
    fig.subplots_adjust(**config["layout"].get("subplot_adjust", {}))

    station_col = str(config.get("station_col", "station"))
    x_col = str(config.get("x_col", "time_h"))
    reference_col, simulation_col = series_columns(config)
    x_axis = config["x_axis"]
    y_axis = config["y_axis"]
    circular = bool(config.get("circular", False))
    circular_jump = float(config.get("circular_jump_deg", 180.0))

    for index, station in enumerate(stations):
        ax = axes_flat[index]
        station_data = data.loc[data[station_col].astype(str).eq(str(station))].sort_values(x_col)

        reference = apply_validity(station_data, config.get("reference_valid"))[[x_col, reference_col]].dropna()
        simulation = apply_validity(station_data, config.get("simulation_valid"))[[x_col, simulation_col]].dropna()

        plot_series(
            ax,
            reference[x_col].to_numpy(),
            reference[reference_col].to_numpy(),
            circular=circular,
            jump=circular_jump,
            color=style["observed_color"],
            linewidth=style["line_width"],
            linestyle=style["observed_linestyle"],
        )
        plot_series(
            ax,
            simulation[x_col].to_numpy(),
            simulation[simulation_col].to_numpy(),
            circular=circular,
            jump=circular_jump,
            color=style["simulated_color"],
            linewidth=style["line_width"],
            linestyle=style["simulated_linestyle"],
        )

        ax.set_xlim(*x_axis["range"])
        ax.set_xticks(x_axis["ticks"])
        ax.set_ylim(*y_axis["range"])
        ax.set_yticks(y_axis["ticks"])
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

        row, col = divmod(index, cols)
        show_y = col == 0 or not config["layout"].get("hide_y_label_nonfirst_col", True)
        show_x = row == rows - 1 or not config["layout"].get("hide_x_label_nonlast_row", True)
        ax.set_ylabel(y_axis["label"] if show_y else "", fontsize=style["axis_label_fontsize"])
        ax.set_xlabel(x_axis["label"] if show_x else "", fontsize=style["axis_label_fontsize"])

        label_cfg = config.get("station_label", {})
        if label_cfg.get("enabled", True):
            ax.text(
                label_cfg.get("x", 0.03),
                label_cfg.get("y", 0.97),
                str(station),
                transform=ax.transAxes,
                ha="left",
                va="top",
                fontsize=style["station_fontsize"],
            )

    for ax in axes_flat[len(stations) :]:
        ax.set_visible(False)

    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, format="svg", facecolor="white", bbox_inches="tight", pad_inches=0.03)
    plt.close(fig)


def draw_legend(config: dict[str, Any], output: Path) -> None:
    configure_fonts()
    style = config["style"]
    legend = config.get("legend", {})
    fig = plt.figure(figsize=legend.get("figsize_in", [3.2, 0.9]))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.axis("off")

    handles = [
        plt.Line2D([0], [0], color=style["observed_color"], linewidth=legend.get("line_width", 2.0), linestyle=style["observed_linestyle"]),
        plt.Line2D([0], [0], color=style["simulated_color"], linewidth=legend.get("line_width", 2.0), linestyle=style["simulated_linestyle"]),
    ]
    ax.legend(
        handles,
        legend.get("labels", ["实测", "模拟"]),
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
    parser.add_argument("--input", type=Path, required=True, help="Prepared CSV with reference/simulation columns.")
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
