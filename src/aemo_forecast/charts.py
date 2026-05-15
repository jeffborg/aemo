from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from html import escape
from typing import Iterable


@dataclass(frozen=True)
class Series:
    label: str
    color: str
    points: list[float | None]


@dataclass(frozen=True)
class Band:
    label: str
    color: str
    lower_points: list[float | None]
    upper_points: list[float | None]
    opacity: float = 0.18


def _fmt(value: float) -> str:
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _tooltip_timestamp(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M")


def _legend_width(label: str) -> int:
    return max(88, 32 + (len(label) * 7))


def _six_hour_tick_label(value: datetime) -> str:
    return value.strftime("%H")


def _day_tick_label(value: datetime) -> str:
    return value.strftime("%a %d %b")


def _nice_step(value: float) -> float:
    if value <= 0:
        return 1.0
    magnitude = 10 ** math.floor(math.log10(value))
    residual = value / magnitude
    if residual <= 1:
        nice = 1
    elif residual <= 2:
        nice = 2
    elif residual <= 5:
        nice = 5
    else:
        nice = 10
    return nice * magnitude


def _y_axis_domain(minimum: float, maximum: float, tick_count: int = 5) -> tuple[float, float, float]:
    if minimum == maximum:
        minimum -= 1.0
        maximum += 1.0

    positive_dominant = maximum > 0 and minimum >= -(maximum * 0.05)
    if positive_dominant:
        minimum = 0.0
        step = _nice_step(maximum / max(1, tick_count - 1))
        maximum = math.ceil(maximum / step) * step
        return minimum, maximum, step

    step = _nice_step((maximum - minimum) / max(1, tick_count - 1))
    minimum = math.floor(minimum / step) * step
    maximum = math.ceil(maximum / step) * step
    return minimum, maximum, step


def _y_axis_ticks(minimum: float, maximum: float, tick_count: int = 5) -> tuple[float, float, list[float]]:
    if minimum == maximum:
        minimum -= 1.0
        maximum += 1.0

    positive_dominant = maximum > 0 and minimum < 0 and minimum >= -(maximum * 0.1)
    if positive_dominant:
        positive_step = _nice_step(maximum / max(1, tick_count - 1))
        rounded_maximum = math.ceil(maximum / positive_step) * positive_step
        negative_step = _nice_step(abs(minimum))
        rounded_minimum = math.floor(minimum / negative_step) * negative_step

        ticks = []
        tick_value = rounded_minimum
        while tick_value < 0:
            ticks.append(tick_value)
            tick_value += negative_step
        ticks.append(0.0)

        tick_value = positive_step
        while tick_value <= rounded_maximum + (positive_step / 2):
            ticks.append(min(tick_value, rounded_maximum))
            tick_value += positive_step
        return rounded_minimum, rounded_maximum, ticks

    rounded_minimum, rounded_maximum, step = _y_axis_domain(minimum, maximum, tick_count)
    ticks = []
    tick_value = rounded_minimum
    while tick_value <= rounded_maximum + (step / 2):
        ticks.append(min(tick_value, rounded_maximum))
        tick_value += step
    return rounded_minimum, rounded_maximum, ticks


def line_chart(
    title: str,
    x_values: list[datetime],
    series_list: Iterable[Series],
    bands: Iterable[Band] = (),
    y_min: float | None = None,
    y_max: float | None = None,
    annotate_clipped_max: bool = False,
    width: int = 960,
    height: int = 360,
) -> str:
    series = list(series_list)
    area_bands = list(bands)
    all_values = [point for item in series for point in item.points if point is not None]
    all_values.extend(point for item in area_bands for point in item.lower_points if point is not None)
    all_values.extend(point for item in area_bands for point in item.upper_points if point is not None)
    if not all_values or len(x_values) < 2:
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">'
            f'<text x="24" y="36" font-size="18">{escape(title)}</text>'
            '<text x="24" y="72" font-size="14">No data available</text>'
            "</svg>"
        )

    left = 70
    right = 20
    actual_minimum = min(all_values)
    actual_maximum = max(all_values)
    minimum = actual_minimum if y_min is None else y_min
    maximum = actual_maximum if y_max is None else y_max
    minimum, maximum, y_ticks = _y_axis_ticks(minimum, maximum)

    title_y = 24
    legend_start_y = 46
    legend_row_height = 18
    legend = []
    legend_x = left
    legend_y = legend_start_y
    legend_rows = 1
    for item in [*area_bands, *series]:
        item_width = _legend_width(item.label)
        if legend_x > left and legend_x + item_width > width - right:
            legend_rows += 1
            legend_x = left
            legend_y += legend_row_height
        fill_opacity = f' fill-opacity="{item.opacity}"' if isinstance(item, Band) else ""
        legend.append(
            f'<rect x="{legend_x}" y="{legend_y-10}" width="10" height="10" fill="{item.color}"{fill_opacity} />'
        )
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

    def clipped_value(value: float) -> float:
        return min(max(value, minimum), maximum)

    def polyline(points: list[float | None]) -> list[str]:
        segments: list[str] = []
        current: list[str] = []
        for idx, point in enumerate(points):
            if point is None:
                if len(current) >= 2:
                    segments.append(" ".join(current))
                current = []
                continue
            current.append(f"{x_pos(idx):.1f},{y_pos(clipped_value(point)):.1f}")
        if len(current) >= 2:
            segments.append(" ".join(current))
        return segments

    def polygons(lower_points: list[float | None], upper_points: list[float | None]) -> list[str]:
        segments: list[list[tuple[float, float, float]]] = []
        current: list[tuple[float, float, float]] = []
        for idx, (lower, upper) in enumerate(zip(lower_points, upper_points)):
            if lower is None or upper is None:
                if len(current) >= 2:
                    segments.append(current)
                current = []
                continue
            current.append((x_pos(idx), y_pos(clipped_value(lower)), y_pos(clipped_value(upper))))
        if len(current) >= 2:
            segments.append(current)

        polygons_out = []
        for segment in segments:
            lower_edge = [f"{x:.1f},{lower_y:.1f}" for x, lower_y, _ in segment]
            upper_edge = [f"{x:.1f},{upper_y:.1f}" for x, _, upper_y in reversed(segment)]
            polygons_out.append(" ".join(lower_edge + upper_edge))
        return polygons_out

    grid_lines = []
    y_axis_labels = []
    for value in y_ticks:
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

    hover_targets = []
    for idx, timestamp in enumerate(x_values):
        if len(x_values) == 1:
            left_edge = left
            right_edge = width - right
        else:
            previous_x = x_pos(max(0, idx - 1))
            current_x = x_pos(idx)
            next_x = x_pos(min(len(x_values) - 1, idx + 1))
            left_edge = left if idx == 0 else (previous_x + current_x) / 2
            right_edge = (width - right) if idx == len(x_values) - 1 else (current_x + next_x) / 2

        tooltip_lines = [_tooltip_timestamp(timestamp)]
        for item in area_bands:
            lower = item.lower_points[idx]
            upper = item.upper_points[idx]
            if lower is not None and upper is not None:
                tooltip_lines.append(f"{item.label}: {_fmt(lower)} to {_fmt(upper)}")
        for item in series:
            point = item.points[idx]
            if point is not None:
                tooltip_lines.append(f"{item.label}: {_fmt(point)}")

        tooltip = "&#10;".join(escape(line) for line in tooltip_lines)
        hover_targets.append(
            f'<rect class="hover-band" x="{left_edge:.1f}" y="{top}" width="{max(1.0, right_edge - left_edge):.1f}" height="{plot_height}" rx="2" ry="2">'
            f"<title>{tooltip}</title>"
            "</rect>"
        )

    polylines = []
    for item in series:
        for segment in polyline(item.points):
            polylines.append(
                f'<polyline fill="none" stroke="{item.color}" stroke-width="2" points="{segment}" />'
            )

    band_polygons = []
    for item in area_bands:
        for polygon in polygons(item.lower_points, item.upper_points):
            band_polygons.append(
                f'<polygon fill="{item.color}" fill-opacity="{item.opacity}" stroke="none" points="{polygon}" />'
            )

    clipped_labels = []
    if annotate_clipped_max and y_max is not None:
        for item in series:
            run: list[tuple[int, float]] = []
            for idx, point in enumerate(item.points):
                if point is not None and point > y_max:
                    run.append((idx, point))
                    continue
                if run:
                    label_idx, label_value = max(run, key=lambda entry: entry[1])
                    clipped_labels.append(
                        f'<text x="{x_pos(label_idx):.1f}" y="{top-6}" text-anchor="start" font-size="10" fill="{item.color}" transform="rotate(-45 {x_pos(label_idx):.1f} {top-6})">{escape(_fmt(label_value))}</text>'
                    )
                    run = []
            if run:
                label_idx, label_value = max(run, key=lambda entry: entry[1])
                clipped_labels.append(
                    f'<text x="{x_pos(label_idx):.1f}" y="{top-6}" text-anchor="start" font-size="10" fill="{item.color}" transform="rotate(-45 {x_pos(label_idx):.1f} {top-6})">{escape(_fmt(label_value))}</text>'
                )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <style>
    .hover-band {{ fill: #2563eb; fill-opacity: 0; transition: fill-opacity 120ms ease-in-out; }}
    .hover-band:hover {{ fill-opacity: 0.08; }}
  </style>
  <rect width="{width}" height="{height}" fill="white" />
  <text x="{left}" y="{title_y}" font-size="18" fill="#111827">{escape(title)}</text>
  {''.join(legend)}
  {''.join(grid_lines)}
  {''.join(six_hour_tick_lines)}
  {''.join(day_dividers)}
  {''.join(band_polygons)}
  <line x1="{left}" y1="{top+plot_height}" x2="{width-right}" y2="{top+plot_height}" stroke="#9ca3af" />
  <line x1="{left}" y1="{top}" x2="{left}" y2="{top+plot_height}" stroke="#9ca3af" />
  {''.join(y_axis_labels)}
  {''.join(six_hour_axis_ticks)}
  {''.join(six_hour_labels)}
  {''.join(day_labels)}
  {''.join(clipped_labels)}
  {''.join(polylines)}
  {''.join(hover_targets)}
</svg>
"""
