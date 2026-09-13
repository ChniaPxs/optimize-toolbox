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
            T.c_card(cv, 22, y, w - 44, 74, outline=ORANGE)
            T.c_wrap(cv, 36, y + 22, "⚠ 未以管理员身份运行：电脑端 TCP/DNS 参数需要管理员权限（"
                     "手机端优化免管理员、免 root，可直接生效）", size=10, color=ORANGE, max_w=w - 90, line_h=17)
            y += 88
        # 当前网络状态
        T.c_section(cv, 22, y + 12, "当前网络状态", CYAN)
        y += 28
        T.c_card(cv, 22, y, w - 44, 150)
        if getattr(self, "status_text", None) is None:
            self.status_text = tk.Text(self, bg="#f8fcff", fg=TEXT, font=("Microsoft YaHei UI", 10),
                                       relief="flat", borderwidth=0, wrap=tk.WORD,
                                       highlightthickness=1, highlightbackground=BORDER,
                                       highlightcolor=BORDER)
            self.status_text.insert(1.0, "点击 [刷新状态] 获取网络信息")
            self.status_text.config(state="disabled")
        cv.create_window(32, y + 10, anchor="nw", width=max(20, w - 68), height=126,
                         window=self.status_text)
        y += 162
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
        T.CanvasBtn(cv, 388, y + 12, 128, 34, "◎ DNS 恢复自动", ORANGE, self._restore_dns, size=11, radius=12)
        y += 72
        # 实时监控
        T.c_card(cv, 22, y, w - 44, 46)
        T.c_text(cv, 40, y + 23, "实时监控网络", size=11, color=TEXT_DIM)
        self.monitor_toggle = T.Toggle(self, command=self._toggle_monitor, on_color=CYAN)
        cv.create_window(w - 78, y + 12, anchor="nw", width=44, height=22,
                         window=self.monitor_toggle.cv)
        # 连接测试（诊断目标站点超时：DNS/TCP/Ping/HTTP + 一键修复）
        y += 60
        T.c_section(cv, 22, y + 12, "连接测试", GREEN)
        y += 28
        T.c_card(cv, 22, y, w - 44, 96)
        self.host_var = tk.StringVar(value="cas.guet.edu.cn")
        self.host_entry = tk.Entry(self, textvariable=self.host_var,
                                   font=("Microsoft YaHei UI", 10),
                                   relief="flat", bg="#f8fcff", fg=TEXT,
                                   highlightthickness=1, highlightbackground=BORDER,
                                   highlightcolor=BORDER)
        cv.create_window(32, y + 10, anchor="nw", width=max(120, w - 230), height=28,
                         window=self.host_entry)
        T.CanvasBtn(cv, w - 188, y + 9, 156, 32, "⚡ 尝试连接", CYAN,
                    self._try_connect, size=11, radius=12)
        self.conn_text = tk.Text(self, bg="#f8fcff", fg=TEXT, font=("Microsoft YaHei UI", 9),
                                 relief="flat", borderwidth=0, wrap=tk.WORD,
                                 highlightthickness=1, highlightbackground=BORDER,
                                 highlightcolor=BORDER, height=2)
        self.conn_text.insert(1.0,
                              "输入目标地址（默认学校认证系统），点击 [⚡ 尝试连接] 诊断并修复")
        self.conn_text.config(state="disabled")
        cv.create_window(32, y + 46, anchor="nw", width=max(20, w - 68), height=44,
                         window=self.conn_text)
        y += 108

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

    def _restore_dns(self):
        """把活动网卡 DNS 恢复为 DHCP 自动获取（校园网场景恢复）"""
        if not self.net:
            return
        if self._app and hasattr(self._app, "_term_log"):
            self._app._term_log("[DNS] 正在恢复自动获取...", CYAN)

        def _work():
            try:
                ok, desc = self.net.restore_dns_auto()
                msg = "[DNS] " + desc
            except Exception as e:
                ok, msg = False, "[DNS] 恢复失败: %s" % e
            if self.log:
                (self.log.ok(desc) if ok else self.log.warn(desc))
            if self._app and hasattr(self._app, "_term_log"):
                self._app._term_log(msg, GREEN if ok else ORANGE)
            self._set_status(msg.replace("[DNS] ", ""))

        threading.Thread(target=_work, daemon=True).start()

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
                    if not c.get("device_ok", True):
                        status = "未连接手机"
                    else:
                        status = "未生效"
                    if c.get("device_ok", True) and c.get("err"):
                        # 把失败的具体原因打到终端，方便诊断
                        try:
                            if self._app and hasattr(self._app, "_term_log"):
                                self._app._term_log(
                                    "  ⚠ 手机操作未生效原因: %s" % c["err"], ORANGE)
                        except Exception:
                            pass
                elif not _is_admin():
                    status = "需管理员权限"
                else:
                    status = "写入失败"
                pname = c.get("param", "参数")
                vtype = c.get("vtype", "REG_DWORD")
                if vtype == "手机操作":
                    # 免 root 手机网络优化：直接展示具体操作与前后对比
                    s_lines.append("  %s %s：%s" % (mark, pname,
                                                        c.get("new") or c.get("desc") or ""))
                    f_lines.append("  %s %s：%s" % (mark, pname,
                                                        c.get("new") or c.get("desc") or ""))
                    continue
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

    # ---------- 连接测试 ----------
    def _try_connect(self):
        host = (self.host_var.get().strip()
                if hasattr(self, "host_var") else "cas.guet.edu.cn")
        if not host:
            host = "cas.guet.edu.cn"
        self._set_conn("正在诊断 %s ..." % host)
        is_mobile = bool(getattr(self._app, "_is_mobile", False))

        def _work():
            lines = []
            try:
                if is_mobile:
                    # 手机模式：adb ping 目标
                    lines.append("手机端连接测试 %s：" % host)
                    if self.net:
                        p = self.net._mobile_ping(host)
                        if p and p.get("avg") is not None:
                            lines.append("  ✓ 手机可达：延迟 %.0fms，丢包 %d%%"
                                         % (p["avg"], p.get("loss") or 0))
                        else:
                            lines.append("  ✗ 手机 ping %s 无响应（可能需校园网/VPN 环境）" % host)
                    else:
                        lines.append("  网络引擎未初始化")
                elif self.net:
                    r = self.net.test_connection(host)
                    for st in r.get("steps", []):
                        mark = "✓" if st["ok"] else "✗"
                        lines.append("  %s %s：%s" % (mark, st["k"], st["v"]))
                    if not r.get("dns_ok"):
                        # 自动修复 DNS：备用公网 DNS 查询 → 切换 → 刷新 → 复查
                        lines.append("  ↻ 检测到 DNS 解析失败，自动修复中...")
                        rep = self.net.repair_dns(host)
                        lines += rep["lines"]
                        if rep.get("ok"):
                            lines.append("  ↻ DNS 已修复，重测连接...")
                            r = self.net.test_connection(host)
                            for st in r.get("steps", []):
                                mark = "✓" if st["ok"] else "✗"
                                lines.append("  %s %s：%s" % (mark, st["k"], st["v"]))
                    # 连接判定增强：DNS 正常但连接不通时检测代理 + 公网对照
                    steps_map = {st["k"]: st for st in r.get("steps", [])}
                    dns_ok = bool(r.get("dns_ok"))
                    tcp_ok = bool((steps_map.get("TCP 443") or {}).get("ok")
                                  or (steps_map.get("TCP 80") or {}).get("ok"))
                    if dns_ok and not tcp_ok:
                        proxy_en, proxy_sv = self.net.get_proxy()
                        if proxy_en:
                            lines.append("  ↻ 系统代理开启：%s（代理可能导致连接失败）" % proxy_sv)
                        pub = self.net.test_connection("www.baidu.com")
                        pub_steps = {st["k"]: st for st in pub.get("steps", [])}
                        pub_tcp = bool((pub_steps.get("TCP 443") or {}).get("ok")
                                       or (pub_steps.get("TCP 80") or {}).get("ok"))
                        if pub_tcp:
                            lines.append("  ↻ 公网对照：百度可正常连接")
                            lines.append("  → 结论：目标服务器需校园网/VPN 环境，或服务器维护中")
                        else:
                            lines.append("  ↻ 公网对照：百度同样不通")
                            lines.append("  → 结论：本机网络连接异常，请检查网线/Wi-Fi/防火墙")
                    else:
                        lines.append("  → " + r["summary"])
                else:
                    lines.append("  网络引擎未初始化")
            except Exception as e:
                lines.append("  诊断失败: %s" % e)
            txt = "\n".join(lines)
            self.after(0, lambda: self._set_conn(txt))
            try:
                if self._app and hasattr(self._app, "_term_log"):
                    self._app._term_log("[连接测试] %s" % host, CYAN)
                    for ln in lines:
                        self._app._term_log(ln, GREEN if "✓" in ln else ORANGE)
            except Exception:
                pass

        threading.Thread(target=_work, daemon=True).start()

    def _set_conn(self, text):
        try:
            self.conn_text.config(state="normal")
            self.conn_text.delete(1.0, tk.END)
            self.conn_text.insert(1.0, text)
            self.conn_text.config(state="disabled")
        except Exception:
            pass

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
