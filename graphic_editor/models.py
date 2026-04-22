from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable
from uuid import uuid4

from .geometry import (
    Point,
    bbox_size,
    bounding_box,
    center_of_bbox,
    flatten_points,
    point_in_bbox,
    point_in_polygon,
    polyline_hit,
    rotate_point,
    sample_ellipse,
    transform_points,
)


def _new_id() -> str:
    return uuid4().hex


@dataclass
class DrawingStyle:
    stroke_color: str = "#202020"
    fill_color: str = ""
    stroke_width: int = 2

    def to_dict(self) -> dict:
        return {
            "stroke_color": self.stroke_color,
            "fill_color": self.fill_color,
            "stroke_width": self.stroke_width,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DrawingStyle":
        return cls(
            stroke_color=data.get("stroke_color", "#202020"),
            fill_color=data.get("fill_color", ""),
            stroke_width=int(data.get("stroke_width", 2)),
        )


class Figure(ABC):
    type_name = "figure"
    display_name = "Фигура"
    supports_fill = False

    def __init__(self, style: DrawingStyle | None = None, figure_id: str | None = None, rotation: float = 0.0):
        self.id = figure_id or _new_id()
        self.style = style or DrawingStyle()
        self.rotation = rotation

    @abstractmethod
    def clone(self) -> "Figure":
        raise NotImplementedError

    @abstractmethod
    def get_center(self) -> Point:
        raise NotImplementedError

    @abstractmethod
    def move(self, dx: float, dy: float) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_render_points(self) -> list[Point]:
        raise NotImplementedError

    @abstractmethod
    def hit_test(self, point: Point) -> bool:
        raise NotImplementedError

    @abstractmethod
    def resize_to(self, width: float, height: float) -> None:
        raise NotImplementedError

    @abstractmethod
    def to_dict(self) -> dict:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def from_dict(cls, data: dict) -> "Figure":
        raise NotImplementedError

    def duplicate(self, dx: float = 20.0, dy: float = 20.0) -> "Figure":
        figure = self.clone()
        figure.id = _new_id()
        figure.move(dx, dy)
        return figure

    def set_style(self, stroke_color: str, fill_color: str, stroke_width: int) -> None:
        self.style.stroke_color = stroke_color
        self.style.fill_color = fill_color if self.supports_fill else ""
        self.style.stroke_width = int(stroke_width)

    def rotate(self, angle_deg: float) -> None:
        self.rotation = (self.rotation + angle_deg) % 360

    def set_rotation(self, angle_deg: float) -> None:
        self.rotation = angle_deg % 360

    def get_dimensions(self) -> tuple[float, float]:
        return bbox_size(self.get_render_points())

    def get_bounding_box(self) -> tuple[float, float, float, float]:
        return bounding_box(self.get_render_points())

    def draw(self, canvas, *, selected: bool = False, preview: bool = False) -> None:
        self._draw_internal(canvas, selected=selected, preview=preview)
        if selected and not preview:
            left, top, right, bottom = self.get_bounding_box()
            canvas.create_rectangle(
                left - 4,
                top - 4,
                right + 4,
                bottom + 4,
                dash=(4, 2),
                outline="#3b82f6",
                width=1,
            )

    @abstractmethod
    def _draw_internal(self, canvas, *, selected: bool, preview: bool) -> None:
        raise NotImplementedError


class PointFigure(Figure):
    supports_fill = True

    def __init__(
        self,
        points: list[Point],
        style: DrawingStyle | None = None,
        figure_id: str | None = None,
        rotation: float = 0.0,
    ):
        super().__init__(style=style, figure_id=figure_id, rotation=rotation)
        self.points = [(float(x), float(y)) for x, y in points]

    def clone(self) -> "PointFigure":
        return self.__class__(
            points=list(self.points),
            style=DrawingStyle.from_dict(self.style.to_dict()),
            figure_id=self.id,
            rotation=self.rotation,
        )

    def get_center(self) -> Point:
        return center_of_bbox(self.points)

    def get_render_points(self) -> list[Point]:
        return transform_points(self.points, self.get_center(), self.rotation)

    def move(self, dx: float, dy: float) -> None:
        self.points = [(x + dx, y + dy) for x, y in self.points]

    def resize_to(self, width: float, height: float) -> None:
        current_points = self.get_render_points()
        current_width, current_height = bbox_size(current_points)
        scale_x = (width / current_width) if current_width else 1.0
        scale_y = (height / current_height) if current_height else 1.0
        center = center_of_bbox(current_points)
        unrotated = [rotate_point(point, center, -self.rotation) for point in current_points]
        self.points = [
            (center[0] + (x - center[0]) * scale_x, center[1] + (y - center[1]) * scale_y)
            for x, y in unrotated
        ]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type_name,
            "rotation": self.rotation,
            "style": self.style.to_dict(),
            "points": self.points,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PointFigure":
        return cls(
            points=[tuple(point) for point in data["points"]],
            style=DrawingStyle.from_dict(data.get("style", {})),
            figure_id=data.get("id"),
            rotation=float(data.get("rotation", 0.0)),
        )


class LineFigure(PointFigure):
    type_name = "line"
    display_name = "Отрезок"
    supports_fill = False

    def hit_test(self, point: Point) -> bool:
        return polyline_hit(point, self.get_render_points(), tolerance=max(6, self.style.stroke_width + 4))

    def _draw_internal(self, canvas, *, selected: bool, preview: bool) -> None:
        points = flatten_points(self.get_render_points())
        dash = (6, 3) if preview else ()
        canvas.create_line(
            *points,
            fill=self.style.stroke_color,
            width=self.style.stroke_width,
            dash=dash,
        )


class PolylineFigure(PointFigure):
    type_name = "polyline"
    display_name = "Ломаная"
    supports_fill = False

    def hit_test(self, point: Point) -> bool:
        return polyline_hit(point, self.get_render_points(), tolerance=max(6, self.style.stroke_width + 4))

    def _draw_internal(self, canvas, *, selected: bool, preview: bool) -> None:
        points = flatten_points(self.get_render_points())
        dash = (6, 3) if preview else ()
        canvas.create_line(
            *points,
            fill=self.style.stroke_color,
            width=self.style.stroke_width,
            dash=dash,
        )


class PolygonFigure(PointFigure):
    type_name = "polygon"
    display_name = "Многоугольник"
    supports_fill = True

    def hit_test(self, point: Point) -> bool:
        render_points = self.get_render_points()
        if point_in_polygon(point, render_points):
            return True
        return polyline_hit(point, render_points + [render_points[0]], tolerance=max(6, self.style.stroke_width + 4))

    def _draw_internal(self, canvas, *, selected: bool, preview: bool) -> None:
        points = flatten_points(self.get_render_points())
        dash = (6, 3) if preview else ()
        canvas.create_polygon(
            *points,
            outline=self.style.stroke_color,
            fill=self.style.fill_color or "",
            width=self.style.stroke_width,
            dash=dash,
        )


class RectangleFigure(PolygonFigure):
    type_name = "rectangle"
    display_name = "Прямоугольник"

    @classmethod
    def from_bounds(cls, start: Point, end: Point, style: DrawingStyle | None = None) -> "RectangleFigure":
        x1, y1 = start
        x2, y2 = end
        points = [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]
        return cls(points=points, style=style)


class EllipseFigure(Figure):
    type_name = "ellipse"
    display_name = "Эллипс"
    supports_fill = True

    def __init__(
        self,
        center: Point,
        width: float,
        height: float,
        style: DrawingStyle | None = None,
        figure_id: str | None = None,
        rotation: float = 0.0,
    ):
        super().__init__(style=style, figure_id=figure_id, rotation=rotation)
        self.center = (float(center[0]), float(center[1]))
        self.width = float(width)
        self.height = float(height)

    def clone(self) -> "EllipseFigure":
        return EllipseFigure(
            center=self.center,
            width=self.width,
            height=self.height,
            style=DrawingStyle.from_dict(self.style.to_dict()),
            figure_id=self.id,
            rotation=self.rotation,
        )

    @classmethod
    def from_bounds(cls, start: Point, end: Point, style: DrawingStyle | None = None) -> "EllipseFigure":
        x1, y1 = start
        x2, y2 = end
        center = ((x1 + x2) / 2, (y1 + y2) / 2)
        return cls(center=center, width=abs(x2 - x1), height=abs(y2 - y1), style=style)

    def get_center(self) -> Point:
        return self.center

    def move(self, dx: float, dy: float) -> None:
        self.center = (self.center[0] + dx, self.center[1] + dy)

    def resize_to(self, width: float, height: float) -> None:
        self.width = abs(width)
        self.height = abs(height)

    def get_render_points(self) -> list[Point]:
        points = sample_ellipse(self.center, self.width, self.height)
        return transform_points(points, self.center, self.rotation)

    def hit_test(self, point: Point) -> bool:
        if not point_in_bbox(point, self.get_bounding_box(), padding=max(6, self.style.stroke_width + 4)):
            return False
        return point_in_polygon(point, self.get_render_points())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type_name,
            "rotation": self.rotation,
            "style": self.style.to_dict(),
            "center": self.center,
            "width": self.width,
            "height": self.height,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "EllipseFigure":
        return cls(
            center=tuple(data["center"]),
            width=float(data["width"]),
            height=float(data["height"]),
            style=DrawingStyle.from_dict(data.get("style", {})),
            figure_id=data.get("id"),
            rotation=float(data.get("rotation", 0.0)),
        )

    def _draw_internal(self, canvas, *, selected: bool, preview: bool) -> None:
        points = flatten_points(self.get_render_points())
        dash = (6, 3) if preview else ()
        canvas.create_polygon(
            *points,
            outline=self.style.stroke_color,
            fill=self.style.fill_color or "",
            width=self.style.stroke_width,
            smooth=True,
            dash=dash,
        )


@dataclass
class Layer:
    id: str
    name: str
    figures: list[Figure] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "figures": [figure.to_dict() for figure in self.figures],
        }


@dataclass
class Document:
    layers: list[Layer] = field(default_factory=list)
    active_layer_id: str | None = None

    def ensure_default_layer(self) -> None:
        if not self.layers:
            layer = Layer(id=_new_id(), name="Слой 1")
            self.layers.append(layer)
            self.active_layer_id = layer.id
        elif self.active_layer_id is None:
            self.active_layer_id = self.layers[0].id

    def get_active_layer(self) -> Layer:
        self.ensure_default_layer()
        layer = self.get_layer(self.active_layer_id)
        if layer is None:
            self.active_layer_id = self.layers[0].id
            return self.layers[0]
        return layer

    def get_layer(self, layer_id: str | None) -> Layer | None:
        for layer in self.layers:
            if layer.id == layer_id:
                return layer
        return None

    def add_layer(self, name: str | None = None) -> Layer:
        index = len(self.layers) + 1
        layer = Layer(id=_new_id(), name=name or f"Слой {index}")
        self.layers.append(layer)
        self.active_layer_id = layer.id
        return layer

    def delete_layer(self, layer_id: str) -> bool:
        if len(self.layers) <= 1:
            return False
        self.layers = [layer for layer in self.layers if layer.id != layer_id]
        if self.active_layer_id == layer_id:
            self.active_layer_id = self.layers[-1].id
        return True

    def move_layer(self, layer_id: str, offset: int) -> None:
        index = self.layer_index(layer_id)
        if index is None:
            return
        new_index = max(0, min(len(self.layers) - 1, index + offset))
        if new_index == index:
            return
        layer = self.layers.pop(index)
        self.layers.insert(new_index, layer)

    def layer_index(self, layer_id: str) -> int | None:
        for index, layer in enumerate(self.layers):
            if layer.id == layer_id:
                return index
        return None

    def add_figure(self, figure: Figure, layer_id: str | None = None) -> None:
        layer = self.get_layer(layer_id) or self.get_active_layer()
        layer.figures.append(figure)

    def all_figures(self) -> list[Figure]:
        figures: list[Figure] = []
        for layer in self.layers:
            figures.extend(layer.figures)
        return figures

    def find_figure(self, figure_id: str) -> Figure | None:
        for figure in self.all_figures():
            if figure.id == figure_id:
                return figure
        return None

    def find_figure_layer(self, figure_id: str) -> Layer | None:
        for layer in self.layers:
            if any(figure.id == figure_id for figure in layer.figures):
                return layer
        return None

    def remove_figures(self, figure_ids: set[str]) -> None:
        for layer in self.layers:
            layer.figures = [figure for figure in layer.figures if figure.id not in figure_ids]

    def move_figures_to_layer(self, figure_ids: set[str], target_layer_id: str) -> None:
        target_layer = self.get_layer(target_layer_id)
        if target_layer is None:
            return
        moved: list[Figure] = []
        for layer in self.layers:
            keep: list[Figure] = []
            for figure in layer.figures:
                if figure.id in figure_ids:
                    moved.append(figure)
                else:
                    keep.append(figure)
            layer.figures = keep
        target_layer.figures.extend(moved)

    def hit_test(self, point: Point) -> Figure | None:
        for layer in self.layers:
            for figure in reversed(layer.figures):
                if figure.hit_test(point):
                    return figure
        return None


@dataclass
class FigureDescriptor:
    type_name: str
    label: str
    figure_class: type[Figure]
    creation_mode: str
    create_from_drag: Callable[[Point, Point, DrawingStyle], Figure] | None = None
    create_from_points: Callable[[list[Point], DrawingStyle], Figure] | None = None
