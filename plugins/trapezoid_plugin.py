from __future__ import annotations

from graphic_editor.models import DrawingStyle, FigureDescriptor, Point, PolygonFigure


class TrapezoidFigure(PolygonFigure):
    type_name = "trapezoid"
    display_name = "Трапеция"

    @classmethod
    def from_bounds(cls, start: Point, end: Point, style: DrawingStyle | None = None) -> "TrapezoidFigure":
        x1, y1 = start
        x2, y2 = end
        left = min(x1, x2)
        right = max(x1, x2)
        top = min(y1, y2)
        bottom = max(y1, y2)
        width = right - left
        inset = width * 0.2
        points = [
            (left + inset, top),
            (right - inset, top),
            (right, bottom),
            (left, bottom),
        ]
        return cls(points=points, style=style)


def register(registry) -> None:
    registry.register(
        FigureDescriptor(
            type_name=TrapezoidFigure.type_name,
            label=TrapezoidFigure.display_name,
            figure_class=TrapezoidFigure,
            creation_mode="drag",
            create_from_drag=lambda start, end, style: TrapezoidFigure.from_bounds(start, end, style),
        )
    )
