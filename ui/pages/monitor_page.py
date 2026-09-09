# -*- coding: utf-8 -*-
"""性能监控页面（Canvas 原生皮肤版）"""
import tkinter as tk
import threading
from tkinter import messagebox
from .base_page import BasePage
from .. import theme as T
from ui.theme import (ACCENT, CYAN, GREEN, ORANGE, RED, PURPLE,
                      TEXT, TEXT_DIM, TEXT_MUT, BORDER)

_TEXT_BG = "#f4f9ff"


class MonitorPage(BasePage):
    def __init__(self, parent, perf_monitor=None, log_widget=None, app=None, adb=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.perf = perf_monitor
        self.log = log_widget
        self._app = app
        self.adb = adb
        self._cards = {}
        self._score_item = None
        self._phone_title = None
        self._phone_meta = None
        self._phone_btn = None
        self._phone_refreshing = False
        self._draw()

    def _draw(self):
        cv = self
        w = self.page_w()
        h = self.page_h()
        T.CanvasBtn(cv, 22, 20, 74, 30, "‹ 返回", BORDER, self._go_back,
                    size=10, radius=12)
        T.c_titlebar(cv, 110, 24, "性能监控", "CPU / 内存 / 磁盘 / 电池 实时指标", PURPLE)
        # 操作按钮（置于顶部，加大尺寸整块可点，任何窗口高度下都可见）
        T.CanvasBtn(cv, 22, 64, 102, 38, "↻ 刷新", ACCENT, self._refresh, size=11, radius=13)
        self.monitor_btn = T.CanvasBtn(cv, 136, 64, 148, 38, "▶ 开始监控", GREEN,
                                       self._toggle_monitor, size=11, radius=13)
        self.opt_btn = T.CanvasBtn(cv, 296, 64, 148, 38, "⚡ 执行优化", ORANGE,
                                   self._apply_optimize, size=11, radius=13)
        # 综合评分
        T.c_card(cv, 22, 116, w - 44, 46)
        T.c_text(cv, 40, 139, "综合评分", size=11, bold=True, color=CYAN)
        self._score_item = T.c_text(cv, w - 44, 139, "--", size=22, bold=True,
                                    color=CYAN, anchor="e")
        # 指标卡 2×2
        cw = (w - 68) / 2.0
        y = 178
        self._make_card(cv, 22, y, cw, "CPU 使用率", CYAN, "cpu")
        self._make_card(cv, 22 + cw + 12, y, cw, "内存使用", PURPLE, "memory")
        y += 104
        self._make_card(cv, 22, y, cw, "磁盘空间", ORANGE, "storage")
        self._make_card(cv, 22 + cw + 12, y, cw, "电池", GREEN, "battery")
        y += 104
        # ---- 手机状态区（电脑与手机一体监控） ----
        T.c_section(cv, 22, y + 10, "手机状态", GREEN)
        y += 26
        T.c_card(cv, 22, y, w - 44, 66)
        self._phone_title = T.c_text(cv, 40, y + 20, "未检测", size=10,
                                     color=TEXT_MUT, outline=False)
        self._phone_btn = T.CanvasBtn(cv, w - 44 - 96, y + 12, 84, 30,
                                      "刷新手机", BORDER, self._refresh_mobile,
                                      size=9, radius=10)
        self._phone_meta = T.c_text(cv, 40, y + 44, "连接手机后显示 CPU / 内存 / 电池 / 存储",
                                    size=9, color=TEXT_MUT, outline=False)
        y += 66 + 8
        # 问题与建议
        T.c_section(cv, 22, y + 10, "性能问题", ORANGE)
        y += 26
        T.c_card(cv, 22, y, w - 44, 78)
        if getattr(self, "issues_text", None) is None:
            self.issues_text = tk.Text(self, bg=_TEXT_BG, fg=TEXT, font=("Microsoft YaHei UI", 9),
                                       relief="flat", borderwidth=0, wrap=tk.WORD,
                                       highlightthickness=0)
            self.issues_text.insert(1.0, "暂无")
            self.issues_text.config(state="disabled")
        cv.create_window(32, y + 8, anchor="nw", width=max(20, w - 68), height=62,
                         window=self.issues_text)
        y += 92
        T.c_section(cv, 22, y + 10, "优化建议", PURPLE)
        y += 26
        T.c_card(cv, 22, y, w - 44, 78)
        if getattr(self, "suggest_text", None) is None:
            self.suggest_text = tk.Text(self, bg=_TEXT_BG, fg=TEXT_DIM, font=("Microsoft YaHei UI", 9),
                                        relief="flat", borderwidth=0, wrap=tk.WORD,
                                        highlightthickness=0)
            self.suggest_text.insert(1.0, "暂无")
            self.suggest_text.config(state="disabled")
        cv.create_window(32, y + 8, anchor="nw", width=max(20, w - 68), height=62,
                         window=self.suggest_text)
        y += 92

    def _make_card(self, cv, x, y, w, title, color, key):
        T.c_card(cv, x, y, w, 90)
        T.c_text(cv, x + 16, y + 16, title, size=10, color=color)
        val_item = T.c_text(cv, x + 16, y + 52, "--", size=22, bold=True, color=TEXT)
        bar_bg = T.c_round(cv, x + 16, y + 68, x + w - 16, y + 78, r=5,
                           fill="#dbe9fb", outline="")
        bar_fg = T.c_round(cv, x + 16, y + 68, x + 16, y + 78, r=5, fill=color, outline="")
        self._cards[key] = {"val": val_item, "bar_bg": bar_bg, "bar_fg": bar_fg,
                            "x0": x + 16, "x1": x + w - 16, "y0": y + 68, "y1": y + 78,
                            "color": color}

    # ================= 手机状态 =================
    def on_show(self):
        super().on_show()
        self._refresh_mobile()

    def _refresh_mobile(self):
        if not self.adb or self._phone_refreshing:
            return
        self._phone_refreshing = True
        try:
            if self._phone_btn:
                self.itemconfigure(self._phone_btn, text="刷新中…", fill=GREEN)
        except Exception:
            pass
        threading.Thread(target=self._mobile_refresh_worker, daemon=True).start()

    def _mobile_refresh_worker(self):
        data = {"ok": False}
        try:
            if self.adb.ensure_online():
                data.update(ok=True, model=self.adb.model)
                data["cpu"] = self.adb.cpu()
                data["mem"] = self.adb.mem()
                data["bat"] = self.adb.battery()
                data["stor"] = self.adb.storage()
            else:
                data["state"] = self.adb.last_state()
        except Exception:
            pass
        try:
            self.after(0, lambda: self._mobile_refresh_done(data))
        except Exception:
            self._phone_refreshing = False

    def _mobile_refresh_done(self, data):
        try:
            if not self.winfo_exists():
                self._phone_refreshing = False
                return
        except Exception:
            self._phone_refreshing = False
            return
        self._phone_refreshing = False
        try:
            if self._phone_btn:
                self.itemconfigure(self._phone_btn, text="刷新手机", fill=BORDER)
        except Exception:
            pass
        if data.get("ok"):
            model = data.get("model") or "Android"
            cpu1 = "0"
            try:
                cpu1 = data["cpu"][0]
            except Exception:
                pass
            mt, ma = data.get("mem", (0, 0))
            mem_pct = min(99, int(100 * ma / mt)) if mt else 0
            lv = "?"
            try:
                lv = data["bat"][0]
            except Exception:
                pass
            total = "?"
            try:
                total = data["stor"][1]
            except Exception:
                pass
            if self._phone_title:
                self.itemconfigure(self._phone_title, text="已连接 · %s" % model, fill=GREEN)
            if self._phone_meta:
                self.itemconfigure(self._phone_meta,
                                   text="CPU %s | 内存 %d%% | 电池 %s%% | 存储 %s"
                                        % (cpu1, mem_pct, lv, total))
        else:
            st = data.get("state", "")
            if st == "unauthorized":
                if self._phone_title:
                    self.itemconfigure(self._phone_title, text="已连接未授权", fill=ORANGE)
                if self._phone_meta:
                    self.itemconfigure(self._phone_meta,
                                       text="请在手机上点击“允许USB调试”")
            else:
                if self._phone_title:
                    self.itemconfigure(self._phone_title, text="未连接手机", fill=TEXT_MUT)
                if self._phone_meta:
                    self.itemconfigure(self._phone_meta,
                                       text="请开启USB调试并连接，然后点“刷新手机”")

    def _set_bar(self, key, ratio, color=None):
        card = self._cards.get(key)
        if not card:
            return
        ratio = max(0.0, min(1.0, ratio or 0.0))
        x1 = card["x0"] + (card["x1"] - card["x0"]) * ratio
        self.coords(card["bar_fg"], card["x0"], card["y0"], max(card["x0"] + 1, x1), card["y1"])
        self.itemconfigure(card["bar_fg"], fill=color or card["color"])

    def _refresh(self):
        if not self.perf:
            return
        # 后台采样一次真实系统数据（psutil 采样约 0.5s，避免卡 UI），
        # 完成后回主线程刷新显示——不点"开始监控"也能看到真实指标与评分
        def _work():
            try:
                self.perf._update_metrics()
            except Exception:
                pass
            try:
                self.after(0, self._refresh_ui)
            except Exception:
                pass

        threading.Thread(target=_work, daemon=True).start()

    def _refresh_ui(self):
        if not self.perf:
            return
        try:
            m = self.perf.get_system_metrics()
            self._set_val("cpu", "%.1f%%" % m.cpu.usage_percent,
                          self._level_color(m.cpu.usage_percent))
            self._set_bar("cpu", m.cpu.usage_percent / 100.0, self._level_color(m.cpu.usage_percent))
            self._set_val("memory", "%.1f%%" % m.memory.usage_percent,
                          self._level_color(m.memory.usage_percent))
            self._set_bar("memory", m.memory.usage_percent / 100.0,
                          self._level_color(m.memory.usage_percent))
            self._set_val("storage", m.storage.used_space,
                          self._level_color(getattr(m.storage, "usage_percent", 50)))
            upct = getattr(m.storage, "usage_percent", 50)
            self._set_bar("storage", min(1.0, upct / 100.0), self._level_color(upct))
            self._set_val("battery", "%d%%" % m.battery.level, GREEN)
            self._set_bar("battery", m.battery.level / 100.0, GREEN)
            score = self.perf.get_performance_score()
            sc = GREEN if score >= 70 else ORANGE if score >= 40 else RED
            self._set_score(score, sc)
            if self._app and hasattr(self._app, '_res_log'):
                self._app._res_log("刷新监控: CPU %.1f%% 内存 %.1f%% 电池 %d%%"
                                   % (m.cpu.usage_percent, m.memory.usage_percent,
                                      m.battery.level))
            issues = self.perf.get_performance_issues()
            self._set_text(self.issues_text, "\n".join(issues) if issues else "无性能问题")
            suggests = self.perf.get_optimization_suggestions()
            self._set_text(self.suggest_text, "\n".join(suggests) if suggests else "暂无建议")
        except Exception:
            pass

    def _set_val(self, key, text, color):
        card = self._cards.get(key)
        if card:
            self.itemconfigure(card["val"], text=text, fill=color)

    def _set_score(self, score, color):
        if self._score_item:
            self.itemconfigure(self._score_item, text="%.0f" % score, fill=color)
        try:
            if self._app and hasattr(self._app, "header"):
                self._app._score_item and self._app.header.itemconfigure(
                    self._app._score_item, text="%.0f" % score, fill=color)
        except Exception:
            pass

    def _level_color(self, pct):
        return GREEN if pct < 70 else ORANGE if pct < 90 else RED

    def _set_text(self, w_, text):
        w_.config(state="normal")
        w_.delete(1.0, tk.END)
        w_.insert(1.0, text)
        w_.config(state="disabled")

    def _toggle_monitor(self):
        if self.perf:
            if getattr(self.perf, "_running", False):
                self.perf.stop_monitoring()
                self.monitor_btn.set_text("▶ 开始监控")
                self.monitor_btn.set_color(GREEN)
            else:
                self.perf.start_monitoring()
                self.monitor_btn.set_text("■ 停止监控")
                self.monitor_btn.set_color(ORANGE)

    # ---------- 执行优化 ----------
    def _apply_optimize(self):
        if not self.perf:
            return
        if not messagebox.askyesno(
                "执行优化",
                "将根据当前监控结果执行安全优化：\n\n"
                "· 清理用户与系统临时文件\n· 清理浏览器缓存\n· 刷新 DNS 缓存\n\n"
                "均为安全缓存项，不会删除个人文件，继续？",
                parent=self):
            return
        self.opt_btn.set_text("优化中...")
        self.opt_btn.set_color(PURPLE)
        self.opt_btn.set_state("disabled")
        threading.Thread(target=self._optimize_worker, daemon=True).start()

    def _optimize_worker(self):
        steps = []
        try:
            from core import SmartCleaner
            cleaner = SmartCleaner()
            r1 = cleaner._clean_temp_folders()
            steps.append("临时文件 %s" % cleaner._fmt_size(r1["size"]))
            r2 = cleaner._clean_win_temp()
            steps.append("系统临时 %s" % cleaner._fmt_size(r2["size"]))
            r3 = cleaner._clean_browser_cache()
            steps.append("浏览器缓存 %s" % cleaner._fmt_size(r3["size"]))
            cleaner._flush_dns()
            steps.append("DNS缓存已刷新")
        except Exception as e:
            steps.append("部分优化失败：" + str(e))
        self.after(0, lambda: self._optimize_done(steps))

    def _optimize_done(self, steps):
        self.opt_btn.set_text("⚡ 执行优化")
        self.opt_btn.set_color(ORANGE)
        self.opt_btn.set_state("normal")
        if self._app:
            if hasattr(self._app, "_term_log"):
                self._app._term_log("[OK] 性能优化执行完成：" + "；".join(steps), GREEN)
            if hasattr(self._app, "_res_log"):
                self._app._res_log("执行优化：" + "；".join(steps))
        self._refresh()

    def _go_back(self):
        if self._app:
            self._app.switch_page("home")

    def on_show(self):
        super().on_show()
        self._refresh()
