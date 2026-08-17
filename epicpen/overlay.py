"""Ventana transparente que cubre todos los monitores; ahi vive la tinta.

El fondo usa un color-key: Windows lo vuelve invisible y ademas deja pasar los
clicks, por eso el dibujo se alimenta de los hooks globales y no de eventos de tk.
"""
import tkinter as tk

TRANSPARENT_KEY = "#010203"
BACKDROPS = {"dark": "#101216", "light": "#f7f5f0"}


class Overlay:
    def __init__(self, master, rect):
        x, y, w, h = rect
        self.origin = (x, y)
        self.size = (w, h)
        self._backdrop = None
        self.win = tk.Toplevel(master)
        self.win.overrideredirect(True)
        self.win.geometry("%dx%d+%d+%d" % (w, h, x, y))
        self.win.attributes("-topmost", True)
        self.win.attributes("-transparentcolor", TRANSPARENT_KEY)
        self.canvas = tk.Canvas(self.win, bg=TRANSPARENT_KEY, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

    def set_backdrop(self, name):
        """Fondo opaco a pantalla completa: convierte el overlay en una pizarra.

        Va siempre al fondo del canvas, asi la tinta que ya habia sigue encima, y
        no lleva el tag de tinta para que la goma y "limpiar" no se lo lleven.
        """
        if self._backdrop is not None:
            self.canvas.delete(self._backdrop)
            self._backdrop = None
        color = BACKDROPS.get(name)
        if color:
            w, h = self.size
            self._backdrop = self.canvas.create_rectangle(0, 0, w, h, fill=color,
                                                          outline=color)
            self.canvas.tag_lower(self._backdrop)

    def to_canvas(self, x, y):
        """Los hooks dan coords de pantalla; el canvas empieza en la esquina virtual."""
        return x - self.origin[0], y - self.origin[1]

    def lift(self):
        self.win.lift()
