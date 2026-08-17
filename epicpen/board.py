"""Modelo de dibujo: trazos, formas, goma y deshacer.

No depende de tkinter: recibe cualquier objeto con la API de Canvas
(create_line / create_rectangle / create_oval / delete / find_overlapping).
"""

PEN, MARKER, ERASER, LINE, RECT, OVAL = "pen", "marker", "eraser", "line", "rect", "oval"
SHAPES = (LINE, RECT, OVAL)
ERASER_RADIUS = 20
INK = "ink"  # solo lo marcado asi se borra; lo demas (el halo del puntero) sobrevive


class Board:
    def __init__(self, canvas):
        self.c = canvas
        self.strokes = []          # cada trazo es una lista de ids -> pila de deshacer
        self.color = "#ff2d2d"
        self.width = 4
        self.mode = PEN
        self._cur = None
        self._last = None
        self._start = None
        self._preview = None

    # ---- gestos
    def down(self, x, y):
        self._start = self._last = (x, y)
        self._cur = None
        if self.mode == ERASER:
            self._erase(x, y)
        elif self.mode not in SHAPES:
            self._cur = []
            self.strokes.append(self._cur)

    def move(self, x, y):
        if self._start is None:
            return
        if self.mode == ERASER:
            self._erase(x, y)
        elif self.mode in SHAPES:
            if self._preview is not None:
                self.c.delete(self._preview)
            self._preview = self._draw_shape(x, y)
        else:
            lx, ly = self._last
            self._cur.append(self.c.create_line(lx, ly, x, y, **self._style()))
        self._last = (x, y)

    def up(self, x, y):
        if self._start is None:
            return
        if self.mode in SHAPES:
            if self._preview is not None:
                self.c.delete(self._preview)
            self._preview = None
            if (x, y) != self._start:
                self.strokes.append([self._draw_shape(x, y)])
        elif self._cur is not None and not self._cur:
            self.move(x + 1, y + 1)  # click seco = punto
        self._cur = self._last = self._start = None

    # ---- acciones
    def undo(self):
        while self.strokes:
            ids = self.strokes.pop()
            for i in ids:
                self.c.delete(i)
            if ids:
                return

    def clear(self):
        self.c.delete(INK)
        self.strokes.clear()
        self._cur = self._last = self._start = self._preview = None

    # ---- interno
    def _style(self):
        kw = dict(fill=self.color, width=self.width, capstyle="round", smooth=True, tags=INK)
        if self.mode == MARKER:
            # ponytail: el canvas de tk no da alpha por item; stipple hace de resaltador
            kw.update(width=self.width * 5, stipple="gray50")
        return kw

    def _draw_shape(self, x, y):
        x0, y0 = self._start
        if self.mode == LINE:
            return self.c.create_line(x0, y0, x, y, fill=self.color, width=self.width,
                                      capstyle="round", tags=INK)
        create = self.c.create_rectangle if self.mode == RECT else self.c.create_oval
        return create(x0, y0, x, y, outline=self.color, width=self.width, tags=INK)

    def _erase(self, x, y):
        r = ERASER_RADIUS
        for i in self.c.find_overlapping(x - r, y - r, x + r, y + r):
            if INK in self.c.gettags(i):
                self.c.delete(i)
