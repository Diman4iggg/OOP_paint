from __future__ import annotations

import json
from pathlib import Path

from .models import Document, Layer
from .plugins import FigureRegistry


def document_to_data(document: Document, selected_ids: list[str] | None = None) -> dict:
    return {
        "layers": [layer.to_dict() for layer in document.layers],
        "active_layer_id": document.active_layer_id,
        "selected_ids": selected_ids or [],
    }


def document_from_data(data: dict, registry: FigureRegistry) -> tuple[Document, list[str]]:
    document = Document()
    for layer_data in data.get("layers", []):
        layer = Layer(id=layer_data["id"], name=layer_data["name"])
        for figure_data in layer_data.get("figures", []):
            layer.figures.append(registry.create_figure_from_data(figure_data))
        document.layers.append(layer)
    document.active_layer_id = data.get("active_layer_id")
    document.ensure_default_layer()
    return document, list(data.get("selected_ids", []))


def save_document(path: str | Path, document: Document, selected_ids: list[str]) -> None:
    Path(path).write_text(
        json.dumps(document_to_data(document, selected_ids), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_document(path: str | Path, registry: FigureRegistry) -> tuple[Document, list[str]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return document_from_data(data, registry)
