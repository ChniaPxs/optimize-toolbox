# -*- coding: utf-8 -*-
"""首页：设备连接 / 一键优化 / 功能入口（Canvas 原生皮肤版）"""
import tkinter as tk
from .base_page import BasePage
from .. import theme as T
from config import ASSETS_DIR
from ui.theme import (ACCENT, CYAN, GREEN, ORANGE, PURPLE, TEXT, TEXT_DIM, TEXT_MUT, BORDER)


class HomePage(BasePage):
    def __init__(self, parent, adb=None, log_widget=None, app=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.adb = adb
        self.log = log_widget
        self._app = app
        self._is_mobile = False
        self._status_item = None
        self._mode_item = None
        self._ind_outer = None
        self._ind_inner = None
        self._dev_img = None
        self._opt_result_item = None
        self._draw()

    def _draw(self):
        cv = self
        w = self.page_w()
        T.c_titlebar(cv, 22, 24, "优化工具箱",
                     "PC + 手机端统一系统优化 · 网络 / 清理 / 监控", CYAN)
        card_w = w - 44

        # ---- 设备卡（两行布局：第一行标题+按钮，第二行状态+模式，任何窗口宽度不重叠）----
        T.c_card(cv, 22, 80, card_w, 58)
        # 设备图标：水彩鲸鱼徽章（与背景同风格，PIL 加载与背景图同一可靠路径）
        try:
            from PIL import Image, ImageTk
            _pimg = Image.open(str(ASSETS_DIR / "icon_dev.png"))
            self._dev_img = ImageTk.PhotoImage(_pimg)
            cv.create_image(46, 104, image=self._dev_img)
            T.c_text(cv, 76, 97, "设备连接", size=11, bold=True, color=CYAN)
        except Exception:
            self._dev_img = None
            T.c_text(cv, 38, 97, "◈  设备连接", size=11, bold=True, color=CYAN)
        T.CanvasBtn(cv, card_w - 220, 86, 100, 30, "↻ 刷新连接", BORDER,
                    self._refresh, size=10, radius=10)
        T.CanvasBtn(cv, card_w - 112, 86, 100, 30, "⇄ 切换设备", BORDER,
                    self._switch_device, size=10, radius=10)
        mobile = bool(self._app and getattr(self._app, "_is_mobile", False))
        self._status_item = T.c_text(cv, 38, 121, "未连接", size=10, color=TEXT_MUT)
        self._mode_item = T.c_text(cv, 118, 121,
                                   "手机模式" if mobile else "电脑模式",
                                   size=10, color=CYAN if mobile else ORANGE)

        # ---- 一键优化（透明描边样式，背景可见）----
        T.CanvasBtn(cv, 22, 154, 270, 48, "⚡ 一键优化（网络 + 性能）", GREEN,
                    self._quick_optimize, size=12, radius=16)

        # ---- 功能入口 ----
        T.c_section(cv, 22, 232, "功能入口", ACCENT)
        y = 260
        entries = [("◈  网络优化", "网速优化 / DNS 切换 / 场景模式", CYAN, "network"),
                   ("⌫  智能清理", "系统垃圾 / 重复文件 / 大文件分析", GREEN, "cleanup"),
                   ("◉  性能监控", "CPU / 内存 / 磁盘 / 电池实时监控", PURPLE, "monitor"),
                   ("✕  应用卸载", "卸载电脑 / 手机已安装应用", ORANGE, "apps")]
        for title, desc, color, pid in entries:
            card = T.c_card(cv, 22, y, card_w, 56)
            # card 必须用默认参数捕获（否则闭包引用循环结束后的最后一张卡，hover 全部错位）
            cv.tag_bind(card, "<Enter>", lambda e, c=color, cd=card: cv.itemconfigure(
                cd, outline=c, width=2))
            cv.tag_bind(card, "<Leave>", lambda e, cd=card: cv.itemconfigure(
                cd, outline=BORDER, width=1))
            cv.tag_bind(card, "<Button-1>", lambda e, p=pid: self._go(p))
            t1 = T.c_text(cv, 40, y + 28, title, size=12, bold=True, color=color)
            t2 = T.c_text(cv, w - 40, y + 28, desc, size=10, color=TEXT_MUT, anchor="e")
            # 文字也绑定点击与 hover（同样用默认参数捕获）
            for it in (t1, t2):
                cv.tag_bind(it, "<Button-1>", lambda e, p=pid: self._go(p))
                cv.tag_bind(it, "<Enter>", lambda e, c=color, cd=card: cv.itemconfigure(
                    cd, outline=c, width=2))
                cv.tag_bind(it, "<Leave>", lambda e, cd=card: cv.itemconfigure(
                    cd, outline=BORDER, width=1))
            y += 72

    def _go(self, page_id):
        if self._app:
            self._app.switch_page(page_id)

    # ---------- 设备 ----------
    def _refresh(self):
        model = "未连接"
        color = TEXT_MUT
        ind = "#8A8A8A"
        try:
            if self.adb and self.adb.connect():
                model = "已连接"
                color = GREEN
                ind = GREEN
        except Exception:
            pass
        if self._status_item:
            self.itemconfigure(self._status_item, text=model, fill=color)
        # 指示灯同步变色：外圈描边 + 内圈实心
        if self._ind_outer:
            self.itemconfigure(self._ind_outer, outline=ind)
        if self._ind_inner:
            self.itemconfigure(self._ind_inner, fill=ind)

    def _switch_device(self):
        if self._app:
            self._app._is_mobile = not self._app._is_mobile
            mobile = self._app._is_mobile
            if self._mode_item:
                self.itemconfigure(self._mode_item,
                                   text="手机模式" if mobile else "电脑模式",
                                   fill=CYAN if mobile else ORANGE)
            if hasattr(self._app, "_paint_header"):
                try:
                    self._app._paint_header()  # 顶栏设备指示同步
                except Exception:
                    pass
            if hasattr(self._app, "_term_log"):
                self._app._term_log("设备模式切换: " + ("手机" if mobile else "电脑"), CYAN)

    def _quick_optimize(self):
        if not self._app:
            return
        # 点击后立即给出手感反馈
        if self._opt_result_item:
            self.itemconfigure(self._opt_result_item, text="正在优化中...", fill=ORANGE)
        else:
            self._opt_result_item = T.c_text(self, 36, 216, "正在优化中...",
                                             size=10, color=ORANGE, anchor="w")
        # 结果异步返回后更新
        import threading
        def _work():
            try:
                r = self._app.quick_optimize()
            except Exception as e:
                r = None
            self.after(0, lambda: self._show_opt_result(r))
        threading.Thread(target=_work, daemon=True).start()

    def _show_opt_result(self, r):
        if r is None:
            color = RED
            txt = "! 优化失败，请查看终端日志"
        else:
            color = GREEN if r.success else ORANGE
            txt = ("✓ " if r.success else "! ") + r.description
        if self._opt_result_item:
            self.itemconfigure(self._opt_result_item, text=txt, fill=color)
        else:
            self._opt_result_item = T.c_text(self, 36, 216, txt,
                                             size=10, color=color, anchor="w")

    def on_show(self):
        super().on_show()
        self._refresh()
