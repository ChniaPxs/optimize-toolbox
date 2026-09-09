# -*- coding: utf-8 -*-
"""网络优化页面（Canvas 原生皮肤版）"""
import tkinter as tk
import ctypes
import threading
from tkinter import messagebox
from .base_page import BasePage
from .. import theme as T
from ui.theme import (ACCENT, CYAN, GREEN, ORANGE, RED, PURPLE, PINK,
                      TEXT, TEXT_DIM, TEXT_MUT, BORDER)


def _is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


class NetworkPage(BasePage):
    def __init__(self, parent, net_optimizer=None, log_widget=None, app=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.net = net_optimizer
        self.log = log_widget
        self._app = app
        self._draw()

    def _draw(self):
        cv = self
        w = self.page_w()
        # 返回 + 标题
        T.CanvasBtn(cv, 22, 20, 74, 30, "‹ 返回", BORDER, self._go_back,
                    size=10, radius=12)
        T.c_titlebar(cv, 22, 78, "网络优化",
                     "TCP/IP 参数调优 · 智能 DNS · 场景模式切换", CYAN)
        y = 122
        # 权限提示
        if not _is_admin():
            T.c_card(cv, 22, y, w - 44, 52, outline=ORANGE)
            T.c_wrap(cv, 36, y + 26, "⚠ 未以管理员身份运行：TCP 参数 / DNS / 场景模式需要管理员权限，"
                     "建议右键「以管理员身份运行」", size=10, color=ORANGE, max_w=w - 90, line_h=16)
            y += 66
        # 当前网络状态
        T.c_section(cv, 22, y + 12, "当前网络状态", CYAN)
        y += 28
        T.c_card(cv, 22, y, w - 44, 196)
        if getattr(self, "status_text", None) is None:
            self.status_text = tk.Text(self, bg="#f8fcff", fg=TEXT, font=("Microsoft YaHei UI", 10),
                                       relief="flat", borderwidth=0, wrap=tk.WORD,
                                       highlightthickness=1, highlightbackground=BORDER,
                                       highlightcolor=BORDER)
            self.status_text.insert(1.0, "点击 [刷新状态] 获取网络信息")
            self.status_text.config(state="disabled")
        cv.create_window(32, y + 10, anchor="nw", width=max(20, w - 68), height=174,
                         window=self.status_text)
        y += 208
        # 场景模式
        T.c_section(cv, 22, y + 12, "场景模式", PURPLE)
        y += 30
        T.c_card(cv, 22, y, w - 44, 58)
        T.CanvasBtn(cv, 40, y + 12, 118, 34, "游戏模式", PURPLE, self._game_mode, size=11, radius=12)
        T.CanvasBtn(cv, 166, y + 12, 118, 34, "视频模式", PINK, self._video_mode, size=11, radius=12)
        T.CanvasBtn(cv, 292, y + 12, 118, 34, "下载模式", ORANGE, self._download_mode, size=11, radius=12)
        y += 72
        # 手动优化
        T.c_section(cv, 22, y + 12, "手动优化", GREEN)
        y += 30
        T.c_card(cv, 22, y, w - 44, 58)
        T.CanvasBtn(cv, 40, y + 12, 108, 34, "↻ 刷新状态", ACCENT, self._refresh, size=11, radius=12)
        T.CanvasBtn(cv, 156, y + 12, 108, 34, "⚡ 一键优化", GREEN, self._full_optimize, size=11, radius=12)
        T.CanvasBtn(cv, 272, y + 12, 108, 34, "◎ DNS 优化", CYAN, self._dns_optimize, size=11, radius=12)
        y += 72
        # 实时监控
        T.c_card(cv, 22, y, w - 44, 46)
        T.c_text(cv, 40, y + 23, "实时监控网络", size=11, color=TEXT_DIM)
        self.monitor_toggle = T.Toggle(self, command=self._toggle_monitor, on_color=CYAN)
        cv.create_window(w - 78, y + 12, anchor="nw", width=44, height=22,
                         window=self.monitor_toggle.cv)

    # ---------- 功能 ----------
    def _set_status(self, text):
        try:
            self.status_text.config(state="normal")
            self.status_text.delete(1.0, tk.END)
            self.status_text.insert(1.0, text)
            self.status_text.config(state="disabled")
        except Exception:
            pass

    def _refresh(self):
        if not self.net:
            self._set_status("网络引擎未初始化")
            return
        # 后台线程真实检测（ping/ipconfig 需数秒，避免卡 UI）
        self._set_status("正在检测网络状态...")
        def _work():
            try:
                if hasattr(self.net, "refresh_stats"):
                    stats = self.net.refresh_stats()
                else:
                    stats = self.net.get_network_stats()
                lines = ["IP 地址 : " + (stats.ip_address or "未知"),
                         "DNS     : " + (stats.dns_server or "未知"),
                         "网关    : " + (stats.gateway or "未知"),
                         "类型    : " + (stats.network_type or "未知"),
                         "延迟    : %.1f ms" % stats.latency,
                         "丢包率  : %.1f%%" % stats.packet_loss,
                         "TCP 连接: %d" % stats.connection_count]
                self.after(0, lambda: self._set_status("\n".join(lines)))
            except Exception as e:
                self.after(0, lambda: self._set_status("读取失败: %s" % e))
        threading.Thread(target=_work, daemon=True).start()

    def _full_optimize(self):
        if self.net:
            result = self.net.optimize_network()
            msg = ("[OK] " if result.success else "[WARN] ") + result.description
            if self.log:
                (self.log.ok(result.description) if result.success
                 else self.log.warn(result.description))
            if self._app and hasattr(self._app, '_res_log'):
                self._app._res_log(msg)
            if self._app and hasattr(self._app, "_term_log"):
                self._app._term_log(msg, GREEN if result.success else ORANGE)
            if not result.success and ("管理员" in result.description
                                       or "权限" in result.description):
                tip = "  ⚠ 需要管理员权限：请右键「以管理员身份运行」本程序后重试"
                if self._app and hasattr(self._app, "_term_log"):
                    self._app._term_log(tip, ORANGE)

    def _dns_optimize(self):
        if self.net:
            result = self.net.optimize_dns()
            if self.log:
                (self.log.ok(result.description) if result.success
                 else self.log.warn(result.description))
            if self._app and hasattr(self._app, "_term_log"):
                self._app._term_log("[DNS] " + result.description,
                                    GREEN if result.success else ORANGE)

    def _game_mode(self):
        if self.net:
            self._show_mode_result("游戏模式", self.net.enable_game_mode())

    def _video_mode(self):
        if self.net:
            self._show_mode_result("视频模式", self.net.enable_video_mode())

    def _download_mode(self):
        if self.net:
            self._show_mode_result("下载模式", self.net.enable_download_mode())

    def _show_mode_result(self, name, r):
        desc = r.description if r else "未知结果"
        ok = getattr(r, "success", False)
        changes = getattr(r, "changes", []) or []
        s_lines = ["[%s] %s" % (name, desc)]
        f_lines = ["[%s] %s" % (name, desc)]
        has_changed = False
        for c in changes:
            if isinstance(c, dict):
                old_s = c.get("old")
                if old_s is None:
                    old_s = "未设置"
                else:
                    try:
                        if isinstance(old_s, str) and old_s.lower().startswith("0x"):
                            old_s = str(int(old_s, 16))
                    except Exception:
                        pass
                mark = "✓" if c.get("ok") else "✗"
                if c.get("ok"):
                    if str(old_s) == str(c.get("new")):
                        status = "已是最优"
                    else:
                        status = "已写入"
                        has_changed = True
                elif c.get("adb"):
                    status = "未连接手机"
                elif not _is_admin():
                    status = "需管理员权限"
                else:
                    status = "写入失败"
                pname = c.get("param", "参数")
                vtype = c.get("vtype", "REG_DWORD")
                # 状态区：键名（值类型）原值 → 新值（状态）
                s_lines.append("  %s %s（%s）%s → %s（%s）"
                               % (mark, pname, vtype, old_s, c.get("new"), status))
                # 运行结果区：+ 完整注册表路径
                f_lines.append("  %s %s（%s）%s → %s（%s）"
                               % (mark, pname, vtype, old_s, c.get("new"), status))
                if c.get("key"):
                    f_lines.append("    路径 %s" % c["key"])
            else:
                s_lines.append("  • %s" % c)
                f_lines.append("  • %s" % c)
        if not ok and changes and not any(
                c.get("ok") for c in changes if isinstance(c, dict)):
            if not _is_admin():
                tip = "  ⚠ 全部写入失败：需要管理员权限，建议右键「以管理员身份运行」"
            else:
                tip = "  ⚠ 全部写入失败：请检查系统状态后重试"
            s_lines.append(tip)
            f_lines.append(tip)
        elif ok:
            # 全部已是最优：无需重启
            if not has_changed:
                tip = "  · 全部参数已是最优，无需改动"
                s_lines.append(tip)
                f_lines.append(tip)
            else:
                tip = "  · 参数已写入 · 在终端输入 net-restart 可立即生效（重启网卡，无需重启电脑）"
                s_lines.append(tip)
                f_lines.append(tip)
        s_text = "\n".join(s_lines)
        f_text = "\n".join(f_lines)
        if self._app and hasattr(self._app, "_term_log"):
            self._app._term_log("[%s] %s" % (name, desc), GREEN if ok else ORANGE)
            for ln in f_text.split("\n")[1:]:
                self._app._term_log(ln, GREEN if ok else ORANGE)
        if self._app and hasattr(self._app, "_res_log"):
            self._app._res_log(f_text)
        self._set_status(s_text)
        if not ok and ("管理员" in desc or "权限" in desc):
            tip = "  ⚠ 需要管理员权限：请右键「以管理员身份运行」本程序后重试"
            s_lines.append(tip)
            f_lines.append(tip)
            if self._app and hasattr(self._app, "_term_log"):
                self._app._term_log(tip, ORANGE)

    def _toggle_monitor(self, value):
        if self.net:
            if value:
                self.net.start_monitoring()
            else:
                self.net.stop_monitoring()

    def _go_back(self):
        if self._app:
            self._app.switch_page("home")

    def on_show(self):
        super().on_show()
        self._refresh()
