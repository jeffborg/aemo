from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from html import escape
from typing import Iterable


@dataclass(frozen=True)
class Series:
    label: str
    color: str
    points: list[float | None]


def _fmt(value: float) -> str:
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _legend_width(label: str) -> int:
    return max(88, 32 + (len(label) * 7))


def _six_hour_tick_label(value: datetime) -> str:
    return value.strftime("%H")


def _day_tick_label(value: datetime) -> str:
    return value.strftime("%a %d %b")


def line_chart(
    title: str,
    x_values: list[datetime],
    series_list: Iterable[Series],
    width: int = 960,
    height: int = 360,
) -> str:
    series = list(series_list)
    all_values = [point for item in series for point in item.points if point is not None]
    if not all_values or len(x_values) < 2:
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">'
            f'<text x="24" y="36" font-size="18">{escape(title)}</text>'
            '<text x="24" y="72" font-size="14">No data available</text>'
            "</svg>"
        )

    left = 70
    right = 20
    minimum = min(all_values)
    maximum = max(all_values)
    if minimum == maximum:
        minimum -= 1.0
        maximum += 1.0

    title_y = 24
    legend_start_y = 46
    legend_row_height = 18
    legend = []
    legend_x = left
    legend_y = legend_start_y
    legend_rows = 1
    for item in series:
        item_width = _legend_width(item.label)
        if legend_x > left and legend_x + item_width > width - right:
            legend_rows += 1
            legend_x = left
            legend_y += legend_row_height
        legend.append(f'<rect x="{legend_x}" y="{legend_y-10}" width="10" height="10" fill="{item.color}" />')
        legend.append(
            f'<text x="{legend_x+16}" y="{legend_y}" font-size="12" fill="#111827">{escape(item.label)}</text>'
        )
        legend_x += item_width

    top = legend_start_y + ((legend_rows - 1) * legend_row_height) + 24
    bottom = 72
    plot_width = width - left - right
    plot_height = height - top - bottom

    def x_pos(index: int) -> float:
        return left + (plot_width * index / max(1, len(x_values) - 1))

    def y_pos(value: float) -> float:
        return top + plot_height - ((value - minimum) / (maximum - minimum) * plot_height)

    def polyline(points: list[float | None]) -> list[str]:
        segments: list[str] = []
        current: list[str] = []
        for idx, point in enumerate(points):
            if point is None:
                if len(current) >= 2:
                    segments.append(" ".join(current))
                current = []
                continue
            current.append(f"{x_pos(idx):.1f},{y_pos(point):.1f}")
        if len(current) >= 2:
            segments.append(" ".join(current))
        return segments

    grid_lines = []
    y_axis_labels = []
    for step in range(5):
        value = minimum + ((maximum - minimum) * step / 4)
        y = y_pos(value)
        grid_lines.append(f'<line x1="{left}" y1="{y:.1f}" x2="{width-right}" y2="{y:.1f}" stroke="#e5e7eb" />')
        y_axis_labels.append(
            f'<text x="{left-10}" y="{y+4:.1f}" text-anchor="end" font-size="11" fill="#4b5563">{escape(_fmt(value))}</text>'
        )

    six_hour_tick_lines = []
    six_hour_axis_ticks = []
    six_hour_labels = []
    day_dividers = []
    day_labels = []
    day_start_idx = 0

    for idx, timestamp in enumerate(x_values):
        x = x_pos(idx)
        if timestamp.minute == 0 and timestamp.second == 0 and timestamp.hour % 6 == 0:
            six_hour_tick_lines.append(
                f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{top+plot_height}" stroke="#f3f4f6" />'
            )
            six_hour_axis_ticks.append(
                f'<line x1="{x:.1f}" y1="{top+plot_height}" x2="{x:.1f}" y2="{top+plot_height+6}" stroke="#9ca3af" />'
            )
            six_hour_labels.append(
                f'<text x="{x:.1f}" y="{height-34}" text-anchor="middle" font-size="10" fill="#4b5563">{_six_hour_tick_label(timestamp)}</text>'
            )

        is_new_day = idx > 0 and timestamp.date() != x_values[idx - 1].date()
        if is_new_day:
            divider_x = x_pos(idx)
            day_dividers.append(
                f'<line x1="{divider_x:.1f}" y1="{top}" x2="{divider_x:.1f}" y2="{top+plot_height}" stroke="#d1d5db" />'
            )
            section_mid = (x_pos(day_start_idx) + x_pos(idx - 1)) / 2
            day_labels.append(
                f'<text x="{section_mid:.1f}" y="{height-14}" text-anchor="middle" font-size="11" fill="#111827">{escape(_day_tick_label(x_values[day_start_idx]))}</text>'
            )
            day_start_idx = idx

    section_mid = (x_pos(day_start_idx) + x_pos(len(x_values) - 1)) / 2
    day_labels.append(
        f'<text x="{section_mid:.1f}" y="{height-14}" text-anchor="middle" font-size="11" fill="#111827">{escape(_day_tick_label(x_values[day_start_idx]))}</text>'
    )

    polylines = []
    for item in series:
        for segment in polyline(item.points):
            polylines.append(
                f'<polyline fill="none" stroke="{item.color}" stroke-width="2" points="{segment}" />'
            )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect width="{width}" height="{height}" fill="white" />
  <text x="{left}" y="{title_y}" font-size="18" fill="#111827">{escape(title)}</text>
  {''.join(legend)}
  {''.join(grid_lines)}
  {''.join(six_hour_tick_lines)}
  {''.join(day_dividers)}
  <line x1="{left}" y1="{top+plot_height}" x2="{width-right}" y2="{top+plot_height}" stroke="#9ca3af" />
  <line x1="{left}" y1="{top}" x2="{left}" y2="{top+plot_height}" stroke="#9ca3af" />
  {''.join(y_axis_labels)}
  {''.join(six_hour_axis_ticks)}
  {''.join(six_hour_labels)}
  {''.join(day_labels)}
  {''.join(polylines)}
</svg>
"""
