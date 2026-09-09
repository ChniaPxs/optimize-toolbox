# -*- coding: utf-8 -*-
"""应用卸载页面（全 Canvas 原生绘制版）：面板透明、背景处处可见；
扫描电脑 / 手机应用，点选后批量卸载；双栏可拖分隔条自由调节大小"""
import tkinter as tk
import threading
from tkinter import messagebox
from .base_page import BasePage
from .. import theme as T
from ui.theme import (ACCENT, CYAN, GREEN, ORANGE, RED, TEXT, TEXT_DIM, TEXT_MUT, BORDER)
from core.app_manager import AppManager

_PANEL_BG = "#f4f9ff"   # 兼容旧常量引用（隐藏输入控件底色，视觉 1px 不可见）
_ROW_A = "#eef6ff"
_ROW_B = "#f7fbff"


class AppsPage(BasePage):
    def __init__(self, parent, adb=None, app=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._adb = adb
        self._app = app
        self._manager = AppManager()
        self._pc_rows = []
        self._mobile_rows = []
        self._busy = False
        self._status_item = None
        self._split_item = None
        self._split_px = None
        self._split_user = False
        self._pc_panel_item = None
        self._mb_panel_item = None
        self._split_redraw_after = None
        self._split0 = 0
        self._split_x0 = 0
        self._pc_off = 0
        self._mb_off = 0
        self._pc_count_item = None
        self._mb_count_item = None
        self._search_text_item = None
        self._search_entry = None
        self._draw()
        self.after(400, self._auto_scan)

    # ================= 绘制（全 Canvas，面板透明，背景处处可见） =================
    def _draw(self):
        cv = self
        w = self.page_w()
        h = self.page_h()
        if w < 30 or h < 30:
            return
        cv.delete("all")
        # 标题行
        T.CanvasBtn(cv, 22, 20, 78, 30, "‹ 返回", BORDER, self._go_back, size=10, radius=12)
        T.c_text(cv, 110, 32, "应用卸载", size=14, bold=True, color=ORANGE)
        T.c_text(cv, 210, 32, "扫描电脑 / 手机应用，点选后批量卸载", size=10, color=TEXT_MUT)
        # 操作栏
        T.CanvasBtn(cv, 22, 56, 118, 32, "扫描电脑应用", BORDER, self._scan_pc, size=10, radius=11)
        T.CanvasBtn(cv, 148, 56, 118, 32, "刷新手机应用", BORDER, self._load_mobile, size=10, radius=11)
        T.CanvasBtn(cv, 286, 56, 76, 32, "全选", BORDER, lambda: self._sel_all(True), size=10, radius=11)
        T.CanvasBtn(cv, 370, 56, 84, 32, "全不选", BORDER, lambda: self._sel_all(False), size=10, radius=11)
        self._status_item = T.c_text(cv, w - 24, 70, "", size=10, color=TEXT_MUT,
                                     anchor="e", outline=False)
        # 双栏布局（用户未拖动时分隔条跟随窗口宽度）
        ly = 100
        lh = max(90, h - ly - 14)
        sash = 6
        max_lw = w - 44 - sash - 100
        if not self._split_user:
            self._split_px = None
        lw = max(100, min((self._split_px if self._split_px else (w - 44 - sash) // 2), max_lw))
        self._split_px = lw
        mx = 22 + lw + sash
        mw = w - 44 - lw - sash
        # ---- PC 卡（透明描边，背景透出） ----
        self._pc_panel_item = T.c_card(cv, 22, ly, lw, lh, radius=12, outline=BORDER)
        T.c_text(cv, 34, ly + 22, "电脑应用", size=11, bold=True, color=CYAN, outline=False)
        self._pc_count_item = T.c_text(cv, 22 + lw - 20, ly + 22, "%d 个应用" % len(self._pc_rows),
                                       size=10, color=CYAN, anchor="e", outline=False)
        # 搜索行（隐藏 1px 输入框 + Canvas 回显，支持中文且不遮挡背景）
        T.c_text(cv, 34, ly + 48, "搜索", size=9, color=TEXT_DIM, outline=False)
        if self._search_entry is None:
            self._search_entry = tk.Entry(cv, width=1, bg=_PANEL_BG, fg=TEXT,
                                          font=("Microsoft YaHei UI", 9), relief="flat",
                                          bd=0, highlightthickness=0, takefocus=1)
            self._search_entry.bind("<KeyRelease>", lambda e: self._search_changed())
            self._search_entry.place(x=-1, y=-1, width=1, height=20)
        self._search_entry.place(x=max(1, 64), y=max(1, ly + 38), width=1, height=20)
        self._search_text_item = T.c_text(cv, 66, ly + 48, self._search_entry.get(),
                                          size=9, color=TEXT, outline=False)
        si = T.c_round(cv, 58, ly + 38, 60, ly + 58, r=1, fill="", outline="")
        cv.tag_bind(si, "<Button-1>", lambda e: self._focus_search())
        # PC 列表（Canvas 原生行，背景透出）
        self._draw_list("pc", 22, ly, lw, lh)
        # 卸载按钮（ghost：描边常态，hover 实心，不再常亮）
        T.CanvasBtn(cv, 22 + lw / 2 - 75, ly + lh - 42, 150, 34, "卸载选中（电脑）",
                    RED, self._uninstall_pc_selected, size=10, radius=12, solid=False)
        # ---- 手机卡 ----
        self._mb_panel_item = T.c_card(cv, mx, ly, mw, lh, radius=12, outline=BORDER)
        T.c_text(cv, mx + 12, ly + 22, "手机应用", size=11, bold=True, color=GREEN, outline=False)
        self._mb_count_item = T.c_text(cv, mx + mw - 12, ly + 22, "%d 个应用" % len(self._mobile_rows),
                                       size=10, color=GREEN, anchor="e", outline=False)
        self._draw_list("mb", mx, ly, mw, lh)
        T.CanvasBtn(cv, mx + mw / 2 - 75, ly + lh - 42, 150, 34, "卸载选中（手机）",
                    RED, self._uninstall_mobile_selected, size=10, radius=12, solid=False)
        # ---- 分隔条（可拖动；常态淡色，hover/拖动时亮蓝） ----
        self._split_item = T.c_round(cv, 22 + lw, ly, 22 + lw + sash, ly + lh, r=2,
                                     fill="#cfe0f5", outline="")
        cv.tag_bind(self._split_item, "<Button-1>", self._split_start)
        cv.tag_bind(self._split_item, "<B1-Motion>", self._split_move)
        cv.tag_bind(self._split_item, "<Enter>", self._split_enter)
        cv.tag_bind(self._split_item, "<Leave>", self._split_leave)
        cv.bind("<MouseWheel>", self._on_wheel)
        cv.configure(cursor="")  # 重绘后恢复全局光标，避免残留

    def _draw_list(self, kind, x0, y0, w, h):
        """Canvas 原生列表：透明行 + 复选方块 + 名称；点击整行切换选中"""
        cv = self
        lx = x0 + 14
        top = y0 + 66
        bottom = y0 + h - 52
        row_h = 30
        if kind == "pc":
            rows = self._filter_pc()
            off = self._pc_off
            count_item = self._pc_count_item
        else:
            rows = self._mobile_rows
            off = self._mb_off
            count_item = self._mb_count_item
        if count_item is not None:
            try:
                cv.itemconfigure(count_item, text="%d 个应用" % len(rows))
            except Exception:
                pass
        max_rows = max(0, (bottom - top) // row_h)
        off = min(off, max(0, len(rows) - max_rows))
        if kind == "pc":
            self._pc_off = off
        else:
            self._mb_off = off
        if max_rows <= 0:
            return
        for i in range(max_rows):
            idx = i + off
            if idx >= len(rows):
                break
            r = rows[idx]
            yy = top + i * row_h + row_h // 2
            sel = r["var"].get()
            # 复选方块
            bx, by = lx + 8, yy
            if sel:
                T.c_round(cv, bx - 7, by - 8, bx + 7, by + 8, r=3, fill=CYAN, outline="")
                T.c_text(cv, bx, by, "✓", size=8, bold=True, color="#ffffff",
                         anchor="center", outline=False)
            else:
                T.c_round(cv, bx - 7, by - 8, bx + 7, by + 8, r=3, fill="",
                          outline="#9cc4ee", width=1)
            # 名称 + 摘要（手机仅包名；均精确截断避免重叠）
            if kind == "pc":
                name_max = max(60, (x0 + w - 12) - (bx + 18) - 100)
                T.c_text(cv, bx + 18, yy, self._fit_text(r["app"].name, name_max, 10),
                         size=10, color=ACCENT if sel else TEXT)
                T.c_text(cv, x0 + w - 12, yy, self._fit_text(r["app"].summary(), 110, 9),
                         size=9, color=TEXT_MUT, anchor="e")
            else:
                name_max = max(60, (x0 + w - 12) - (bx + 18) - 8)
                T.c_text(cv, bx + 18, yy, self._fit_text(r.get("label") or r["pkg"], name_max, 10),
                         size=10, color=ACCENT if sel else TEXT)
            # 透明整行点击区（切换选中）
            it = cv.create_rectangle(lx, top + i * row_h, x0 + w - 10,
                                     top + i * row_h + row_h, outline="", fill="")
            cv.tag_bind(it, "<Button-1>", lambda e, rr=r: self._toggle_row(rr))
            cv.tag_bind(it, "<Enter>", lambda e: cv.configure(cursor="hand2"))
            cv.tag_bind(it, "<Leave>", lambda e: cv.configure(cursor=""))

    # ================= 列表辅助 =================
    def _fit_text(self, text, max_w, size):
        """按像素精确截断文字（微软雅黑测量，二分），超出加省略号"""
        if not text:
            return ""
        try:
            import tkinter.font as tkfont
            if getattr(self, "_tf_font", None) is None:
                self._tf_font = tkfont.Font(family="Microsoft YaHei UI", size=size)
                self._tf_size = size
            elif getattr(self, "_tf_size", None) != size:
                self._tf_font.configure(size=size)
                self._tf_size = size
            if self._tf_font.measure(text) <= max_w:
                return text
            lo, hi = 0, len(text)
            while lo < hi:
                mid = (lo + hi + 1) // 2
                if self._tf_font.measure(text[:mid]) <= max_w:
                    lo = mid
                else:
                    hi = mid - 1
            return text[:lo - 1] + "…" if lo > 1 else text[:1]
        except Exception:
            return text

    def _filter_pc(self):
        kw = ""
        if self._search_entry is not None:
            kw = self._search_entry.get().strip().lower()
        if not kw:
            return self._pc_rows
        return [r for r in self._pc_rows
                if kw in r["app"].name.lower() or kw in r["app"].publisher.lower()]

    def _toggle_row(self, r):
        r["var"].set(not r["var"].get())
        self._draw()

    def _focus_search(self):
        try:
            self._search_entry.focus_set()
        except Exception:
            pass

    def _search_changed(self):
        self._pc_off = 0
        self._draw()

    def _on_wheel(self, e):
        try:
            if 22 <= e.x <= 22 + self._split_px:
                self._pc_off += (-1 if e.delta > 0 else 1)
            else:
                self._mb_off += (-1 if e.delta > 0 else 1)
            self._draw()
        except Exception:
            pass
        return "break"

    # ================= 分隔条拖拽 =================
    def _split_enter(self, e):
        try:
            self.itemconfigure(self._split_item, fill="#9cc4ee")
            self.configure(cursor="sb_h_double_arrow")
        except Exception:
            pass

    def _split_leave(self, e):
        try:
            self.itemconfigure(self._split_item, fill="#cfe0f5")
            self.configure(cursor="")
        except Exception:
            pass

    def _split_start(self, e):
        self._split0 = self._split_px
        self._split_x0 = e.x

    def _split_move(self, e):
        w = self.page_w()
        self._split_user = True
        self._split_px = max(100, min(w - 44 - 8 - 100,
                                      self._split0 + (e.x - self._split_x0)))
        # 轻量实时反馈：只移动分隔条与两面板框（列表松手后重排，拖动全程跟手）
        try:
            h = self.page_h()
            ly = 100
            lh = max(90, h - ly - 14)
            sx = 22 + self._split_px
            if self._split_item:
                self.coords(self._split_item, sx, ly, sx + 6, ly + lh)
            if self._pc_panel_item:
                self.coords(self._pc_panel_item,
                            *self._card_coords(22, ly, self._split_px, lh))
            if self._mb_panel_item:
                mw = w - 44 - self._split_px - 6
                self.coords(self._mb_panel_item,
                            *self._card_coords(sx + 6, ly, mw, lh))
        except Exception:
            pass
        if getattr(self, "_split_redraw_after", None):
            try:
                self.after_cancel(self._split_redraw_after)
            except Exception:
                pass
        self._split_redraw_after = self.after(100, lambda: (setattr(self, '_split_redraw_after', None), self._draw()))  # 松手后完整重绘

    def _card_coords(self, x, y, w, h, r=12):
        """生成与 c_round 一致的圆角多边形顶点"""
        r = max(0, min(r, w / 2.0, h / 2.0))
        x2, y2 = x + w, y + h
        return [x + r, y, x2 - r, y, x2, y, x2, y + r, x2, y2 - r, x2, y2,
                x2 - r, y2, x + r, y2, x, y2, x, y2 - r, x, y + r, x, y]

    def _go_back(self):
        if self._app and hasattr(self._app, "switch_page"):
            self._app.switch_page("home")

    # ================= 兼容旧接口 =================
    def _render_pc(self):
        try:
            self._draw()
        except Exception:
            pass

    def _render_mobile(self):
        try:
            self._draw()
        except Exception:
            pass

    def _set_count(self, kind, n):
        pass  # 计数在 _draw_list 内联更新

    def _set_status(self, text, color=TEXT_MUT):
        if self._status_item:
            try:
                self.itemconfigure(self._status_item, text=text, fill=color)
            except Exception:
                pass

    # ================= 扫描（业务逻辑保留） =================
    def _auto_scan(self):
        self._scan_pc()
        self._load_mobile()

    def _scan_pc(self):
        if self._busy:
            return
        self._busy = True
        self._set_status("正在扫描电脑应用...", CYAN)
        threading.Thread(target=self._scan_pc_worker, daemon=True).start()

    def _scan_pc_worker(self):
        try:
            apps = self._manager.list_pc_apps()
        except Exception:
            apps = []
        try:
            self.after(0, lambda: self._scan_pc_done(apps))
        except Exception:
            self._busy = False

    def _scan_pc_done(self, apps):
        try:
            if not self.winfo_exists():
                self._busy = False
                return
        except Exception:
            self._busy = False
            return
        self._busy = False
        self._pc_rows = [{"app": a, "var": tk.BooleanVar(value=False)} for a in apps]
        self._render_pc()
        self._set_status("电脑应用 %d 个" % len(apps), GREEN)

    def _load_mobile(self):
        if self._busy:
            return
        self._busy = True
        self._set_status("正在获取手机应用...", CYAN)
        threading.Thread(target=self._mobile_worker, daemon=True).start()

    def _mobile_worker(self):
        ok, pkgs = False, []
        state = ""
        try:
            if self._adb:
                if self._adb.ensure_online():
                    pkgs = self._adb.pkgs()
                    ok = True
                else:
                    state = self._adb.last_state()
        except Exception:
            pass
        try:
            self.after(0, lambda: self._mobile_done(ok, pkgs, state))
        except Exception:
            self._busy = False

    def _mobile_done(self, ok, pkgs, state=""):
        try:
            if not self.winfo_exists():
                self._busy = False
                return
        except Exception:
            self._busy = False
            return
        self._busy = False
        if not ok:
            self._mobile_rows = []
            self._render_mobile()
            if state == "unauthorized":
                self._set_status("手机已连接但未授权 · 请在手机上点“允许USB调试”", ORANGE)
            else:
                self._set_status("未连接手机 · 请开启USB调试并连接", ORANGE)
            return
        self._mobile_rows = [{"pkg": p["pkg"], "label": p.get("label") or p["pkg"],
                              "var": tk.BooleanVar(value=False)} for p in pkgs]
        self._render_mobile()
        self._set_status("手机应用 %d 个 · 正在解析中文名…" % len(pkgs), GREEN)
        self._start_label_fetch()

    # ================= 中文应用名（后台并行解析，逐个更新） =================
    def _start_label_fetch(self):
        if not (self._adb and self._adb._adb_path and self._mobile_rows):
            return
        try:
            from concurrent.futures import ThreadPoolExecutor
            import subprocess
            adb = self._adb._adb_path
            rows = list(self._mobile_rows)
            try:
                r = subprocess.run([adb, "shell", "pm", "list", "packages", "-3", "-f"],
                                   capture_output=True, text=True, timeout=12,
                                   encoding="utf-8", errors="replace")
                pairs = []
                for line in (r.stdout or "").splitlines():
                    line = line.strip()
                    if not line.startswith("package:"):
                        continue
                    try:
                        path = line.split("package:")[1].rsplit("=", 1)[0]
                        pkg = line.rsplit("=", 1)[1].strip()
                    except Exception:
                        continue
                    if any(row["pkg"] == pkg for row in rows):
                        pairs.append((path, pkg))
            except Exception:
                return
            from utils import apk_label

            def work(path, pkg):
                return pkg, apk_label.fetch_label(adb, path)

            def done_cb(futures):
                labels = {}
                for f in futures:
                    try:
                        pkg, lab = f.result()
                        if lab:
                            labels[pkg] = lab
                    except Exception:
                        pass
                try:
                    self.after(0, lambda: self._labels_done(labels))
                except Exception:
                    pass

            ex = ThreadPoolExecutor(max_workers=8)
            futures = [ex.submit(work, path, pkg) for path, pkg in pairs]
            threading.Thread(target=done_cb, args=(futures,), daemon=True).start()
            ex.shutdown(wait=False)
        except Exception:
            pass

    def _labels_done(self, labels):
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return
        if not labels:
            self._set_status("手机应用 %d 个" % len(self._mobile_rows), GREEN)
            return
        n = 0
        for row in self._mobile_rows:
            if row["pkg"] in labels:
                row["label"] = labels[row["pkg"]]
                n += 1
        self._render_mobile()
        self._set_status("手机应用 %d 个（已显示中文名 %d 个）" % (len(self._mobile_rows), n), GREEN)

    # ================= 选择与卸载 =================
    def _sel_all(self, value):
        for r in self._pc_rows + self._mobile_rows:
            r["var"].set(value)
        self._draw()

    def _uninstall_pc_selected(self):
        sel = [r for r in self._pc_rows if r["var"].get()]
        if not sel:
            self._set_status("请先勾选要卸载的应用", RED)
            return
        names = "\n".join(r["app"].name for r in sel[:8]) + ("\n..." if len(sel) > 8 else "")
        if not messagebox.askyesno(
                "确认卸载",
                "将卸载以下 %d 个应用：\n\n%s\n\n此操作不可恢复，确定继续？" % (len(sel), names),
                parent=self):
            return
        self._start_uninstall(sel, "pc")

    def _uninstall_mobile_selected(self):
        sel = [r for r in self._mobile_rows if r["var"].get()]
        if not sel:
            self._set_status("请先勾选要卸载的应用", RED)
            return
        pkgs = "\n".join(r.get("label") or r["pkg"] for r in sel[:8]) + ("\n..." if len(sel) > 8 else "")
        if not messagebox.askyesno(
                "确认卸载",
                "将从手机卸载以下 %d 个应用：\n\n%s\n\n此操作不可恢复，确定继续？" % (len(sel), pkgs),
                parent=self):
            return
        self._start_uninstall(sel, "mobile")

    def _start_uninstall(self, sel, kind):
        self._busy = True
        self._set_status("正在卸载...", ORANGE)
        threading.Thread(target=self._uninstall_worker, args=(sel, kind), daemon=True).start()

    def _uninstall_worker(self, sel, kind):
        results = []
        for r in sel:
            try:
                if kind == "pc":
                    ok, msg = self._manager.uninstall_pc(r["app"])
                else:
                    ok, msg = self._adb.uninstall(r["pkg"])
            except Exception as e:
                ok, msg = False, "卸载出错：" + str(e)
            results.append((ok, msg))
        try:
            self.after(0, lambda: self._uninstall_done(kind, results))
        except Exception:
            pass

    def _uninstall_done(self, kind, results):
        try:
            if not self.winfo_exists():
                self._busy = False
                return
        except Exception:
            self._busy = False
            return
        self._busy = False
        ok_n = sum(1 for ok, _ in results if ok)
        self._set_status("卸载完成：成功 %d / %d" % (ok_n, len(results)),
                         GREEN if ok_n == len(results) else ORANGE)
        if self._app and hasattr(self._app, "_term_log"):
            for ok, msg in results:
                self._app._term_log(("[OK] " if ok else "[ERR] ") + msg,
                                    GREEN if ok else RED)
        if kind == "pc":
            self._scan_pc()
        else:
            self._load_mobile()
