"""Halo que sigue al puntero, para senalar cosas sin dibujar.

Vive en el canvas del overlay pero sin el tag de tinta, asi la goma y "limpiar"
no se lo llevan por delante.
"""
import math

RADIUS = 42
COLOR = "#ffd400"
SIDES = 36

# ponytail: circulo como poligono, no como oval. Tk en Windows ignora el stipple al
# rellenar un oval (sale opaco y tapa el texto) pero si lo respeta en poligonos.
_UNIT = [(math.cos(a), math.sin(a)) for a in
         (i * 2 * math.pi / SIDES for i in range(SIDES))]


def _points(x, y):
    return [c for ux, uy in _UNIT for c in (x + ux * RADIUS, y + uy * RADIUS)]


class Spotlight:
    def __init__(self, canvas):
        self.c = canvas
        self.enabled = False
        self._item = None

    def toggle(self):
        self.enabled = not self.enabled
        if not self.enabled:
            self.hide()
        return self.enabled

    def hide(self):
        if self._item is not None:
            self.c.delete(self._item)
            self._item = None

    def move_to(self, x, y):
        pts = _points(x, y)
        if self._item is None:
            self._item = self.c.create_polygon(*pts, fill=COLOR, stipple="gray25",
                                               outline=COLOR, width=3)
        else:
            self.c.coords(self._item, *pts)
