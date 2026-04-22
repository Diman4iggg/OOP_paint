from __future__ import annotations

import importlib.util
from pathlib import Path

from .models import (
    Document,
    DrawingStyle,
    EllipseFigure,
    Figure,
    FigureDescriptor,
    LineFigure,
    PolygonFigure,
    PolylineFigure,
    RectangleFigure,
)


class FigureRegistry:
    def __init__(self):
        self._descriptors: dict[str, FigureDescriptor] = {}

    def register(self, descriptor: FigureDescriptor) -> None:
        self._descriptors[descriptor.type_name] = descriptor

    def get_descriptor(self, type_name: str) -> FigureDescriptor:
        return self._descriptors[type_name]

    def descriptors(self) -> list[FigureDescriptor]:
        order = ["line", "polyline", "ellipse", "rectangle", "polygon"]
        known = [self._descriptors[name] for name in order if name in self._descriptors]
        plugins = [descriptor for name, descriptor in self._descriptors.items() if name not in order]
        return known + sorted(plugins, key=lambda item: item.label.lower())

    def create_figure_from_data(self, data: dict) -> Figure:
        descriptor = self.get_descriptor(data["type"])
        return descriptor.figure_class.from_dict(data)


def register_builtin_figures(registry: FigureRegistry) -> None:
    registry.register(
        FigureDescriptor(
            type_name=LineFigure.type_name,
            label=LineFigure.display_name,
            figure_class=LineFigure,
            creation_mode="drag",
            create_from_drag=lambda start, end, style: LineFigure(points=[start, end], style=style),
        )
    )
    registry.register(
        FigureDescriptor(
            type_name=PolylineFigure.type_name,
            label=PolylineFigure.display_name,
            figure_class=PolylineFigure,
            creation_mode="points",
            create_from_points=lambda points, style: PolylineFigure(points=points, style=style),
        )
    )
    registry.register(
        FigureDescriptor(
            type_name=EllipseFigure.type_name,
            label=EllipseFigure.display_name,
            figure_class=EllipseFigure,
            creation_mode="drag",
            create_from_drag=lambda start, end, style: EllipseFigure.from_bounds(start, end, style),
        )
    )
    registry.register(
        FigureDescriptor(
            type_name=RectangleFigure.type_name,
            label=RectangleFigure.display_name,
            figure_class=RectangleFigure,
            creation_mode="drag",
            create_from_drag=lambda start, end, style: RectangleFigure.from_bounds(start, end, style),
        )
    )
    registry.register(
        FigureDescriptor(
            type_name=PolygonFigure.type_name,
            label=PolygonFigure.display_name,
            figure_class=PolygonFigure,
            creation_mode="points",
            create_from_points=lambda points, style: PolygonFigure(points=points, style=style),
        )
    )


def create_default_document() -> Document:
    document = Document()
    document.ensure_default_layer()
    return document


def load_plugin(path: str | Path, registry: FigureRegistry) -> str:
    plugin_path = Path(path)
    spec = importlib.util.spec_from_file_location(plugin_path.stem, plugin_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Не удалось загрузить плагин: {plugin_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    if hasattr(module, "register"):
        module.register(registry)
    elif hasattr(module, "PLUGIN_DESCRIPTORS"):
        for descriptor in module.PLUGIN_DESCRIPTORS:
            registry.register(descriptor)
    else:
        raise RuntimeError("Плагин должен содержать register(registry) или PLUGIN_DESCRIPTORS")

    return plugin_path.stem


def load_plugins_from_directory(directory: str | Path, registry: FigureRegistry) -> list[str]:
    directory_path = Path(directory)
    if not directory_path.exists():
        return []
    loaded: list[str] = []
    for plugin_path in sorted(directory_path.glob("*.py")):
        if plugin_path.name.startswith("_"):
            continue
        loaded.append(load_plugin(plugin_path, registry))
    return loaded
