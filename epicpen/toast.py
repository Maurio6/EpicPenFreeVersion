"""Aviso flotante que se cierra solo, para confirmar acciones sin bloquear nada."""
import tkinter as tk

BG = "#23262c"
BORDER = "#3a3f49"
FG = "#e8eaee"
MUTED = "#9aa1ad"
ERROR = "#ff6b6b"
DURATION_MS = 5000


class Toast:
    def __init__(self, master, screen):
        self.screen = screen
        self._timer = None
        self._on_click = None

        self.win = tk.Toplevel(master)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.configure(bg=BORDER)
        body = tk.Frame(self.win, bg=BG)
        body.pack(padx=1, pady=1)
        self.title = tk.Label(body, bg=BG, fg=FG, font=("Segoe UI", 10, "bold"), anchor="w")
        self.title.pack(fill="x", padx=16, pady=(11, 0))
        self.detail = tk.Label(body, bg=BG, fg=MUTED, font=("Segoe UI", 8), anchor="w",
                               justify="left")
        self.detail.pack(fill="x", padx=16, pady=(3, 11))
        for widget in (body, self.title, self.detail):
            widget.bind("<Button-1>", self._clicked)
        self.win.withdraw()

    def show(self, title, detail="", on_click=None, error=False):
        self._on_click = on_click
        cursor = "hand2" if on_click else ""
        self.title.config(text=title, fg=ERROR if error else FG, cursor=cursor)
        self.detail.config(text=detail, cursor=cursor)

        self.win.update_idletasks()
        width, height = self.win.winfo_reqwidth(), self.win.winfo_reqheight()
        self.win.geometry("+%d+%d" % ((self.screen[0] - width) // 2,
                                      self.screen[1] - height - 90))
        self.win.deiconify()
        self.win.lift()
        if self._timer:
            self.win.after_cancel(self._timer)
        self._timer = self.win.after(DURATION_MS, self.hide)

    def hide(self):
        self._timer = None
        self.win.withdraw()

    def lift(self):
        if self.win.winfo_ismapped():
            self.win.lift()

    def _clicked(self, _event):
        callback, self._on_click = self._on_click, None
        self.hide()
        if callback:
            callback()
