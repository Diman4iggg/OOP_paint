from __future__ import annotations

import math
from typing import Iterable

Point = tuple[float, float]


def rotate_point(point: Point, center: Point, angle_deg: float) -> Point:
    angle_rad = math.radians(angle_deg)
    px, py = point
    cx, cy = center
    tx = px - cx
    ty = py - cy
    cos_a = math.cos(angle_rad)
    sin_a = math.sin(angle_rad)
    return (
        cx + tx * cos_a - ty * sin_a,
        cy + tx * sin_a + ty * cos_a,
    )


def transform_points(points: Iterable[Point], center: Point, angle_deg: float) -> list[Point]:
    return [rotate_point(point, center, angle_deg) for point in points]


def bounding_box(points: Iterable[Point]) -> tuple[float, float, float, float]:
    pts = list(points)
    xs = [point[0] for point in pts]
    ys = [point[1] for point in pts]
    return min(xs), min(ys), max(xs), max(ys)


def bbox_size(points: Iterable[Point]) -> tuple[float, float]:
    left, top, right, bottom = bounding_box(points)
    return right - left, bottom - top


def point_in_bbox(point: Point, bbox: tuple[float, float, float, float], padding: float = 0.0) -> bool:
    x, y = point
    left, top, right, bottom = bbox
    return left - padding <= x <= right + padding and top - padding <= y <= bottom + padding


def point_in_polygon(point: Point, polygon: list[Point]) -> bool:
    x, y = point
    inside = False
    count = len(polygon)
    if count < 3:
        return False
    for index in range(count):
        x1, y1 = polygon[index]
        x2, y2 = polygon[(index + 1) % count]
        intersects = ((y1 > y) != (y2 > y)) and (
            x < (x2 - x1) * (y - y1) / ((y2 - y1) or 1e-9) + x1
        )
        if intersects:
            inside = not inside
    return inside


def distance_point_to_segment(point: Point, start: Point, end: Point) -> float:
    px, py = point
    x1, y1 = start
    x2, y2 = end
    dx = x2 - x1
    dy = y2 - y1
    if dx == 0 and dy == 0:
        return math.dist(point, start)
    t = ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    projection = (x1 + t * dx, y1 + t * dy)
    return math.dist(point, projection)


def polyline_hit(point: Point, points: list[Point], tolerance: float) -> bool:
    for index in range(len(points) - 1):
        if distance_point_to_segment(point, points[index], points[index + 1]) <= tolerance:
            return True
    return False


def sample_ellipse(center: Point, width: float, height: float, segments: int = 48) -> list[Point]:
    cx, cy = center
    rx = width / 2
    ry = height / 2
    return [
        (
            cx + math.cos(2 * math.pi * index / segments) * rx,
            cy + math.sin(2 * math.pi * index / segments) * ry,
        )
        for index in range(segments)
    ]


def flatten_points(points: Iterable[Point]) -> list[float]:
    flattened: list[float] = []
    for x, y in points:
        flattened.extend([x, y])
    return flattened


def center_of_bbox(points: Iterable[Point]) -> Point:
    left, top, right, bottom = bounding_box(points)
    return (left + right) / 2, (top + bottom) / 2
