"""Barra flotante estilo Epic Pen: vertical, oscura, sin bordes y arrastrable."""
import tkinter as tk

from .board import ERASER, LINE, MARKER, OVAL, PEN, RECT

BG = "#1b1d22"
FG = "#c9ccd3"
HOVER = "#2b2f38"
ACTIVE = "#e5484d"
SEP = "#33373f"
PANEL = "#23262c"

COLORS = ["#ff2d2d", "#ff9f1c", "#ffd400", "#31d843",
          "#22d3ee", "#2f8bff", "#c06bff", "#ffffff", "#000000"]
WIDTHS = [2, 4, 8, 16]
SHAPE_GLYPHS = [(LINE, "╱"), (RECT, "▭"), (OVAL, "◯")]
FONT = ("Segoe UI Symbol", 13)


class Toolbar:
    """Vista pura: dibuja controles y llama al controlador (app). No guarda estado."""

    def __init__(self, win, app, area):
        self.win, self.app = win, app
        self.area = area          # zona util de la pantalla: la barra nunca sale de aqui
        self.mode_buttons = {}
        self._shape_idx = 0
        self._drag = (0, 0)
        self._pos = None

        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.configure(bg=BG)

        grip = tk.Label(win, text="≡", bg=BG, fg="#6b7280",
                        font=("Segoe UI Symbol", 11), cursor="fleur", pady=3)
        grip.pack(fill="x")
        grip.bind("<Button-1>", self._drag_start)
        grip.bind("<B1-Motion>", self._drag_move)

        self._sep()
        self._mode_button(PEN, "✎", "Lapiz")
        self._mode_button(MARKER, "▨", "Resaltador")
        self.shape_button = self._button(SHAPE_GLYPHS[0][1], self._shape_click,
                                         "Formas (click de nuevo para cambiar)")
        for mode, _ in SHAPE_GLYPHS:
            self.mode_buttons[mode] = self.shape_button
        self._mode_button(ERASER, "⌫", "Goma")

        self._sep()
        self.swatch = tk.Label(win, bg=BG, pady=6, cursor="hand2")
        self.swatch.pack(fill="x")
        self.swatch.bind("<Button-1>", lambda e: self.toggle_panel())
        self.panel = self._build_panel()
        self.panel.pack(fill="x")  # abierto de entrada: si no, nadie descubre los colores

        self._sep()
        self.board_button = self._button("▦", app.cycle_backdrop,
                                         "Pizarra: oscura / clara / apagada (F7)")
        self.spot_button = self._button("◎", app.toggle_spotlight, "Resaltar el puntero (F8)")
        self._button("↶", app.undo, "Deshacer (F11)")
        self._button("⊘", app.clear, "Limpiar todo (F10)")
        self.save_button = self._button("⬇", app.save_shot,
                                        "Guardar PNG en Imagenes\\EpicPen (F12)")

        self._sep()
        self.toggle_button = self._button("◉", app.toggle_drawing, "Dibujar / Click (F9)")
        self._button("✕", app.quit, "Salir")

    # ---- construccion
    def _sep(self):
        tk.Frame(self.win, height=1, bg=SEP).pack(fill="x", padx=4, pady=2)

    def _button(self, glyph, command, tip="", parent=None):
        b = tk.Label(parent or self.win, text=glyph, bg=BG, fg=FG, font=FONT,
                     width=2, pady=5, cursor="hand2")
        b.pack(fill="x")
        b.bind("<Button-1>", lambda e: command())
        b.bind("<Enter>", lambda e: b.config(bg=HOVER) if b["bg"] == BG else None)
        b.bind("<Leave>", lambda e: b.config(bg=BG) if b["bg"] == HOVER else None)
        if tip:
            _tooltip(b, tip)
        return b

    def _mode_button(self, mode, glyph, tip):
        b = self._button(glyph, lambda m=mode: self.app.set_mode(m), tip)
        self.mode_buttons[mode] = b
        return b

    def _build_panel(self):
        panel = tk.Frame(self.win, bg=PANEL)
        grid = tk.Frame(panel, bg=PANEL)
        grid.pack(padx=5, pady=(5, 2))
        for i, color in enumerate(COLORS):
            sw = tk.Label(grid, bg=color, width=1, height=1, cursor="hand2",
                          highlightthickness=1, highlightbackground=SEP)
            sw.grid(row=i // 3, column=i % 3, padx=1, pady=1)
            sw.bind("<Button-1>", lambda e, c=color: self.app.set_color(c))

        more = tk.Label(grid, text="+", bg=PANEL, fg=FG, width=1, height=1,
                        font=("Segoe UI", 9, "bold"), cursor="hand2",
                        highlightthickness=1, highlightbackground=SEP)
        more.grid(row=len(COLORS) // 3, column=len(COLORS) % 3, padx=1, pady=1)
        more.bind("<Button-1>", lambda e: self.app.pick_color())
        _tooltip(more, "Cualquier otro color")

        sizes = tk.Frame(panel, bg=PANEL)
        sizes.pack(padx=5, pady=(2, 5))
        for w in WIDTHS:
            c = tk.Canvas(sizes, width=12, height=18, bg=PANEL, highlightthickness=0,
                          cursor="hand2")
            r = min(w, 10) / 2
            c.create_oval(6 - r, 9 - r, 6 + r, 9 + r, fill=FG, outline="")
            c.pack()
            c.bind("<Button-1>", lambda e, w=w: self.app.set_width(w))
        return panel

    # ---- posicion
    def place(self, x, y):
        self._pos = self._clamp(x, y)
        self.win.geometry("+%d+%d" % self._pos)

    def pin(self):
        """Tk reubica a +0+0 la ventana sin bordes cada vez que cambia de tamano, y al
        desplegar la paleta puede crecer hasta salirse: recolocar cubre ambos casos."""
        if self._pos:
            self.place(*self._pos)

    def _clamp(self, x, y):
        ax, ay, aw, ah = self.area
        self.win.update_idletasks()
        w = max(self.win.winfo_width(), self.win.winfo_reqwidth())
        h = max(self.win.winfo_height(), self.win.winfo_reqheight())
        x = min(max(x, ax), ax + aw - w)
        y = ay if h >= ah else min(max(y, ay), ay + ah - h)
        return x, y

    # ---- interaccion
    def toggle_panel(self):
        if self.panel.winfo_ismapped():
            self.panel.pack_forget()
        else:
            self.panel.pack(fill="x", after=self.swatch)
        self.win.after_idle(self.pin)

    def flash_save(self, saved):
        """Sin esto no hay forma de saber si la captura se escribio o fallo."""
        self.save_button.config(bg="#31d843" if saved else ACTIVE, fg="#000000")
        self.win.after(1200, lambda: self.save_button.config(bg=BG, fg=FG))

    def _shape_click(self):
        """Primer click selecciona la forma; los siguientes ciclan linea/rect/elipse."""
        if self.app.mode == SHAPE_GLYPHS[self._shape_idx][0]:
            self._shape_idx = (self._shape_idx + 1) % len(SHAPE_GLYPHS)
        mode, glyph = SHAPE_GLYPHS[self._shape_idx]
        self.shape_button.config(text=glyph)
        self.app.set_mode(mode)

    def _drag_start(self, e):
        self._drag = (e.x_root - self.win.winfo_x(), e.y_root - self.win.winfo_y())

    def _drag_move(self, e):
        dx, dy = self._drag
        self.place(e.x_root - dx, e.y_root - dy)

    # ---- estado
    def refresh(self, app):
        for mode, b in self.mode_buttons.items():
            active = mode == app.mode and app.drawing
            b.config(bg=ACTIVE if active else BG, fg="#ffffff" if active else FG)
        self.swatch.config(bg=app.color, text="▬" * max(1, app.width // 4),
                           fg="#000000" if app.color.lower() in ("#ffffff", "#fff") else "#ffffff",
                           font=("Segoe UI Symbol", 7))
        self.spot_button.config(bg=ACTIVE if app.spotlight_on else BG,
                                fg="#ffffff" if app.spotlight_on else FG)
        # el propio boton se pinta del color de la pizarra: se ve cual esta puesta
        board_look = {None: (BG, FG), "dark": ("#101216", "#ffffff"),
                      "light": ("#f7f5f0", "#101216")}[app.backdrop]
        self.board_button.config(bg=board_look[0], fg=board_look[1])
        self.toggle_button.config(text="◉" if app.drawing else "○",
                                  fg="#31d843" if app.drawing else FG)
        self.win.after_idle(self.pin)


def _tooltip(widget, text):
    tip = {"win": None}

    def show(_e):
        if tip["win"]:
            return
        t = tk.Toplevel(widget)
        t.overrideredirect(True)
        t.attributes("-topmost", True)
        tk.Label(t, text=text, bg="#101216", fg=FG, font=("Segoe UI", 8),
                 padx=6, pady=2).pack()
        t.geometry(f"+{widget.winfo_rootx() - t.winfo_reqwidth() - 8}"
                   f"+{widget.winfo_rooty()}")
        tip["win"] = t

    def hide(_e):
        if tip["win"]:
            tip["win"].destroy()
            tip["win"] = None

    widget.bind("<Enter>", show, add="+")
    widget.bind("<Leave>", hide, add="+")
