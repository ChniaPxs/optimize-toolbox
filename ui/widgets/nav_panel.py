
# -*- coding: utf-8 -*-
"""侧边栏导航组件"""
import tkinter as tk
from config import CLR, FONT_SUBTITLE

class NavPanel(tk.Frame):
    def __init__(self, parent, items=None, on_select=None, **kwargs):
        super().__init__(parent, bg=CLR["bg_main"], width=200, **kwargs)
        self.items = items or []
        self.on_select = on_select
        self._btns = {}
        self._build()

    def _build(self):
        self.pack_propagate(False)
        # Logo
        tk.Label(self, text="⚡ 优化工具箱", font=("Microsoft YaHei UI", 13, "bold"),
                 bg=CLR["bg_main"], fg=CLR["cyan"]).pack(pady=(16, 4), anchor=tk.W, padx=16)
        tk.Label(self, text="PC + 手机 统一优化", font=FONT_SUBTITLE,
                 bg=CLR["bg_main"], fg=CLR["text_muted"]).pack(anchor=tk.W, padx=16, pady=(0, 12))
        # Divider
        tk.Frame(self, bg=CLR["border"], height=1).pack(fill=tk.X, padx=16)
        # Nav items
        for text, page_id in self.items:
            btn = NavButton(self, text=text, page_id=page_id, command=lambda pid=page_id: self.on_select(pid) if self.on_select else None)
            btn.pack(fill=tk.X, pady=1)
            self._btns[page_id] = btn

    def select(self, page_id):
        for pid, btn in self._btns.items():
            btn.select(pid == page_id)

class NavButton(tk.Frame):
    def __init__(self, parent, text="", page_id="", command=None, **kwargs):
        super().__init__(parent, bg=CLR["bg_main"], height=42, **kwargs)
        self.pack_propagate(False)
        self.page_id = page_id
        self.selected = False
        # Indicator
        self.indicator = tk.Frame(self, bg=CLR["cyan"], width=3)
        self.indicator.pack(side=tk.LEFT, fill=tk.Y)
        # Content
        content = tk.Frame(self, bg=CLR["bg_main"])
        content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.label = tk.Label(content, text="  " + text, font=FONT_SUBTITLE,
                              bg=CLR["bg_main"], fg=CLR["text_dim"], anchor=tk.W)
        self.label.pack(fill=tk.X, padx=12, pady=9)
        self.bind("<Enter>", lambda e: self.config(bg=CLR["bg_hover"]) if not self.selected else None)
        self.bind("<Leave>", lambda e: self.config(bg=CLR["bg_main"]) if not self.selected else None)
        self.bind("<Button-1>", lambda e: command() if command else None)

    def select(self, on):
        self.selected = on
        self.config(bg=CLR["bg_main"] if not on else CLR["bg_card"])
        self.indicator.config(bg=CLR["cyan"] if on else "transparent")
        self.label.config(fg=CLR["cyan"] if on else CLR["text_dim"])