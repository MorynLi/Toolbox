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
    add_bottom_time_band,
    add_embedded_legend,
    audit_axis_range,
    break_circular,
    clip_and_rebase_xy,
    configure_fonts,
    make_figure_axes,
    resolve_geometry,
    resolve_x_window,
    x_axis_for_window,
    x_tick_labels_visible,
)
from style import (
    axes_box_mm,
    draw_label,
    export_figure,
    label_text,
    load_profile,
    panel_letter,
    setup_fonts,
    style_defaults,
    write_caption_snippet,
)

__version__ = "1.5.0"

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

    profile = load_profile(config["profile"]) if config.get("profile") else None
    config["_profile"] = profile
    style = DEFAULT_STYLE.copy()
    if profile is not None:
        style.update(style_defaults(profile))
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
    resolve_geometry(config["layout"], config.get("_profile"))


def apply_validity(frame: pd.DataFrame, rule: dict[str, Any] | None) -> pd.DataFrame:
    if not rule:
        return frame
    column = str(rule["column"])
    values = rule.get("values")
    if not isinstance(values, list) or not values:
        raise ValueError("Validity rule 'values' must be a non-empty list.")
    return frame.loc[frame[column].isin(values)]


def plot_series(ax: plt.Axes, x: np.ndarray, y: np.ndarray, *, circular: bool, jump: float, **kwargs: Any) -> None:
    if circular:
        x, y = break_circular(x, y, jump)
    ax.plot(x, y, **kwargs)


def prepare_station_series(data: pd.DataFrame, config: dict[str, Any]) -> dict[str, tuple[pd.DataFrame, pd.DataFrame]]:
    station_col = str(config.get("station_col", "station"))
    reference_x_col, simulation_x_col = series_x_columns(config)
    reference_col, simulation_col = series_columns(config)
    prepared: dict[str, tuple[pd.DataFrame, pd.DataFrame]] = {}
    for station in config["stations"]:
        station_data = data.loc[data[station_col].astype(str).eq(str(station))]
        reference = apply_validity(station_data, config.get("reference_valid"))[
            [reference_x_col, reference_col]
        ].dropna().sort_values(reference_x_col)
        simulation = apply_validity(station_data, config.get("simulation_valid"))[
            [simulation_x_col, simulation_col]
        ].dropna().sort_values(simulation_x_col)
        prepared[str(station)] = (reference, simulation)
    return prepared


def apply_profile_axis_defaults(x_axis: dict[str, Any], profile: dict[str, Any], style: dict[str, Any]) -> dict[str, Any]:
    x_axis = dict(x_axis)
    x_axis["bottom_band"] = {"y_mm": profile["geometry_mm"]["bottom_band_y"], **(x_axis.get("bottom_band") or {})}
    if x_axis.get("origin_timestamp"):
        x_axis["origin_timestamp"] = {"fontsize": style["annotation_fontsize"], **x_axis["origin_timestamp"]}
    return x_axis


def draw_main(
    data: pd.DataFrame,
    config: dict[str, Any],
    output: Path,
    *,
    draft: bool = False,
    font_dir: Path | None = None,
) -> list[Path]:
    profile = config.get("_profile")
    if profile is None:
        configure_fonts()
    else:
        setup_fonts(profile, draft=draft, font_dir=font_dir)
    validate_inputs(data, config)

    style = config["style"]
    stations = [str(v) for v in config["stations"]]
    layout = config["layout"]
    rows = int(layout["rows"])
    cols = int(layout["cols"])
    reference_x_col, simulation_x_col = series_x_columns(config)
    reference_col, simulation_col = series_columns(config)

    prepared = prepare_station_series(data, config)
    series_x: list[np.ndarray] = []
    for station in stations:
        reference, simulation = prepared[station]
        series_x.extend([reference[reference_x_col].to_numpy(), simulation[simulation_x_col].to_numpy()])

    window_cfg = config.get("x_window")
    window = resolve_x_window(series_x, window_cfg)
    if window is not None:
        start, end, rebase = window
        for station in stations:
            reference, simulation = prepared[station]
            prepared[station] = (
                clip_and_rebase_xy(reference, reference_x_col, start, end, rebase),
                clip_and_rebase_xy(simulation, simulation_x_col, start, end, rebase),
            )

    x_axis = x_axis_for_window(config["x_axis"], window, window_cfg)
    if profile is not None:
        x_axis = apply_profile_axis_defaults(x_axis, profile, style)
    x_axis["label"] = label_text(x_axis.get("label", ""), profile)
    y_axis = config["y_axis"]
    y_label = label_text(y_axis.get("label", ""), profile)
    circular = bool(config.get("circular", False))
    circular_jump = float(config.get("circular_jump_deg", 180.0))
    range_mode = str(config.get("range_guard", {}).get("mode", "warn"))

    fig, axes, fixed_geometry, geometry = make_figure_axes(rows, cols, layout, profile)
    hide_y_ticks = layout.get("hide_y_ticklabels_nonfirst_col", profile is not None)
    axes_flat = axes.ravel()

    for index, station in enumerate(stations):
        ax = axes_flat[index]
        reference, simulation = prepared[station]

        audit_axis_range(reference[reference_col].to_numpy(), y_axis["range"], name=f"{station} reference", mode=range_mode)
        audit_axis_range(simulation[simulation_col].to_numpy(), y_axis["range"], name=f"{station} simulation", mode=range_mode)

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
        show_y = col == 0 or not layout.get("hide_y_label_nonfirst_col", True)
        if profile is not None and fixed_geometry:
            ax.set_ylabel("")
            if show_y:
                left, bottom, _, height = axes_box_mm(fig, ax)
                offset = profile["geometry_mm"]["ylabel_offset"]
                draw_label(fig, y_label, left - offset, bottom + height / 2, fontsize=style["axis_label_fontsize"], rotation=90)
        else:
            ax.set_ylabel(y_label if show_y else "", fontsize=style["axis_label_fontsize"])
        ax.set_xlabel("")
        ax.tick_params(labelbottom=x_tick_labels_visible(row, rows, x_axis))
        if col > 0 and hide_y_ticks:
            ax.tick_params(labelleft=False)

        label_cfg = config.get("station_label", {})
        if label_cfg.get("enabled", True):
            text = station
            if label_cfg.get("letters", profile is not None):
                text = f"{panel_letter(index, profile)} {station}"
            ax.text(
                label_cfg.get("x", 0.03),
                label_cfg.get("y", 0.97),
                text,
                transform=ax.transAxes,
                ha="left",
                va="top",
                fontsize=style["station_fontsize"],
            )

    for ax in axes_flat[len(stations):]:
        ax.set_visible(False)

    add_bottom_time_band(fig, axes, layout, geometry, x_axis, axis_label_fontsize=style["axis_label_fontsize"])

    legend_cfg = dict(config.get("legend", {}))
    if profile is not None:
        legend_cfg.setdefault("fontsize", style["legend_fontsize"])
        legend_cfg.setdefault("handlelength", 2.6)
    add_embedded_legend(
        fig,
        layout,
        geometry,
        labels=legend_cfg.get("labels", ["实测", "模拟"]),
        colors=[style["observed_color"], style["simulated_color"]],
        linestyles=[style["observed_linestyle"], style["simulated_linestyle"]],
        linewidths=[style["observed_line_width"], style["simulated_line_width"]],
        legend_cfg=legend_cfg,
    )

    width_mm = fig.get_figwidth() * 25.4
    written = export_figure(fig, output, profile=profile, fixed_geometry=fixed_geometry, draft=draft, qc=config.get("qc"))
    snippet = write_caption_snippet(output, config.get("caption"), width_mm=width_mm, profile=profile)
    return written + ([snippet] if snippet else [])


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
    ax.legend(handles, legend.get("labels", ["实测", "模拟"]), loc="center", ncol=2, frameon=False, fontsize=legend.get("fontsize", 14))
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, format="svg", facecolor="white", bbox_inches="tight", pad_inches=0.03)
    plt.close(fig)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Prepared CSV with reference/simulation columns.")
    parser.add_argument("--config", type=Path, required=True, help="JSON plot configuration.")
    parser.add_argument("--output", type=Path, required=True, help="Main output path; with a profile, every profile format is written next to it.")
    parser.add_argument("--draft", action="store_true", help="Use metric-compatible substitute fonts and stamp DRAFT.")
    parser.add_argument("--font-dir", type=Path, default=None, help="Folder with the profile font files (or set ACADEMIC_PLOT_FONT_DIR).")
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
    for path in draw_main(data, config, args.output, draft=args.draft, font_dir=args.font_dir):
        print(path)
    if args.legend_output is not None:
        draw_legacy_legend(config, args.legend_output)


if __name__ == "__main__":
    main()
