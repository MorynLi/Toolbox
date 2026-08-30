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

from plot_common import (
    add_embedded_legend,
    audit_axis_range,
    break_circular,
    configure_fonts,
    make_figure_axes,
    resolve_geometry,
    save_main_figure,
)

__version__ = "1.3.0"

DEFAULT_STYLE: dict[str, Any] = {
    "observed_color": "#8B0000",
    "observed_linestyle": "--",
    "simulated_color": "#000000",
    "simulated_linestyle": "-",
    "observed_line_width": 1.6,
    "simulated_line_width": 1.8,
    "spine_width": 1.15,
    "tick_width": 1.0,
    "tick_length": 4.0,
    "tick_fontsize": 12,
    "axis_label_fontsize": 14,
    "station_fontsize": 13,
}

REQUIRED_CONFIG_KEYS = {"stations", "layout", "x_axis", "y_axis"}


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
        style["observed_line_width"] = legacy_width
        style["simulated_line_width"] = legacy_width
    config["style"] = style
    return config


def series_columns(config: dict[str, Any]) -> tuple[str, str]:
    reference_col = config.get("reference_col", config.get("observed_col", "observed"))
    simulation_col = config.get("simulation_col", config.get("simulated_col", "simulated"))
    return str(reference_col), str(simulation_col)


def series_x_columns(config: dict[str, Any]) -> tuple[str, str]:
    default_x = str(config.get("x_col", "time_h"))
    return (
        str(config.get("reference_x_col", default_x)),
        str(config.get("simulation_x_col", default_x)),
    )


def validity_columns(config: dict[str, Any]) -> set[str]:
    columns: set[str] = set()
    for key in ("reference_valid", "simulation_valid"):
        rule = config.get(key)
        if rule:
            columns.add(str(rule["column"]))
    return columns


def validate_inputs(data: pd.DataFrame, config: dict[str, Any]) -> None:
    reference_col, simulation_col = series_columns(config)
    reference_x_col, simulation_x_col = series_x_columns(config)
    columns = {
        str(config.get("station_col", "station")),
        reference_x_col,
        simulation_x_col,
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
    resolve_geometry(config["layout"])


def apply_validity(frame: pd.DataFrame, rule: dict[str, Any] | None) -> pd.DataFrame:
    if not rule:
        return frame
    column = str(rule["column"])
    values = rule.get("values")
    if not isinstance(values, list) or not values:
        raise ValueError("Validity rule 'values' must be a non-empty list.")
    return frame.loc[frame[column].isin(values)]


def plot_series(
    ax: plt.Axes,
    x: np.ndarray,
    y: np.ndarray,
    *,
    circular: bool,
    jump: float,
    **kwargs: Any,
) -> None:
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

    fig, axes, fixed_geometry, geometry = make_figure_axes(rows, cols, config["layout"])
    axes_flat = axes.ravel()

    station_col = str(config.get("station_col", "station"))
    reference_x_col, simulation_x_col = series_x_columns(config)
    reference_col, simulation_col = series_columns(config)
    x_axis = config["x_axis"]
    y_axis = config["y_axis"]
    circular = bool(config.get("circular", False))
    circular_jump = float(config.get("circular_jump_deg", 180.0))
    range_guard = config.get("range_guard", {})
    range_mode = str(range_guard.get("mode", "warn"))

    for index, station in enumerate(stations):
        ax = axes_flat[index]
        station_data = data.loc[data[station_col].astype(str).eq(str(station))]

        reference = apply_validity(station_data, config.get("reference_valid"))[
            [reference_x_col, reference_col]
        ].dropna().sort_values(reference_x_col)

        simulation = apply_validity(station_data, config.get("simulation_valid"))[
            [simulation_x_col, simulation_col]
        ].dropna().sort_values(simulation_x_col)

        audit_axis_range(
            reference[reference_col].to_numpy(),
            y_axis["range"],
            name=f"{station} reference",
            mode=range_mode,
        )
        audit_axis_range(
            simulation[simulation_col].to_numpy(),
            y_axis["range"],
            name=f"{station} simulation",
            mode=range_mode,
        )

        plot_series(
            ax,
            reference[reference_x_col].to_numpy(),
            reference[reference_col].to_numpy(),
            circular=circular,
            jump=circular_jump,
            color=style["observed_color"],
            linewidth=style["observed_line_width"],
            linestyle=style["observed_linestyle"],
        )
        plot_series(
            ax,
            simulation[simulation_x_col].to_numpy(),
            simulation[simulation_col].to_numpy(),
            circular=circular,
            jump=circular_jump,
            color=style["simulated_color"],
            linewidth=style["simulated_line_width"],
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
        if not show_x:
            ax.tick_params(labelbottom=False)

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

    for ax in axes_flat[len(stations):]:
        ax.set_visible(False)

    legend_cfg = config.get("legend", {})
    add_embedded_legend(
        fig,
        config["layout"],
        geometry,
        labels=legend_cfg.get("labels", ["实测", "模拟"]),
        colors=[style["observed_color"], style["simulated_color"]],
        linestyles=[style["observed_linestyle"], style["simulated_linestyle"]],
        linewidths=[style["observed_line_width"], style["simulated_line_width"]],
        legend_cfg=legend_cfg,
    )

    save_main_figure(fig, output, fixed_geometry)


def draw_legacy_legend(config: dict[str, Any], output: Path) -> None:
    """Legacy helper. New figures should use the embedded legend in draw_main()."""
    configure_fonts()
    style = config["style"]
    legend = config.get("legend", {})
    fig = plt.figure(figsize=legend.get("figsize_in", [3.2, 0.9]))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.axis("off")
    handles = [
        plt.Line2D([0], [0], color=style["observed_color"], linewidth=style["observed_line_width"], linestyle=style["observed_linestyle"]),
        plt.Line2D([0], [0], color=style["simulated_color"], linewidth=style["simulated_line_width"], linestyle=style["simulated_linestyle"]),
    ]
    ax.legend(
        handles,
        legend.get("labels", ["实测", "模拟"]),
        loc="center",
        ncol=2,
        frameon=False,
        fontsize=legend.get("fontsize", 14),
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, format="svg", facecolor="white", bbox_inches="tight", pad_inches=0.03)
    plt.close(fig)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Prepared CSV with reference/simulation columns.")
    parser.add_argument("--config", type=Path, required=True, help="JSON plot configuration.")
    parser.add_argument("--output", type=Path, required=True, help="Main SVG output path.")
    parser.add_argument(
        "--legend-output",
        type=Path,
        default=None,
        help="Deprecated: optional standalone legend SVG for legacy workflows. Main SVG always embeds the legend.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data = pd.read_csv(args.input)
    config = load_config(args.config)
    draw_main(data, config, args.output)
    if args.legend_output is not None:
        draw_legacy_legend(config, args.legend_output)


if __name__ == "__main__":
    main()
