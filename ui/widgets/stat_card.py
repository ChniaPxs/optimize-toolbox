
# -*- coding: utf-8 -*-
"""状态卡片组件"""
import tkinter as tk
from config import CLR, FONT_SUBTITLE, FONT_NUM

class StatCard(tk.Frame):
    def __init__(self, parent, title="", value="", icon="", unit="", **kwargs):
        super().__init__(parent, bg=CLR["bg_card"], highlightthickness=1, highlightbackground=CLR["border"])
        self.title = title
        self.value = value
        self.icon = icon
        self.unit = unit
        self._build()

    def _build(self):
        # 顶部图标+标题
        top = tk.Frame(self, bg=CLR["bg_card"])
        top.pack(fill=tk.X, padx=12, pady=(10, 4))
        tk.Label(top, text=self.icon, font=FONT_SUBTITLE, bg=CLR["bg_card"], fg=CLR["cyan"]).pack(side=tk.LEFT)
        tk.Label(top, text="  " + self.title, font=FONT_SUBTITLE, bg=CLR["bg_card"], fg=CLR["text_dim"]).pack(side=tk.LEFT)
        # 数值
        val_text = self.value + (" " + self.unit if self.unit else "")
        tk.Label(self, text=val_text, font=FONT_NUM, bg=CLR["bg_card"], fg=CLR["text"]).pack(pady=(0, 10), padx=12, anchor=tk.W)

    def update(self, value, unit=""):
        self.value = value
        self.unit = unit
        val_text = value + (" " + unit if unit else "")
        for w in self.winfo_children():
            if isinstance(w, tk.Frame): continue
            if isinstance(w, tk.Label) and w.cget("font") == FONT_NUM:
                w.config(text=val_text)
                break
