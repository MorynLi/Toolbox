#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared layout, legend, axis-audit, font, and circular-series utilities."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import warnings

import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager, rcParams

MM_PER_INCH = 25.4
STANDARD_GEOMETRY_PROFILE = "academic_mm_v1"
STANDARD_GEOMETRY_MM: dict[str, Any] = {
    "panel_size_mm": [90.0, 65.0],
    "gap_mm": [18.0, 15.0],
    "margin_mm": {"left": 22.0, "right": 6.0, "bottom": 18.0, "top": 10.0},
}


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

    xo: list[float] = []
    yo: list[float] = []
    for i in range(y.size):
        if breaks[i]:
            xo.append(np.nan)
            yo.append(np.nan)
        xo.append(float(x[i]))
        yo.append(float(y[i]))
    return np.asarray(xo), np.asarray(yo)


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

    canvas_w = margin["left"] + int(layout["cols"]) * panel_w + (int(layout["cols"]) - 1) * gap_x + margin["right"]
    canvas_h = margin["bottom"] + int(layout["rows"]) * panel_h + (int(layout["rows"]) - 1) * gap_y + margin["top"]
    return {
        "profile": profile,
        "panel_size_mm": [panel_w, panel_h],
        "gap_mm": [gap_x, gap_y],
        "margin_mm": margin,
        "canvas_size_mm": [canvas_w, canvas_h],
    }


def make_figure_axes(rows: int, cols: int, layout: dict[str, Any]) -> tuple[plt.Figure, np.ndarray, bool, dict[str, Any] | None]:
    geometry = resolve_geometry(layout)
    if geometry is None:
        figsize = layout.get("figsize_in", [10.6, 7.55])
        fig, axes = plt.subplots(rows, cols, figsize=figsize, squeeze=False)
        fig.subplots_adjust(**layout.get("subplot_adjust", {}))
        return fig, axes, False, None

    panel_w, panel_h = geometry["panel_size_mm"]
    gap_x, gap_y = geometry["gap_mm"]
    margin = geometry["margin_mm"]
    canvas_w, canvas_h = geometry["canvas_size_mm"]

    fig = plt.figure(figsize=(canvas_w / MM_PER_INCH, canvas_h / MM_PER_INCH))
    axes = np.empty((rows, cols), dtype=object)
    for row in range(rows):
        for col in range(cols):
            left_mm = margin["left"] + col * (panel_w + gap_x)
            bottom_mm = margin["bottom"] + (rows - 1 - row) * (panel_h + gap_y)
            axes[row, col] = fig.add_axes(
                [left_mm / canvas_w, bottom_mm / canvas_h, panel_w / canvas_w, panel_h / canvas_h]
            )
    return fig, axes, True, geometry


def save_main_figure(fig: plt.Figure, output: Path, fixed_geometry: bool) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    if fixed_geometry:
        fig.savefig(output, format="svg", facecolor="white")
    else:
        fig.savefig(output, format="svg", facecolor="white", bbox_inches="tight", pad_inches=0.03)
    plt.close(fig)


def add_embedded_legend(
    fig: plt.Figure,
    layout: dict[str, Any],
    geometry: dict[str, Any] | None,
    *,
    labels: list[str],
    colors: list[str],
    linestyles: list[str],
    linewidths: list[float],
    legend_cfg: dict[str, Any] | None = None,
) -> None:
    """Put one legend above the first row and centered over the panel block.

    One-column layout: centered over the first panel.
    Two-or-more-column layout: centered over the whole first-row panel block.
    """
    legend_cfg = legend_cfg or {}
    if not legend_cfg.get("enabled", True):
        return

    handles = [
        plt.Line2D([0], [0], color=color, linewidth=lw, linestyle=ls)
        for color, lw, ls in zip(colors, linewidths, linestyles)
    ]

    if geometry is None:
        anchor = legend_cfg.get("bbox_to_anchor", [0.5, 1.01])
        fig.legend(
            handles,
            labels,
            loc=legend_cfg.get("loc", "lower center"),
            bbox_to_anchor=anchor,
            ncol=legend_cfg.get("ncol", len(labels)),
            frameon=False,
            fontsize=legend_cfg.get("fontsize", 14),
            handlelength=legend_cfg.get("handlelength", 3.2),
            handletextpad=legend_cfg.get("handletextpad", 0.6),
            columnspacing=legend_cfg.get("columnspacing", 1.8),
            borderaxespad=0.0,
        )
        return

    panel_w, _ = geometry["panel_size_mm"]
    gap_x, _ = geometry["gap_mm"]
    margin = geometry["margin_mm"]
    canvas_w, canvas_h = geometry["canvas_size_mm"]
    cols = int(layout["cols"])

    panel_block_w = cols * panel_w + (cols - 1) * gap_x
    center_x_mm = margin["left"] + panel_block_w / 2.0
    default_y_mm = canvas_h - max(2.0, min(5.0, margin["top"] / 2.0))

    anchor_x_mm = float(legend_cfg.get("anchor_x_mm", center_x_mm))
    anchor_y_mm = float(legend_cfg.get("anchor_y_mm", default_y_mm))
    anchor_x_mm += float(legend_cfg.get("shift_x_mm", 0.0))
    anchor_y_mm += float(legend_cfg.get("shift_y_mm", 0.0))

    fig.legend(
        handles,
        labels,
        loc="center",
        bbox_to_anchor=(anchor_x_mm / canvas_w, anchor_y_mm / canvas_h),
        ncol=legend_cfg.get("ncol", len(labels)),
        frameon=False,
        fontsize=legend_cfg.get("fontsize", 14),
        handlelength=legend_cfg.get("handlelength", 3.2),
        handletextpad=legend_cfg.get("handletextpad", 0.6),
        columnspacing=legend_cfg.get("columnspacing", 1.8),
        borderaxespad=0.0,
    )


def audit_axis_range(
    values: np.ndarray,
    axis_range: list[float],
    *,
    name: str,
    mode: str = "warn",
) -> None:
    finite = np.asarray(values, dtype=float)
    finite = finite[np.isfinite(finite)]
    if finite.size == 0:
        return

    data_min = float(finite.min())
    data_max = float(finite.max())
    axis_min = float(axis_range[0])
    axis_max = float(axis_range[1])
    if data_min >= axis_min and data_max <= axis_max:
        return

    message = (
        f"{name}: data range [{data_min:.6g}, {data_max:.6g}] exceeds "
        f"axis range [{axis_min:.6g}, {axis_max:.6g}]."
    )
    mode = str(mode).lower()
    if mode == "error":
        raise ValueError(message)
    if mode == "warn":
        warnings.warn(message, RuntimeWarning, stacklevel=2)
    elif mode not in {"off", "none"}:
        raise ValueError("range_guard.mode must be one of: error, warn, off.")
