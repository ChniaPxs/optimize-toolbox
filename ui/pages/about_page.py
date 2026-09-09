# -*- coding: utf-8 -*-
"""关于页面（Canvas 原生皮肤版）"""
import tkinter as tk
from .base_page import BasePage
from .. import theme as T
from ui.theme import CYAN, GREEN, PURPLE, ORANGE, TEXT, TEXT_DIM, TEXT_MUT, BORDER


class AboutPage(BasePage):
    def __init__(self, parent, app=None, **kwargs):
        self._app = app
        super().__init__(parent, **kwargs)
        self._draw()

    def _draw(self):
        cv = self
        w = self.page_w()
        T.CanvasBtn(cv, 22, 20, 74, 30, "‹ 返回", BORDER, self._go_back,
                    size=10, radius=12)
        T.c_titlebar(cv, 22, 78, "关于", "优化工具箱 · PC + 手机统一优化", CYAN)
        y = 124
        # 版本横幅
        T.c_card(cv, 22, y, w - 44, 50)
        T.c_text(cv, 40, y + 25, "⚡ 优化工具箱 v6.1", size=16, bold=True, color=CYAN)
        T.c_text(cv, w - 40, y + 25, "Canvas 原生皮肤 · 构建 " + getattr(self._app, "BUILD_TS", "?"),
                 size=10, color=TEXT_MUT, anchor="e")
        y = self._section(cv, y + 64, "核心功能", CYAN, [
            "PC 网络优化（TCP/IP / DNS / 场景模式）",
            "智能垃圾清理（系统 / 浏览器 / 重复 / 大文件）",
            "性能实时监控（CPU / 内存 / 磁盘 / 电池）",
            "ADB 手机端管理（连接 / 优化 / 清理）",
        ])
        y = self._section(cv, y, "技术栈", PURPLE, [
            "Python 3.10+ / tkinter",
            "psutil 系统监控",
            "ADB Android Debug Bridge",
        ])
        y = self._section(cv, y, "特性", GREEN, [
            "PC + 手机端统一架构",
            "蓝白水彩原生皮肤 UI（背景插画 + Canvas 原生绘制）",
            "实时性能监控与优化建议",
        ])
        y = self._section(cv, y, "运行", ORANGE, [
            "python main.py",
            "依赖: pip install psutil",
        ])

    def _section(self, cv, y, title, color, lines):
        """自适应高度小节：返回下一小节起始 y"""
        h = 22 + 18 * len(lines) + 6
        T.c_section(cv, 22, y + 12, title, color)
        y2 = y + 28
        T.c_card(cv, 22, y2, cv.winfo_width() - 44, h)
        yy = y2 + 18
        for ln in lines:
            T.c_text(cv, 40, yy, "·  " + ln, size=10, color=TEXT_DIM)
            yy += 18
        return y2 + h + 12

    def _go_back(self):
        if self._app:
            self._app.switch_page("home")
