# -*- coding: utf-8 -*-
"""页面基类（Canvas 原生皮肤版）

页面本身是 Canvas：底层绘制窗口背景图的对应片段，UI 元素（标题/卡片/按钮/文字）
用 Canvas 原语直接画在背景之上——背景图与控件同窗口原生渲染，控件即图上的像素，
任何位置都能透出背景插画。窗口缩放时由主程序统一重绘。
"""
import tkinter as tk
from config import FADE_MS

_BG_FALLBACK = "#dceafc"


class BasePage(tk.Canvas):
    def __init__(self, parent, **kwargs):
        kwargs.pop("bg", None)
        allowed = {}
        for k in ("width", "height", "cursor", "takefocus", "confine",
                  "scrollregion", "xscrollincrement", "yscrollincrement"):
            if k in kwargs:
                allowed[k] = kwargs.pop(k)
        super().__init__(parent, bg=_BG_FALLBACK, highlightthickness=0, bd=0,
                         relief="flat", **allowed)
        self._fade_id = None
        self._opacity = 0
        self._bg_photo = None
        self._win_x = 0
        self._win_y = 0

    # ---------- 绘制 ----------
    def redraw(self, bg_photo, win_x, win_y):
        """清除并重绘：背景图 + 页面内容（子类实现 _draw）"""
        self._bg_photo = bg_photo
        self._win_x = win_x
        self._win_y = win_y
        self.delete("all")
        try:
            from ui import background
            background.paint(self, bg_photo, win_x, win_y)
        except Exception:
            pass
        try:
            self._draw()
        except Exception:
            pass

    def _draw(self):
        """子类绘制页面内容"""

    def page_w(self):
        return max(50, self.winfo_width())

    def page_h(self):
        return max(50, self.winfo_height())

    # ---------- 淡入淡出（保留接口） ----------
    def _fade_in(self):
        if self._opacity < 1.0:
            self._opacity += 0.15
            if self._opacity > 1.0:
                self._opacity = 1.0
            self._fade_id = self.after(FADE_MS // 6, self._fade_in)
        else:
            self._fade_id = None

    def on_show(self):
        self._opacity = 0
        self._fade_in()

    def on_hide(self):
        if self._fade_id:
            self.after_cancel(self._fade_id)
            self._fade_id = None

    def destroy(self):
        if self._fade_id:
            self.after_cancel(self._fade_id)
        super().destroy()
