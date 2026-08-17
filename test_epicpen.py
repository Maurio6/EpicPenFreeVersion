"""python test_epicpen.py -- checks sin framework: modelo, halo, PNG y multi-monitor."""
import struct
import zlib

from epicpen import capture
from epicpen.board import ERASER, MARKER, OVAL, PEN, Board
from epicpen.spotlight import RADIUS, Spotlight


class FakeCanvas:
    def __init__(self):
        self.items, self.n = {}, 0

    def _add(self, kind, args, kw):
        self.n += 1
        self.items[self.n] = (kind, args, kw)
        return self.n

    def create_line(self, *a, **k):
        return self._add("line", a, k)

    def create_rectangle(self, *a, **k):
        return self._add("rect", a, k)

    def create_oval(self, *a, **k):
        return self._add("oval", a, k)

    def create_polygon(self, *a, **k):
        return self._add("polygon", a, k)

    def delete(self, i):
        if i == "all":
            self.items.clear()
        elif isinstance(i, str):
            for k in [k for k in self.items if i in self.gettags(k)]:
                del self.items[k]
        else:
            self.items.pop(i, None)

    def gettags(self, i):
        tags = self.items.get(i, ("", (), {}))[2].get("tags", ())
        return (tags,) if isinstance(tags, str) else tuple(tags)

    def coords(self, i, *box):
        self.items[i] = self.items[i][:1] + (box,) + self.items[i][2:]

    def find_overlapping(self, *box):
        return tuple(self.items)


def check_board():
    c = FakeCanvas()
    b = Board(c)

    b.down(0, 0); b.move(10, 10); b.move(20, 20); b.up(20, 20)
    assert len(c.items) == 2 and len(b.strokes) == 1, c.items

    b.down(50, 50); b.up(50, 50)                       # click seco = un punto
    assert len(c.items) == 3, c.items
    b.undo()
    assert len(c.items) == 2 and len(b.strokes) == 1

    b.mode = MARKER
    b.down(0, 0); b.move(5, 5); b.up(5, 5)
    assert c.items[c.n][2]["stipple"] == "gray50"      # resaltador = trazo con trama

    b.mode = OVAL                                      # la forma deja un item, sin rastro del preview
    before = len(c.items)
    b.down(0, 0); b.move(10, 10); b.move(30, 30); b.up(30, 30)
    assert len(c.items) == before + 1 and c.items[c.n][0] == "oval", c.items

    b.mode = OVAL                                      # forma sin arrastre no crea nada
    before = len(c.items)
    b.down(1, 1); b.up(1, 1)
    assert len(c.items) == before

    b.mode = ERASER                                    # la goma borra y no abre trazo nuevo
    strokes = len(b.strokes)
    b.down(0, 0)
    assert c.items == {} and len(b.strokes) == strokes

    b.mode = PEN
    b.down(0, 0); b.move(1, 1); b.clear()
    assert not c.items and not b.strokes


def check_spotlight():
    c = FakeCanvas()
    b = Board(c)
    spot = Spotlight(c)                                # el halo no es tinta: goma y limpiar lo respetan
    spot.move_to(100, 100)
    halo = c.n
    b.mode = PEN; b.down(100, 100); b.move(110, 110); b.up(110, 110)
    b.mode = ERASER; b.down(100, 100)
    assert list(c.items) == [halo], c.items
    b.clear()
    assert list(c.items) == [halo]
    spot.move_to(200, 200)                             # mover no crea otro item, solo mueve
    assert list(c.items) == [halo]
    assert c.items[halo][1][:2] == (200 + RADIUS, 200.0), c.items[halo][1][:2]


def _png_chunks(png):
    out, i = {}, 8
    while i < len(png):
        size = struct.unpack(">I", png[i:i + 4])[0]
        tag, data = png[i + 4:i + 8], png[i + 8:i + 8 + size]
        crc = struct.unpack(">I", png[i + 8 + size:i + 12 + size])[0]
        assert crc == zlib.crc32(tag + data) & 0xFFFFFFFF, tag
        out[tag] = data
        i += 12 + size
    return out


def check_png():
    rgba = bytes([255, 0, 0, 255,  0, 255, 0, 255,        # 2x2
                  0, 0, 255, 255,  255, 255, 255, 255])
    png = capture.encode_png(2, 2, rgba)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    parts = _png_chunks(png)
    assert struct.unpack(">IIBB", parts[b"IHDR"][:10]) == (2, 2, 8, 6)
    assert parts[b"IEND"] == b""
    # cada fila va precedida por su byte de filtro (0 = sin filtro)
    assert zlib.decompress(parts[b"IDAT"]) == b"\x00" + rgba[:8] + b"\x00" + rgba[8:]


def check_virtual_desktop_offset():
    """Con un monitor a la izquierda el escritorio empieza en negativo: los puntos
    del hook (coords de pantalla) tienen que aterrizar bien en el canvas."""
    from epicpen.app import App
    a = App()
    try:
        a.overlay.origin = (-1920, -200)
        a._events.extend([("down", -1900, -150), ("move", -1880, -100), ("up", -1880, -100)])
        a._drain()
        assert a.overlay.canvas.coords(a.board.strokes[-1][0]) == [20.0, 50.0, 40.0, 100.0]
    finally:
        a.quit()


def check_lost_button_up():
    """Si un LBUTTONUP se pierde, el siguiente click tiene que cerrar el trazo abierto
    antes de empezar el nuevo, o los dos quedarian unidos en uno solo."""
    from epicpen import win32
    from epicpen.app import App
    a = App()
    try:
        a.drawing = True
        a._pressed = True                              # como si el UP no hubiera llegado
        a._events.clear()
        assert a._on_mouse(win32.WM_LBUTTONDOWN, 500, 500) is True
        assert list(a._events) == [("up", 500, 500), ("down", 500, 500)], list(a._events)

        a._events.clear()                              # el movimiento nunca se traga
        assert a._on_mouse(win32.WM_MOUSEMOVE, 510, 510) is False
        assert list(a._events) == [("move", 510, 510)]
    finally:
        a.quit()


def check_backdrop():
    """La pizarra va debajo de la tinta y no la borran ni la goma ni "limpiar"."""
    from epicpen.app import App
    a = App()
    try:
        canvas = a.overlay.canvas
        a.board.down(10, 10); a.board.move(60, 60); a.board.up(60, 60)
        tinta = a.board.strokes[-1][0]

        a.cycle_backdrop()
        assert a.backdrop == "dark"
        fondo = a.overlay._backdrop
        assert canvas.find_all()[0] == fondo, "la pizarra tapa la tinta que ya estaba"

        a.board.mode = "eraser"; a.board.down(10, 10)   # borra tinta, no la pizarra
        assert fondo in canvas.find_all() and tinta not in canvas.find_all()
        a.board.clear()
        assert canvas.find_all() == (fondo,)

        a.cycle_backdrop()
        assert a.backdrop == "light" and len(canvas.find_all()) == 1
        a.cycle_backdrop()
        assert a.backdrop is None and canvas.find_all() == ()
    finally:
        a.quit()


def check_toolbar_stays_on_screen():
    """Al arrancar tiene que caber entera, y ni arrastrandola debe poder salirse."""
    from epicpen.app import App
    a = App()
    try:
        a._place_toolbar()
        ax, ay, aw, ah = a.work
        w = a.root.winfo_reqwidth()
        h = a.root.winfo_reqheight()
        assert h <= ah, f"la barra mide {h} y solo hay {ah} de alto util"
        for x, y in [(ax + aw - w - 24, ay + (ah - h) // 2), (9999, 9999), (-500, -500)]:
            a.toolbar.place(x, y)
            px, py = a.toolbar._pos
            assert ax <= px and px + w <= ax + aw, (px, w)
            assert ay <= py and py + h <= ay + ah, (py, h, ah)
    finally:
        a.quit()


def main():
    check_board()
    check_spotlight()
    check_png()
    check_virtual_desktop_offset()
    check_lost_button_up()
    check_backdrop()
    check_toolbar_stays_on_screen()
    print("ok")


if __name__ == "__main__":
    main()
