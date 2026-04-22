from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import colorchooser, filedialog, messagebox, simpledialog, ttk

from .geometry import Point
from .history import HistoryManager, SnapshotCommand
from .models import Document, DrawingStyle, Figure, FigureDescriptor
from .plugins import FigureRegistry, create_default_document, load_plugin, load_plugins_from_directory, register_builtin_figures
from .serialization import (
    document_from_data,
    document_to_data,
    load_document as load_document_file,
    save_document as save_document_file,
)


class EditorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("ЛР2-ЛР3 Графический редактор")
        self.geometry("1400x860")
        self.minsize(1100, 700)

        self.registry = FigureRegistry()
        register_builtin_figures(self.registry)
        self.loaded_plugins = load_plugins_from_directory(Path.cwd() / "plugins", self.registry)

        self.document: Document = create_default_document()
        self.history = HistoryManager()
        self.selected_ids: list[str] = []
        self.current_file: str | None = None

        self.current_tool = tk.StringVar(value="select")
        self.stroke_color = tk.StringVar(value="#202020")
        self.fill_color = tk.StringVar(value="#d9e8ff")
        self.stroke_width = tk.IntVar(value=2)
        self.rotation_value = tk.DoubleVar(value=15.0)
        self.width_value = tk.DoubleVar(value=120.0)
        self.height_value = tk.DoubleVar(value=80.0)
        self.status_text = tk.StringVar(value="Готово")

        self.drag_start: Point | None = None
        self.drag_previous: Point | None = None
        self.preview_figure: Figure | None = None
        self.point_drawing: list[Point] = []
        self.marquee_start: Point | None = None
        self.move_before_state: dict | None = None

        self._build_ui()
        self._bind_shortcuts()
        self.refresh_toolbox()
        self.refresh_layers()
        self.render_canvas()

    def _build_ui(self) -> None:
        self.columnconfigure(1, weight=1)
        self.rowconfigure(1, weight=1)

        toolbar = ttk.Frame(self, padding=8)
        toolbar.grid(row=0, column=0, columnspan=3, sticky="ew")
        toolbar.columnconfigure(1, weight=1)

        file_frame = ttk.LabelFrame(toolbar, text="Файл")
        file_frame.grid(row=0, column=0, padx=(0, 8), sticky="w")
        ttk.Button(file_frame, text="Новый", command=self.new_document).grid(row=0, column=0, padx=2, pady=2)
        ttk.Button(file_frame, text="Открыть", command=self.open_document).grid(row=0, column=1, padx=2, pady=2)
        ttk.Button(file_frame, text="Сохранить", command=self.save_document).grid(row=0, column=2, padx=2, pady=2)
        ttk.Button(file_frame, text="Сохранить как", command=self.save_document_as).grid(row=0, column=3, padx=2, pady=2)

        edit_frame = ttk.LabelFrame(toolbar, text="Действия")
        edit_frame.grid(row=0, column=1, padx=(0, 8), sticky="w")
        ttk.Button(edit_frame, text="Отменить", command=self.undo).grid(row=0, column=0, padx=2, pady=2)
        ttk.Button(edit_frame, text="Повторить", command=self.redo).grid(row=0, column=1, padx=2, pady=2)
        ttk.Button(edit_frame, text="Дублировать", command=self.duplicate_selection).grid(row=0, column=2, padx=2, pady=2)
        ttk.Button(edit_frame, text="Удалить", command=self.delete_selection).grid(row=0, column=3, padx=2, pady=2)
        ttk.Button(edit_frame, text="Загрузить плагин", command=self.load_plugin_from_file).grid(row=0, column=4, padx=2, pady=2)

        move_frame = ttk.LabelFrame(toolbar, text="Сдвиг на 1px")
        move_frame.grid(row=0, column=2, sticky="e")
        ttk.Button(move_frame, text="←", width=3, command=lambda: self.nudge_selection(-1, 0)).grid(row=0, column=0, padx=1, pady=2)
        ttk.Button(move_frame, text="↑", width=3, command=lambda: self.nudge_selection(0, -1)).grid(row=0, column=1, padx=1, pady=2)
        ttk.Button(move_frame, text="↓", width=3, command=lambda: self.nudge_selection(0, 1)).grid(row=0, column=2, padx=1, pady=2)
        ttk.Button(move_frame, text="→", width=3, command=lambda: self.nudge_selection(1, 0)).grid(row=0, column=3, padx=1, pady=2)

        left_panel = ttk.Frame(self, padding=(8, 0, 8, 8))
        left_panel.grid(row=1, column=0, sticky="ns")
        left_panel.rowconfigure(3, weight=1)

        tools_frame = ttk.LabelFrame(left_panel, text="Инструменты", padding=8)
        tools_frame.grid(row=0, column=0, sticky="ew")
        self.tools_frame = tools_frame

        style_frame = ttk.LabelFrame(left_panel, text="Свойства", padding=8)
        style_frame.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        ttk.Label(style_frame, text="Толщина").grid(row=0, column=0, sticky="w")
        ttk.Spinbox(style_frame, from_=1, to=20, textvariable=self.stroke_width, width=8).grid(row=0, column=1, sticky="ew")
        ttk.Button(style_frame, text="Цвет линии", command=self.choose_stroke_color).grid(row=1, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        ttk.Button(style_frame, text="Цвет заливки", command=self.choose_fill_color).grid(row=2, column=0, columnspan=2, sticky="ew", pady=(4, 0))
        ttk.Button(style_frame, text="Применить стиль", command=self.apply_style_to_selection).grid(row=3, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        ttk.Button(style_frame, text="Без заливки", command=self.clear_fill_color).grid(row=4, column=0, columnspan=2, sticky="ew", pady=(4, 0))

        transform_frame = ttk.LabelFrame(left_panel, text="Трансформация", padding=8)
        transform_frame.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        ttk.Label(transform_frame, text="Ширина").grid(row=0, column=0, sticky="w")
        ttk.Entry(transform_frame, textvariable=self.width_value, width=10).grid(row=0, column=1, sticky="ew")
        ttk.Label(transform_frame, text="Высота").grid(row=1, column=0, sticky="w")
        ttk.Entry(transform_frame, textvariable=self.height_value, width=10).grid(row=1, column=1, sticky="ew")
        ttk.Button(transform_frame, text="Изменить размер", command=self.resize_selection).grid(row=2, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        ttk.Label(transform_frame, text="Угол").grid(row=3, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(transform_frame, textvariable=self.rotation_value, width=10).grid(row=3, column=1, sticky="ew", pady=(8, 0))
        ttk.Button(transform_frame, text="Повернуть", command=self.rotate_selection).grid(row=4, column=0, columnspan=2, sticky="ew", pady=(6, 0))

        layers_frame = ttk.LabelFrame(left_panel, text="Слои", padding=8)
        layers_frame.grid(row=3, column=0, sticky="nsew", pady=(8, 0))
        layers_frame.rowconfigure(0, weight=1)
        self.layers_listbox = tk.Listbox(layers_frame, exportselection=False, height=12)
        self.layers_listbox.grid(row=0, column=0, columnspan=2, sticky="nsew")
        self.layers_listbox.bind("<<ListboxSelect>>", self.on_layer_selected)
        ttk.Button(layers_frame, text="Добавить", command=self.add_layer).grid(row=1, column=0, sticky="ew", pady=(6, 0))
        ttk.Button(layers_frame, text="Удалить", command=self.delete_layer).grid(row=1, column=1, sticky="ew", padx=(4, 0), pady=(6, 0))
        ttk.Button(layers_frame, text="Выше", command=lambda: self.move_layer(-1)).grid(row=2, column=0, sticky="ew", pady=(4, 0))
        ttk.Button(layers_frame, text="Ниже", command=lambda: self.move_layer(1)).grid(row=2, column=1, sticky="ew", padx=(4, 0), pady=(4, 0))
        ttk.Button(layers_frame, text="Фигуры в активный слой", command=self.move_selection_to_active_layer).grid(
            row=3,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=(6, 0),
        )

        canvas_frame = ttk.Frame(self, padding=(0, 0, 8, 8))
        canvas_frame.grid(row=1, column=1, sticky="nsew")
        canvas_frame.rowconfigure(0, weight=1)
        canvas_frame.columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(canvas_frame, bg="white", highlightthickness=1, highlightbackground="#b8b8b8")
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)
        self.canvas.bind("<Double-Button-1>", self.on_canvas_double_click)
        self.canvas.bind("<Motion>", self.on_canvas_motion)

        right_panel = ttk.Frame(self, padding=(0, 0, 8, 8))
        right_panel.grid(row=1, column=2, sticky="ns")
        info_frame = ttk.LabelFrame(right_panel, text="Подсказки", padding=8)
        info_frame.grid(row=0, column=0, sticky="n")
        ttk.Label(
            info_frame,
            text=(
                "Shift+клик: мультивыделение\n"
                "Delete: удалить\n"
                "Ctrl+Z / Ctrl+Y: история\n"
                "Ломаная/многоугольник: двойной клик для завершения"
            ),
            justify="left",
        ).grid(row=0, column=0, sticky="w")

        status_bar = ttk.Label(self, textvariable=self.status_text, anchor="w", padding=6)
        status_bar.grid(row=2, column=0, columnspan=3, sticky="ew")

    def _bind_shortcuts(self) -> None:
        self.bind("<Delete>", lambda event: self.delete_selection())
        self.bind("<Control-z>", lambda event: self.undo())
        self.bind("<Control-y>", lambda event: self.redo())
        self.bind("<Control-d>", lambda event: self.duplicate_selection())
        self.bind("<Left>", lambda event: self.nudge_selection(-1, 0))
        self.bind("<Right>", lambda event: self.nudge_selection(1, 0))
        self.bind("<Up>", lambda event: self.nudge_selection(0, -1))
        self.bind("<Down>", lambda event: self.nudge_selection(0, 1))

    def refresh_toolbox(self) -> None:
        for child in self.tools_frame.winfo_children():
            child.destroy()

        ttk.Radiobutton(self.tools_frame, text="Выделение", variable=self.current_tool, value="select").grid(
            row=0,
            column=0,
            sticky="w",
        )
        for index, descriptor in enumerate(self.registry.descriptors(), start=1):
            ttk.Radiobutton(
                self.tools_frame,
                text=descriptor.label,
                variable=self.current_tool,
                value=descriptor.type_name,
            ).grid(row=index, column=0, sticky="w")

    def current_style(self) -> DrawingStyle:
        return DrawingStyle(
            stroke_color=self.stroke_color.get(),
            fill_color=self.fill_color.get(),
            stroke_width=max(1, int(self.stroke_width.get())),
        )

    def export_state(self) -> dict:
        return document_to_data(self.document, self.selected_ids)

    def restore_state(self, state: dict) -> None:
        self.document, self.selected_ids = document_from_data(state, self.registry)
        self.point_drawing = []
        self.preview_figure = None
        self.drag_start = None
        self.drag_previous = None
        self.move_before_state = None
        self.refresh_layers()
        self.sync_property_panel()
        self.render_canvas()

    def push_history_state(self, label: str, before_state: dict, after_state: dict) -> None:
        if before_state != after_state:
            self.history.push(SnapshotCommand(label=label, before_state=before_state, after_state=after_state))

    def execute_document_change(self, label: str, mutation) -> None:
        before_state = self.export_state()
        mutation()
        after_state = self.export_state()
        self.push_history_state(label, before_state, after_state)
        self.refresh_layers()
        self.sync_property_panel()
        self.render_canvas()

    def render_canvas(self) -> None:
        self.canvas.delete("all")
        selected = set(self.selected_ids)
        for layer in reversed(self.document.layers):
            for figure in layer.figures:
                figure.draw(self.canvas, selected=figure.id in selected)
        if self.preview_figure is not None:
            self.preview_figure.draw(self.canvas, preview=True)
        if self.current_tool.get() in {"polyline", "polygon"} and len(self.point_drawing) >= 2:
            self.canvas.create_line(*self._flatten_preview_points(), fill="#2563eb", dash=(6, 2), width=2)

    def _flatten_preview_points(self) -> list[float]:
        points = self.point_drawing[:]
        return [coord for point in points for coord in point]

    def refresh_layers(self) -> None:
        current = self.document.active_layer_id
        self.layers_listbox.delete(0, tk.END)
        for index, layer in enumerate(self.document.layers):
            self.layers_listbox.insert(tk.END, layer.name)
            if layer.id == current:
                self.layers_listbox.selection_set(index)

    def sync_property_panel(self) -> None:
        figures = self.selected_figures()
        if not figures:
            return
        first = figures[0]
        self.stroke_color.set(first.style.stroke_color)
        self.fill_color.set(first.style.fill_color or "")
        self.stroke_width.set(first.style.stroke_width)
        width, height = first.get_dimensions()
        self.width_value.set(round(width, 2))
        self.height_value.set(round(height, 2))

    def selected_figures(self) -> list[Figure]:
        figures: list[Figure] = []
        for figure_id in self.selected_ids:
            figure = self.document.find_figure(figure_id)
            if figure is not None:
                figures.append(figure)
        return figures

    def set_status(self, message: str) -> None:
        self.status_text.set(message)

    def on_canvas_click(self, event) -> None:
        point = (event.x, event.y)
        tool = self.current_tool.get()
        if tool == "select":
            clicked = self.document.hit_test(point)
            shift_pressed = bool(event.state & 0x0001)
            if clicked is None:
                if not shift_pressed:
                    self.selected_ids = []
                self.render_canvas()
                return
            if shift_pressed:
                if clicked.id in self.selected_ids:
                    self.selected_ids = [figure_id for figure_id in self.selected_ids if figure_id != clicked.id]
                else:
                    self.selected_ids.append(clicked.id)
            else:
                if clicked.id not in self.selected_ids:
                    self.selected_ids = [clicked.id]
            layer = self.document.find_figure_layer(clicked.id)
            if layer is not None:
                self.document.active_layer_id = layer.id
            self.refresh_layers()
            self.sync_property_panel()
            self.render_canvas()
            if clicked.id in self.selected_ids:
                self.drag_start = point
                self.drag_previous = point
                self.move_before_state = self.export_state()
            return

        descriptor = self.registry.get_descriptor(tool)
        if descriptor.creation_mode == "drag":
            self.drag_start = point
            self.preview_figure = descriptor.create_from_drag(point, point, self.current_style())
            self.render_canvas()
            return

        if descriptor.creation_mode == "points":
            self.point_drawing.append(point)
            if len(self.point_drawing) >= 2:
                self.preview_figure = descriptor.create_from_points(self.point_drawing, self.current_style())
            self.render_canvas()

    def on_canvas_drag(self, event) -> None:
        point = (event.x, event.y)
        tool = self.current_tool.get()
        if tool == "select" and self.drag_previous is not None and self.selected_ids:
            dx = point[0] - self.drag_previous[0]
            dy = point[1] - self.drag_previous[1]
            for figure in self.selected_figures():
                figure.move(dx, dy)
            self.drag_previous = point
            self.sync_property_panel()
            self.render_canvas()
            return

        if self.drag_start is not None and tool != "select":
            descriptor = self.registry.get_descriptor(tool)
            if descriptor.creation_mode == "drag":
                self.preview_figure = descriptor.create_from_drag(self.drag_start, point, self.current_style())
                self.render_canvas()

    def on_canvas_release(self, event) -> None:
        point = (event.x, event.y)
        tool = self.current_tool.get()
        if tool == "select" and self.drag_start is not None and self.drag_previous is not None and self.move_before_state is not None:
            after_state = self.export_state()
            if after_state != self.move_before_state:
                self.history.push(
                    SnapshotCommand(
                        label="Перемещение фигур",
                        before_state=self.move_before_state,
                        after_state=after_state,
                    )
                )
            self.drag_start = None
            self.drag_previous = None
            self.move_before_state = None
            self.refresh_layers()
            self.render_canvas()
            return

        if self.drag_start is not None and tool != "select":
            descriptor = self.registry.get_descriptor(tool)
            if descriptor.creation_mode == "drag":
                figure = descriptor.create_from_drag(self.drag_start, point, self.current_style())
                self.execute_document_change("Добавление фигуры", lambda: self._add_figure_and_select(figure))
            self.drag_start = None
            self.preview_figure = None
            self.render_canvas()

    def on_canvas_motion(self, event) -> None:
        tool = self.current_tool.get()
        if tool in {"polyline", "polygon"} and self.point_drawing:
            descriptor = self.registry.get_descriptor(tool)
            points = self.point_drawing + [(event.x, event.y)]
            self.preview_figure = descriptor.create_from_points(points, self.current_style())
            self.render_canvas()

    def on_canvas_double_click(self, event) -> None:
        tool = self.current_tool.get()
        if tool not in {"polyline", "polygon"}:
            return
        descriptor = self.registry.get_descriptor(tool)
        final_points = self.point_drawing[:]
        if not final_points or final_points[-1] != (event.x, event.y):
            final_points.append((event.x, event.y))
        minimum = 3 if tool == "polygon" else 2
        if len(final_points) < minimum:
            self.point_drawing = []
            self.preview_figure = None
            self.render_canvas()
            return
        figure = descriptor.create_from_points(final_points, self.current_style())
        self.point_drawing = []
        self.preview_figure = None
        self.execute_document_change("Добавление фигуры", lambda: self._add_figure_and_select(figure))

    def _add_figure_and_select(self, figure: Figure) -> None:
        self.document.add_figure(figure)
        self.selected_ids = [figure.id]

    def new_document(self) -> None:
        self.document = create_default_document()
        self.selected_ids = []
        self.current_file = None
        self.history.clear()
        self.point_drawing = []
        self.preview_figure = None
        self.refresh_layers()
        self.render_canvas()
        self.set_status("Создан новый документ")

    def open_document(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if not path:
            return
        try:
            self.document, self.selected_ids = load_document_file(path, self.registry)
        except Exception as error:
            messagebox.showerror("Ошибка", str(error))
            return
        self.current_file = path
        self.history.clear()
        self.point_drawing = []
        self.preview_figure = None
        self.refresh_layers()
        self.sync_property_panel()
        self.render_canvas()
        self.set_status(f"Открыт файл: {Path(path).name}")

    def save_document(self) -> None:
        if self.current_file is None:
            self.save_document_as()
            return
        save_document_file(self.current_file, self.document, self.selected_ids)
        self.set_status(f"Сохранено: {Path(self.current_file).name}")

    def save_document_as(self) -> None:
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")])
        if not path:
            return
        self.current_file = path
        self.save_document()

    def choose_stroke_color(self) -> None:
        chosen = colorchooser.askcolor(color=self.stroke_color.get())[1]
        if chosen:
            self.stroke_color.set(chosen)

    def choose_fill_color(self) -> None:
        chosen = colorchooser.askcolor(color=self.fill_color.get() or "#ffffff")[1]
        if chosen:
            self.fill_color.set(chosen)

    def clear_fill_color(self) -> None:
        self.fill_color.set("")

    def apply_style_to_selection(self) -> None:
        figures = self.selected_figures()
        if not figures:
            return
        style = self.current_style()

        def mutation():
            for figure in figures:
                figure.set_style(style.stroke_color, style.fill_color, style.stroke_width)

        self.execute_document_change("Изменение стиля", mutation)

    def resize_selection(self) -> None:
        figures = self.selected_figures()
        if not figures:
            return
        width = max(1.0, float(self.width_value.get()))
        height = max(1.0, float(self.height_value.get()))

        def mutation():
            for figure in figures:
                figure.resize_to(width, height)

        self.execute_document_change("Изменение размера", mutation)

    def rotate_selection(self) -> None:
        figures = self.selected_figures()
        if not figures:
            return
        angle = float(self.rotation_value.get())

        def mutation():
            for figure in figures:
                figure.rotate(angle)

        self.execute_document_change("Поворот фигур", mutation)

    def delete_selection(self) -> None:
        if not self.selected_ids:
            return
        target_ids = set(self.selected_ids)

        def mutation():
            self.document.remove_figures(target_ids)
            self.selected_ids = []

        self.execute_document_change("Удаление фигур", mutation)

    def duplicate_selection(self) -> None:
        figures = self.selected_figures()
        if not figures:
            return

        def mutation():
            duplicates: list[Figure] = []
            for figure in figures:
                duplicate = figure.duplicate()
                layer = self.document.find_figure_layer(figure.id) or self.document.get_active_layer()
                layer.figures.append(duplicate)
                duplicates.append(duplicate)
            self.selected_ids = [figure.id for figure in duplicates]

        self.execute_document_change("Копирование фигур", mutation)

    def nudge_selection(self, dx: int, dy: int) -> None:
        figures = self.selected_figures()
        if not figures:
            return

        def mutation():
            for figure in figures:
                figure.move(dx, dy)

        self.execute_document_change("Сдвиг фигур", mutation)

    def undo(self) -> None:
        self.history.undo(self.restore_state)
        self.refresh_layers()
        self.sync_property_panel()
        self.render_canvas()

    def redo(self) -> None:
        self.history.redo(self.restore_state)
        self.refresh_layers()
        self.sync_property_panel()
        self.render_canvas()

    def add_layer(self) -> None:
        name = simpledialog.askstring("Новый слой", "Название слоя:")
        if name is None:
            return

        def mutation():
            self.document.add_layer(name or None)

        self.execute_document_change("Добавление слоя", mutation)

    def delete_layer(self) -> None:
        layer = self.document.get_active_layer()
        if len(self.document.layers) <= 1:
            messagebox.showinfo("Слои", "Нельзя удалить единственный слой")
            return
        if not messagebox.askyesno("Удаление слоя", "Удалить слой вместе со всеми фигурами?"):
            return
        affected_ids = {figure.id for figure in layer.figures}

        def mutation():
            self.document.delete_layer(layer.id)
            self.selected_ids = [figure_id for figure_id in self.selected_ids if figure_id not in affected_ids]

        self.execute_document_change("Удаление слоя", mutation)

    def move_layer(self, offset: int) -> None:
        layer = self.document.get_active_layer()

        def mutation():
            self.document.move_layer(layer.id, offset)

        self.execute_document_change("Перемещение слоя", mutation)

    def on_layer_selected(self, event) -> None:
        selection = self.layers_listbox.curselection()
        if not selection:
            return
        index = selection[0]
        if index >= len(self.document.layers):
            return
        self.document.active_layer_id = self.document.layers[index].id
        self.render_canvas()

    def move_selection_to_active_layer(self) -> None:
        if not self.selected_ids:
            return
        target_layer = self.document.get_active_layer()
        figure_ids = set(self.selected_ids)

        def mutation():
            self.document.move_figures_to_layer(figure_ids, target_layer.id)

        self.execute_document_change("Перенос фигур в слой", mutation)

    def load_plugin_from_file(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("Python plugin", "*.py")])
        if not path:
            return
        try:
            name = load_plugin(path, self.registry)
        except Exception as error:
            messagebox.showerror("Ошибка загрузки", str(error))
            return
        self.refresh_toolbox()
        self.set_status(f"Плагин загружен: {name}")


def run() -> None:
    app = EditorApp()
    app.mainloop()
