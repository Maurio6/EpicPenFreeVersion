"""Ventana transparente que cubre todos los monitores; ahi vive la tinta.

El fondo usa un color-key: Windows lo vuelve invisible y ademas deja pasar los
clicks, por eso el dibujo se alimenta de los hooks globales y no de eventos de tk.
"""
import tkinter as tk

TRANSPARENT_KEY = "#010203"


class Overlay:
    def __init__(self, master, rect):
        x, y, w, h = rect
        self.origin = (x, y)
        self.win = tk.Toplevel(master)
        self.win.overrideredirect(True)
        self.win.geometry("%dx%d+%d+%d" % (w, h, x, y))
        self.win.attributes("-topmost", True)
        self.win.attributes("-transparentcolor", TRANSPARENT_KEY)
        self.canvas = tk.Canvas(self.win, bg=TRANSPARENT_KEY, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

    def to_canvas(self, x, y):
        """Los hooks dan coords de pantalla; el canvas empieza en la esquina virtual."""
        return x - self.origin[0], y - self.origin[1]

    def lift(self):
        self.win.lift()
