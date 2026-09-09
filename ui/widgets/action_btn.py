
# -*- coding: utf-8 -*-
"""操作按钮组件"""
import tkinter as tk
from config import CLR, FONT_SUBTITLE

class ActionBtn(tk.Frame):
    def __init__(self, parent, text="", icon="", command=None, bg_color=None, fg_color="white", **kwargs):
        color = bg_color or CLR["accent"]
        super().__init__(parent, bg=color, highlightthickness=1, highlightbackground=color)
        self.config(cursor="hand2")
        self._orig_color = color
        self.bind("<Enter>", lambda e: self.config(bg=self._lighten(color)))
        self.bind("<Leave>", lambda e: self.config(bg=color))
        self.bind("<Button-1>", lambda e: command() if command else None)
        tk.Label(self, text=(icon + "  " if icon else "") + text,
                 font=FONT_SUBTITLE, bg=color, fg=fg_color).pack(padx=14, pady=8)

    def _lighten(self, hex_color):
        hex_color = hex_color.lstrip("#")
        r = min(255, int(hex_color[0:2], 16) + 30)
        g = min(255, int(hex_color[2:4], 16) + 30)
        b = min(255, int(hex_color[4:6], 16) + 30)
        return "#{:02x}{:02x}{:02x}".format(r, g, b)
