from __future__ import annotations

from dataclasses import dataclass
from html import escape
from typing import Iterable


@dataclass(frozen=True)
class Series:
    label: str
    color: str
    points: list[float | None]


def _fmt(value: float) -> str:
    return f"{value:.2f}".rstrip("0").rstrip(".")


def line_chart(
    title: str,
    x_labels: list[str],
    series_list: Iterable[Series],
    width: int = 960,
    height: int = 360,
) -> str:
    series = list(series_list)
    all_values = [point for item in series for point in item.points if point is not None]
    if not all_values or len(x_labels) < 2:
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">'
            f'<text x="24" y="36" font-size="18">{escape(title)}</text>'
            '<text x="24" y="72" font-size="14">No data available</text>'
            "</svg>"
        )

    left = 70
    right = 20
    top = 40
    bottom = 55
    plot_width = width - left - right
    plot_height = height - top - bottom
    minimum = min(all_values)
    maximum = max(all_values)
    if minimum == maximum:
        minimum -= 1.0
        maximum += 1.0

    def x_pos(index: int) -> float:
        return left + (plot_width * index / max(1, len(x_labels) - 1))

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

    x_axis_marks = []
    for idx in {0, len(x_labels) // 2, len(x_labels) - 1}:
        x = x_pos(idx)
        label = x_labels[idx]
        x_axis_marks.append(
            f'<text x="{x:.1f}" y="{height-20}" text-anchor="middle" font-size="11" fill="#4b5563">{escape(label)}</text>'
        )

    legend = []
    legend_x = left
    legend_y = 22
    for item in series:
        legend.append(f'<rect x="{legend_x}" y="{legend_y-10}" width="10" height="10" fill="{item.color}" />')
        legend.append(
            f'<text x="{legend_x+16}" y="{legend_y}" font-size="12" fill="#111827">{escape(item.label)}</text>'
        )
        legend_x += 170

    polylines = []
    for item in series:
        for segment in polyline(item.points):
            polylines.append(
                f'<polyline fill="none" stroke="{item.color}" stroke-width="2" points="{segment}" />'
            )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect width="{width}" height="{height}" fill="white" />
  <text x="{left}" y="18" font-size="18" fill="#111827">{escape(title)}</text>
  {''.join(legend)}
  {''.join(grid_lines)}
  <line x1="{left}" y1="{top+plot_height}" x2="{width-right}" y2="{top+plot_height}" stroke="#9ca3af" />
  <line x1="{left}" y1="{top}" x2="{left}" y2="{top+plot_height}" stroke="#9ca3af" />
  {''.join(y_axis_labels)}
  {''.join(x_axis_marks)}
  {''.join(polylines)}
</svg>
"""

