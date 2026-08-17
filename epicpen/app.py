"""Controlador: conecta los hooks globales con el modelo y las vistas."""
import subprocess
import threading
import tkinter as tk
from collections import deque
from datetime import datetime
from pathlib import Path
from tkinter import colorchooser

from . import capture, win32
from .board import Board
from .overlay import Overlay
from .spotlight import Spotlight
from .toast import Toast
from .toolbar import Toolbar

DRAIN_MS = 8      # los hooks encolan; tk dibuja aparte (un hook lento lo mata Windows)
LIFT_MS = 2000
CURSOR_MS = 16    # ~60 fps para que el halo no vaya a rastras del puntero
HIDE_MS = 150     # margen para que Windows repinte donde estaba la barra
SHOTS_DIR = Path.home() / "Pictures" / "EpicPen"


class App:
    def __init__(self):
        win32.enable_dpi_awareness()
        self.screen = win32.screen_size()        # monitor primario: donde va la barra
        self.work = win32.work_area()            # lo mismo sin la barra de tareas
        self.desktop = win32.virtual_screen()    # todos los monitores: lo que cubre la tinta

        self.root = tk.Tk()
        self.root.title("EpicPen")
        self.overlay = Overlay(self.root, self.desktop)
        self.board = Board(self.overlay.canvas)
        self.spotlight = Spotlight(self.overlay.canvas)
        self.toolbar = Toolbar(self.root, self, self.work)
        self.toast = Toast(self.root, self.screen)

        self.drawing = False
        self._pressed = False
        self._modal = False
        self._events = deque()
        self._ui_hwnds = set()
        self._shot_result = None  # lo deja el hilo de guardado; lo recoge el drain
        self.hooks = win32.Hooks(self._on_mouse, self._on_key)

    # ---- API que usa la toolbar
    @property
    def mode(self):
        return self.board.mode

    @property
    def color(self):
        return self.board.color

    @property
    def width(self):
        return self.board.width

    @property
    def spotlight_on(self):
        return self.spotlight.enabled

    def set_mode(self, mode):
        self.board.mode = mode
        self.set_drawing(True)

    def set_color(self, color):
        self.board.color = color
        self._refresh()

    def pick_color(self):
        self._modal = True  # sin esto el hook se traga los clicks del dialogo
        try:
            chosen = colorchooser.askcolor(color=self.board.color, parent=self.root,
                                           title="Color del lapiz")[1]
        finally:
            self._modal = False
        if chosen:
            self.set_color(chosen)

    def toggle_spotlight(self):
        if self.spotlight.toggle():
            self._follow_cursor()
        self._refresh()

    def save_shot(self):
        self.root.withdraw()  # la barra no debe salir en la foto
        self.root.update()
        self.root.after(HIDE_MS, self._write_shot)

    def _write_shot(self):
        path = SHOTS_DIR / datetime.now().strftime("epicpen-%Y%m%d-%H%M%S.png")
        pixels = None
        try:
            pixels = capture.grab_rgba(*self.desktop)
        except Exception as err:
            self._shot_result = (False, str(err), path)
        self.root.deiconify()
        self.toolbar.pin()
        if pixels is not None:
            # comprimir el PNG tarda cientos de ms; en el hilo de tk el mainloop dejaria
            # de bombear mensajes y el hook se perderia clicks (trazos que no cierran)
            threading.Thread(target=self._encode_shot, args=(path, pixels),
                             daemon=True).start()

    def _encode_shot(self, path, pixels):
        try:
            SHOTS_DIR.mkdir(parents=True, exist_ok=True)
            path.write_bytes(capture.encode_png(self.desktop[2], self.desktop[3], pixels))
            self._shot_result = (True, str(path), path)
        except Exception as err:
            self._shot_result = (False, str(err), path)

    def _announce_shot(self):
        saved, detail, path = self._shot_result
        self._shot_result = None
        self.toolbar.flash_save(saved)
        if saved:
            self.toast.show("Captura guardada", f"{path}\nClick aqui para abrir la carpeta",
                            on_click=lambda: self._reveal(path))
        else:
            self.toast.show("No se pudo guardar la captura", detail, error=True)

    @staticmethod
    def _reveal(path):
        # /select, deja el explorador abierto con el archivo ya marcado
        subprocess.Popen(["explorer", f"/select,{path}"])

    def set_width(self, width):
        self.board.width = width
        self._refresh()

    def undo(self):
        self.board.undo()

    def clear(self):
        self.board.clear()

    def toggle_drawing(self):
        self.set_drawing(not self.drawing)

    def set_drawing(self, on):
        self.drawing = on
        self._pressed = False
        self._refresh()

    def quit(self):
        self.hooks.uninstall()
        for timer in self.root.tk.call("after", "info"):
            self.root.after_cancel(timer)  # si no, los bucles disparan sobre tk ya destruido
        self.root.destroy()

    # ---- hooks (corren en el hilo del mainloop: solo encolar y decidir si tragar)
    def _on_mouse(self, msg, x, y):
        if not self.drawing or self._modal:
            return False
        if msg == win32.WM_LBUTTONDOWN and not self._over_own_ui(x, y):
            if self._pressed:  # si se perdio un UP, cerramos el trazo antes de abrir otro
                self._events.append(("up", x, y))
            self._pressed = True
            self._events.append(("down", x, y))
            return True
        if msg == win32.WM_LBUTTONUP and self._pressed:
            self._pressed = False
            self._events.append(("up", x, y))
            return True
        if msg == win32.WM_MOUSEMOVE and self._pressed:
            self._events.append(("move", x, y))
        return False  # tragarse WM_MOUSEMOVE congela el cursor del sistema

    def _on_key(self, vk):
        if vk == win32.VK_F8:
            self._events.append(("spotlight", 0, 0))
            return True
        if vk == win32.VK_F9:
            self._events.append(("toggle", 0, 0))
            return True
        if vk == win32.VK_F10:
            self._events.append(("clear", 0, 0))
            return True
        if vk == win32.VK_F11:
            self._events.append(("undo", 0, 0))
            return True
        if vk == win32.VK_F12:
            self._events.append(("save", 0, 0))
            return True
        if vk == win32.VK_ESCAPE and self.drawing:
            self._events.append(("stop", 0, 0))
        return False

    def _over_own_ui(self, x, y):
        """La barra y el aviso reciben clicks normales; el overlay no cuenta, ahi se dibuja."""
        return win32.top_window_at(x, y) in self._ui_hwnds

    # ---- bucles
    def _drain(self):
        actions = {"clear": self.clear, "undo": self.undo, "save": self.save_shot,
                   "toggle": self.toggle_drawing, "spotlight": self.toggle_spotlight,
                   "stop": lambda: self.set_drawing(False)}
        while self._events:
            kind, sx, sy = self._events.popleft()
            if kind in actions:
                actions[kind]()
                continue
            x, y = self.overlay.to_canvas(sx, sy)  # de coords de pantalla a coords del canvas
            if kind == "down":
                self.board.down(x, y)
            elif kind == "move":
                self.board.move(x, y)
            elif kind == "up":
                self.board.up(x, y)
        if self._shot_result:  # tk solo se toca desde su hilo, por eso lo recogemos aqui
            self._announce_shot()
        self.root.after(DRAIN_MS, self._drain)

    def _follow_cursor(self):
        if self.spotlight.enabled:
            self.spotlight.move_to(*self.overlay.to_canvas(*win32.cursor_pos()))
            self.root.after(CURSOR_MS, self._follow_cursor)

    def _keep_on_top(self):
        if not self._modal:  # un lift aqui taparia el dialogo de color
            self.overlay.lift()
            self.root.lift()
            self.toast.lift()
        self.toolbar.pin()
        self.root.after(LIFT_MS, self._keep_on_top)

    def _refresh(self):
        self.toolbar.refresh(self)

    def _place_toolbar(self):
        self.root.update()  # sin la ventana ya mapeada, geometry() se ignora
        ax, ay, aw, ah = self.work
        width = max(self.root.winfo_width(), self.root.winfo_reqwidth())
        height = max(self.root.winfo_height(), self.root.winfo_reqheight())
        self.toolbar.place(ax + aw - width - 24, ay + (ah - height) // 2)

    def run(self):
        self._ui_hwnds = {win32.top_window_of(self.root), win32.top_window_of(self.toast.win)}
        self.hooks.install()
        self.set_drawing(False)
        self._place_toolbar()
        self._drain()
        self._keep_on_top()
        try:
            self.root.mainloop()
        finally:
            self.hooks.uninstall()
