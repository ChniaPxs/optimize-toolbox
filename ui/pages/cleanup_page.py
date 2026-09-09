# -*- coding: utf-8 -*-
"""智能垃圾清理页面（Canvas 原生皮肤版）"""
import tkinter as tk
import threading
from tkinter import messagebox
from .base_page import BasePage
from .. import theme as T
from ui.theme import (ACCENT, CYAN, GREEN, ORANGE, RED, PURPLE, TEXT,
                      TEXT_DIM, TEXT_MUT, BORDER)

_LIST_BG = "#f4f9ff"
_ROW_A = "#eef6ff"
_ROW_B = "#f7fbff"


class _PhoneJunk:
    """手机垃圾项（与电脑清理项同接口，额外带 adb 路径）"""
    def __init__(self, path, size, desc):
        self.name = "📱 " + desc
        self.path = path
        self.size = size
        self.is_selected = True
        self.is_safe = True


class CleanupPage(BasePage):
    def __init__(self, parent, cleaner=None, log_widget=None, app=None,
                 adb=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.cleaner = cleaner
        self.log = log_widget
        self._app = app
        self.adb = adb
        self._vars = {}
        self._targets = {}
        self._scanning = False
        self._cleaning = False
        self._status_item = None
        self._draw()

    def _draw(self):
        cv = self
        w = self.page_w()
        h = self.page_h()
        T.CanvasBtn(cv, 22, 20, 74, 30, "‹ 返回", BORDER, self._go_back,
                    size=10, radius=12)
        T.c_titlebar(cv, 22, 78, "智能垃圾清理",
                     "系统临时文件 · 浏览器缓存 · 重复与大文件", GREEN)
        self._status_item = T.c_text(cv, 22, 122, "", size=11, color=GREEN)
        # 操作按钮
        T.c_card(cv, 22, 138, w - 44, 56)
        self.scan_btn = T.CanvasBtn(cv, 40, 149, 122, 34, "⇕ 扫描垃圾", ACCENT,
                                    self._scan, size=11, radius=12)
        self.clean_btn = T.CanvasBtn(cv, 172, 149, 122, 34, "⚡ 一键清理", GREEN,
                                     self._clean_all, size=11, radius=12)
        T.CanvasBtn(cv, 304, 149, 122, 34, "⏰ 定时清理", PURPLE,
                    self._schedule, size=11, radius=12)
        # 清理项目列表
        T.c_section(cv, 22, 222, "清理项目", CYAN)
        ly = 238
        lh = max(60, h - ly - 14)
        T.c_card(cv, 22, ly, w - 44, lh, radius=12)
        # 列表滚动容器（实底，功能列表区）
        self._build_list_box(w - 68, ly + 10)
        cv.create_window(32, ly + 10, anchor="nw", width=max(20, w - 68),
                         height=max(40, lh - 20), window=self._list_box)

    def _build_list_box(self, width, height):
        if getattr(self, "_list_box", None) is None:
            box = tk.Frame(self, bg=_LIST_BG)
            canvas = tk.Canvas(box, bg=_LIST_BG, highlightthickness=0, bd=0)
            scrollbar = tk.Scrollbar(box, orient=tk.VERTICAL, command=canvas.yview,
                                     bg=_LIST_BG, troughcolor="#dbe9fb",
                                     activebackground=ACCENT, relief="flat", bd=0)
            self.scroll_frame = tk.Frame(canvas, bg=_LIST_BG)
            self.scroll_frame.bind("<Configure>",
                                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
            canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)
            canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            canvas.bind("<Configure>", lambda e: canvas.itemconfigure(
                "all", width=e.width))
            box._scroll_canvas = canvas
            self._list_box = box
            self._list_scroll_canvas = canvas
        else:
            self._list_box.configure(width=width, height=height)

    def _set_status(self, text, color=GREEN):
        if self._status_item:
            self.itemconfigure(self._status_item, text=text, fill=color)

    # ---------- 扫描 ----------
    def _scan(self):
        if self._scanning or self._cleaning:
            return
        self._scanning = True
        self.scan_btn.set_state("disabled")
        self.scan_btn.set_text("⋯ 扫描中")
        self._set_status("正在扫描系统垃圾...", ORANGE)

        def _do_scan():
            phone_n = 0
            try:
                targets = list(self.cleaner.scan_for_junk()) if self.cleaner else []
                if self.adb:
                    try:
                        phone = self.adb.scan_junk() or []
                    except Exception:
                        phone = []
                    for path, sz, desc in phone:
                        targets.append(_PhoneJunk(path, sz, desc))
                    phone_n = len(phone)
                self.after(0, lambda: self._populate_list(targets, phone_n))
            except Exception as e:
                self.after(0, lambda: self._set_status("扫描出错: " + str(e), RED))
            finally:
                self.after(0, self._scan_done)

        threading.Thread(target=_do_scan, daemon=True).start()

    def _scan_done(self):
        self._scanning = False
        self.scan_btn.set_state("normal")
        self.scan_btn.set_text("⇕ 扫描垃圾")

    def _populate_list(self, targets, phone_n=0):
        for w_ in self.scroll_frame.winfo_children():
            w_.destroy()
        self._vars.clear()
        self._targets.clear()
        for t in targets:
            self._add_item(t)
        total_size = sum(t.size for t in targets)
        if phone_n:
            msg = "✓ 发现 %d 项（含手机 %d 项），共 %s" % (
                len(targets), phone_n, self._fmt_size(total_size))
        else:
            msg = "✓ 发现 %d 项，共 %s" % (len(targets), self._fmt_size(total_size))
        self._set_status(msg)
        if self._app and hasattr(self._app, '_res_log'):
            self._app._res_log(msg)
        if self._app and hasattr(self._app, '_term_log'):
            self._app._term_log(msg, GREEN)
        if self.log:
            self.log.ok("扫描完成: 发现 %d 个清理项" % len(targets))
        self._update_scroll_region()

    def _update_scroll_region(self):
        try:
            self._list_scroll_canvas.configure(
                scrollregion=self._list_scroll_canvas.bbox("all"))
        except Exception:
            pass

    def _add_item(self, target):
        row = tk.Frame(self.scroll_frame, bg=_ROW_A if len(self._vars) % 2 else _ROW_B)
        row.pack(fill=tk.X, pady=1)
        var = tk.BooleanVar(value=target.is_selected)
        self._vars[target.name] = var
        self._targets[target.name] = target
        tk.Checkbutton(row, variable=var, bg=row.cget("bg"), fg=TEXT,
                       selectcolor="#ffffff", activebackground=row.cget("bg"),
                       activeforeground=TEXT,
                       command=lambda t=target, v=var: self._on_check(t, v)).pack(side=tk.LEFT, padx=8)
        icon = "◈"
        tk.Label(row, text=icon + "  " + target.name, font=("Microsoft YaHei UI", 10),
                 bg=row.cget("bg"), fg=TEXT).pack(side=tk.LEFT, padx=4)
        if getattr(target, "is_safe", False):
            tk.Label(row, text="SAFE", font=("Microsoft YaHei UI", 8, "bold"),
                     bg="#e3f9ee", fg=GREEN).pack(side=tk.RIGHT, padx=8, pady=3)
        size_str = self._fmt_size(target.size) if target.size > 0 else "0 B"
        tk.Label(row, text=size_str, font=("Microsoft YaHei UI", 9),
                 bg=row.cget("bg"), fg=TEXT_MUT).pack(side=tk.RIGHT, padx=12)

    def _on_check(self, target, var):
        target.is_selected = var.get()

    # ---------- 清理 ----------
    def _clean_all(self):
        if self._scanning or self._cleaning:
            return
        if not self.cleaner:
            self._set_status("清理引擎未初始化", RED)
            return
        self._cleaning = True
        self.clean_btn.set_state("disabled")
        self.clean_btn.set_text("⋯ 清理中")
        self._set_status("正在清理垃圾文件...", ORANGE)

        def _do_clean():
            err = None
            result = None
            phone_ok, phone_fail = 0, []
            try:
                result = self.cleaner.clean_all() if self.cleaner else None
                selected_phone = [t for t in self._targets.values()
                                  if isinstance(t, _PhoneJunk) and t.is_selected]
                if selected_phone and self.adb:
                    phone_ok, phone_fail = self.adb.clean_junk(
                        [t.path for t in selected_phone])
            except Exception as e:
                err = e

            def _show_result():
                if err is not None:
                    self._set_status("清理失败: " + str(err), RED)
                    if self._app and hasattr(self._app, '_term_log'):
                        self._app._term_log("[ERR] 清理失败: " + str(err), RED)
                    return
                steps = list(result.steps) if result else []
                if phone_ok:
                    steps.append("📱 手机垃圾已删除 %d 项" % phone_ok)
                if phone_fail:
                    steps.append("⚠ 手机垃圾 %d 项清理失败: %s" % (
                        len(phone_fail), "; ".join(phone_fail[:3])))
                if self._app and hasattr(self._app, '_term_log'):
                    for step in steps:
                        self._app._term_log(step, TEXT)
                    self._app._term_log("", TEXT)
                freed = self._fmt_size(result.total_size) if result else "0 B"
                count = result.total_files if result else 0
                failed = getattr(result, 'failed_files', 0) if result else 0
                need_admin = getattr(result, 'need_admin', False) if result else False
                if (result and result.success) or phone_ok:
                    msg = "✓ 清理完成: 删除 %d 个文件, 释放 %s" % (count, freed)
                    if phone_ok:
                        msg += " · 手机 %d 项" % phone_ok
                    if failed:
                        msg += "（%d 项被占用/无权限跳过）" % failed
                    color = GREEN
                else:
                    msg = "! 没有可清理项（可能需要管理员权限）"
                    color = ORANGE
                self._set_status(msg, color)
                if self._app and hasattr(self._app, '_res_log'):
                    self._app._res_log(msg)
                if self.log:
                    self.log.ok(result.message)
                if need_admin:
                    tip = "  ⚠ 部分系统垃圾需要管理员权限：请右键「以管理员身份运行」本程序后清理更彻底"
                    self._set_status(msg + " · " + tip, ORANGE)
                    if self._app and hasattr(self._app, '_res_log'):
                        self._app._res_log(tip)
                    if self._app and hasattr(self._app, '_term_log'):
                        self._app._term_log(tip, ORANGE)

            self.after(0, _show_result)
            self.after(0, self._clean_done)

        threading.Thread(target=_do_clean, daemon=True).start()

    def _clean_done(self):
        self._cleaning = False
        self.clean_btn.set_state("normal")
        self.clean_btn.set_text("⚡ 一键清理")
        self._scan()

    def _schedule(self):
        if self._scanning or self._cleaning:
            return
        if not self.cleaner:
            self._set_status("清理引擎未初始化", RED)
            return
        try:
            scheduled = self.cleaner.schedule_smart_clean()
            if scheduled:
                msg, color = "✓ 定时清理已启用 (每天自动清理)", GREEN
            else:
                msg, color = "定时清理已关闭", TEXT_MUT
            self._set_status(msg, color)
            if self.log:
                self.log.ok("定时清理已" + ("启用" if scheduled else "关闭"))
        except Exception as e:
            self._set_status("设置定时清理失败: " + str(e), RED)
            if self.log:
                self.log.err("定时清理设置失败: " + str(e))

    def _go_back(self):
        if self._app:
            self._app.switch_page("home")

    def _fmt_size(self, b):
        for u in ["B", "KB", "MB", "GB"]:
            if b < 1024:
                return "%.1f %s" % (b, u)
            b /= 1024
        return "%.1f TB" % b

    def on_show(self):
        pass
