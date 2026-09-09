# -*- coding: utf-8 -*-
import os
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
import sys
import ctypes
import threading
import subprocess as _subprocess

# ---- 全局隐藏子进程控制台窗口（Windows 打包版必须，否则网络检测/清理/ADB 会弹命令窗） ----
_orig_subprocess_run = _subprocess.run


def _silent_run(*args, **kwargs):
    if sys.platform == "win32":
        kwargs.setdefault("creationflags", 0x08000000)  # CREATE_NO_WINDOW
    return _orig_subprocess_run(*args, **kwargs)


_subprocess.run = _silent_run
import tkinter as tk
from tkinter import messagebox
from collections import deque

HEADER_H = 58
SIDEBAR_W = 210
RIGHT_W = 400

# ===== 蓝白水彩风格（背景插画 + 原生 Canvas 皮肤）=====
BG = "#dceafc"           # 窗口兜底色（背景图不可用时的纯色）
BORDER = "#bfd9f5"
ACCENT = "#2f6fed"
CYAN = "#0ea5e9"
GREEN = "#0fb981"
ORANGE = "#f59e0b"
RED = "#ef4444"
PURPLE = "#8b5cf6"
TEXT = "#1e2a44"
TEXT_DIM = "#3d5470"
TEXT_MUT = "#6b82a0"
TERM_FG = "#0d5c46"      # 终端文字（深绿，浮于浅色背景上可读）
TERM_PROMPT = "#0fb981"
TERM_INPUT = "#134e5e"   # 输入文字（深青）

NAV_ITEMS = [("首页", "home", CYAN), ("网络优化", "network", CYAN),
             ("智能清理", "cleanup", GREEN), ("性能监控", "monitor", PURPLE),
             ("应用卸载", "apps", ORANGE), ("关于", "about", ACCENT)]

_TERM_FONT = ("Microsoft YaHei UI", 10)
_RES_FONT = ("Microsoft YaHei UI", 10)
_LINE_H = 17
_RES_LINE_H = 16


class OptimizeApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("优化工具箱 v6.1")
        # 窗口图标：与 exe 桌面图标一致（蓝发少女水彩头像），替代 Tk 默认羽毛图标。
        # 用 iconphoto + PNG 图片（Tk 原生可靠支持），不用 iconbitmap（.ico 含 PNG 压缩条目可能读取失败）
        try:
            from config import ASSETS_DIR
            from PIL import Image, ImageTk
            _ic = str(ASSETS_DIR / "icon_win.png")
            if os.path.exists(_ic):
                self._win_icon = ImageTk.PhotoImage(Image.open(_ic))
                self.root.iconphoto(True, self._win_icon)
        except Exception:
            pass
        self.root.geometry("1280x800")
        self.root.minsize(1024, 660)
        self.root.configure(bg=BG)
        self.root.resizable(True, True)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        from core import NetworkOptimizer, SmartCleaner, PerformanceMonitor
        from utils.adb_helper import ADBHelper
        from ui import background
        self.bg_module = background
        self._bg_photo = None
        self._win_w = 1280
        self._win_h = 800
        self.net_optimizer = NetworkOptimizer()
        self.smart_cleaner = SmartCleaner()
        self.perf_monitor = PerformanceMonitor()
        self.adb = ADBHelper()
        self._current_page = None
        self._pages = {}
        self._cur_page_id = "home"
        self._is_mobile = False  # 全局设备操作模式：True=手机 / False=电脑（首页切换，顶栏/首页共用）
        self._nav_items = {}
        self._redraw_id = None
        self._term_h = 300
        self._drag_y0 = 0
        self._drag_h0 = 300
        self._build_layout()
        self._build_terminal()
        self._create_page("home", "HomePage", {"adb": self.adb})
        self.root.bind("<Configure>", self._on_root_resize)
        self._chk_adb()
        self.root.after(30000, self._periodic_chk)
        # 启动时先在屏幕外映射窗口：内容持续有效，绘制完成后再移入屏幕，
        # 杜绝“窗口映射到内容绘制完成之间”的黑窗/空白（紊乱）窗口期
        self.root.geometry("1280x800+3200+3200")
        self.root.update_idletasks()
        self.root.after(150, self._show_ready)

    def _show_ready(self):
        """背景与内容就绪后把窗口移入屏幕（杜绝启动瞬间的黑窗/空白/紊乱）"""
        try:
            self._redraw_all()
            self.root.update_idletasks()
        except Exception as e:
            self._log_err("_show_ready", e)
        try:
            w = max(1024, self.root.winfo_width())
            h = max(660, self.root.winfo_height())
            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()
            x = max(0, (sw - w) // 2 - 20)
            y = max(0, (sh - h) // 2 - 20)
            self.root.geometry("%dx%d+%d+%d" % (w, h, x, y))
            self.root.lift()
            self.root.update_idletasks()
        except Exception:
            pass
        # 保险：窗口显示后再补一次重绘，杜绝最大化/合成器时序导致的空白
        self.root.after(600, self._safe_repaint)

    def _safe_repaint(self):
        """显示后的保险重绘"""
        try:
            self._redraw_all()
        except Exception:
            pass

    # ================= 布局 =================
    def _build_layout(self):
        self.header = tk.Canvas(self.root, height=HEADER_H, bg=BG, highlightthickness=0, bd=0)
        self.header.pack(fill=tk.X)
        self.sidebar = tk.Canvas(self.root, width=SIDEBAR_W, bg=BG, highlightthickness=0, bd=0)
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y)
        self.right_panel = tk.Canvas(self.root, width=RIGHT_W, bg=BG, highlightthickness=0, bd=0,
                                     takefocus=1)
        self.right_panel.pack(side=tk.RIGHT, fill=tk.Y)
        self.right_panel.bind("<Button-1>", self._right_click)
        self.right_panel.bind("<MouseWheel>", self._on_right_scroll)

    # ================= 终端数据（日志与输入文字全部 Canvas 原生绘制，不遮挡背景） =================
    def _build_terminal(self):
        self.term_output = self  # 兼容旧接口（页面只用 hasattr 判断）
        self._term_lines = deque(maxlen=400)   # [(text, color)]
        self._res_lines = deque(maxlen=400)
        self._term_offset = 0
        self._res_offset = 0
        self._term_history = deque(maxlen=50)
        self._history_index = -1
        self._term_input_item = None
        self._tf_font = None
        # 隐藏输入控件（1px 视觉不可见）：负责捕获键盘与中文输入法，
        # 输入文字由 Canvas 原生绘制在背景上，因此输入区不遮挡背景。
        self.term_entry = tk.Entry(self.right_panel, width=1, bg="#f4f9ff", fg="#134e5e",
                                   font=("Consolas", 10), relief="flat", bd=0,
                                   insertbackground=CYAN, highlightthickness=0, takefocus=1)
        self.term_entry.bind("<Return>", self._entry_return)
        self.term_entry.bind("<Up>", self._entry_up)
        self.term_entry.bind("<Down>", self._entry_down)
        self.term_entry.bind("<KeyRelease>", self._entry_refresh)
        self.term_entry.place(x=-1, y=-1, width=1, height=22)
        self._term_log("优化工具箱命令窗口 -- 输入 help 查看可用命令", CYAN)

    def _term_log(self, text, color=TEXT):
        for ln in (text or "").split("\n"):
            self._term_lines.append((ln or " ", color))
        self._term_offset = 0
        if getattr(self, "right_panel", None):
            try:
                self._paint_right()
            except Exception:
                pass

    def _res_log(self, text):
        for ln in (text or "").split("\n"):
            self._res_lines.append(ln or " ")
        self._res_offset = 0
        if getattr(self, "right_panel", None):
            try:
                self._paint_right()
            except Exception:
                pass

    def _clear_terminal(self):
        self._term_lines.clear()
        self._term_offset = 0
        try:
            self.term_entry.delete(0, tk.END)
        except Exception:
            pass
        self._paint_right()

    def _clear_result(self):
        """清空运行结果区"""
        self._res_lines.clear()
        self._res_offset = 0
        self._paint_right()

    # ================= 页面 =================
    def _create_page(self, page_id, class_name, kwargs):
        from ui.pages import HomePage, NetworkPage, CleanupPage, MonitorPage, AboutPage, AppsPage
        page_classes = {"HomePage": HomePage, "NetworkPage": NetworkPage,
                        "CleanupPage": CleanupPage, "MonitorPage": MonitorPage,
                        "AboutPage": AboutPage, "AppsPage": AppsPage}
        cls = page_classes.get(class_name)
        if cls is None:
            return
        old_page = self._current_page
        # ---- 页面已缓存：零耗时切换（不重建、不销毁，彻底避免重叠） ----
        if page_id in self._pages:
            page = self._pages[page_id]
            if old_page is not None and old_page is not page:
                old_page.pack_forget()
            page.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            self._current_page = page
            self._nav_select(page_id)
            self._schedule_redraw()
            return
        # ---- 首次创建并缓存 ----
        if old_page is not None:
            old_page.pack_forget()  # 先隐藏旧页面，避免创建期间重叠
        kwargs["app"] = self
        page = cls(self.root, **kwargs)
        page.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._current_page = page
        self._pages[page_id] = page  # 缓存复用，之后切换零耗时
        self._nav_select(page_id)
        self._schedule_redraw()

    def switch_page(self, page_id):
        import config
        page_map = {"home": ("HomePage", {"adb": self.adb}),
                    "network": ("NetworkPage", {"net_optimizer": self.net_optimizer, "log": config.log}),
                    "cleanup": ("CleanupPage", {"cleaner": self.smart_cleaner, "log": config.log, "adb": self.adb}),
                    "monitor": ("MonitorPage", {"perf_monitor": self.perf_monitor, "adb": self.adb}),
                    "apps": ("AppsPage", {"adb": self.adb}),
                    "about": ("AboutPage", {})}
        if page_id in page_map:
            class_name, kwargs = page_map[page_id]
            self._create_page(page_id, class_name, kwargs)

    def _nav_select(self, page_id):
        self._cur_page_id = page_id
        from ui import theme as T
        for pid, (bg, bar, tx) in getattr(self, "_nav_items", {}).items():
            sel = (pid == page_id)
            try:
                self.sidebar.itemconfigure(bg, fill="#e3eeff" if sel else "")
                self.sidebar.itemconfigure(bar, fill=ACCENT if sel else "")
                self.sidebar.itemconfigure(tx, fill=ACCENT if sel else TEXT_DIM)
                self.sidebar.itemconfigure(tx, font=T.c_font(11, sel))
            except Exception:
                pass

    # ================= 背景与重绘 =================
    def _on_root_resize(self, e):
        if e.widget is not self.root:
            return
        self._schedule_redraw()

    def _schedule_redraw(self):
        if self._redraw_id:
            try:
                self.root.after_cancel(self._redraw_id)
            except Exception:
                pass
        self._redraw_id = self.root.after(250, self._redraw_all)

    def _log_err(self, where, e):
        """异常写入 _debug.log（exe 无控制台，静默异常难以定位）"""
        try:
            import traceback
            with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "_debug.log"), "a", encoding="utf-8") as f:
                f.write("[%s] %s: %r\n%s\n" % (time.strftime("%m-%d %H:%M:%S"),
                                                 where, e, traceback.format_exc()))
        except Exception:
            pass

    def _redraw_all(self):
        self._redraw_id = None
        try:
            w = self.root.winfo_width()
            h = self.root.winfo_height()
            if w < 30 or h < 30:
                self._schedule_redraw()
                return
            self._win_w, self._win_h = w, h
            # 强制每次新建背景图：PyInstaller 环境下缓存 PhotoImage 在
            # 第二次重绘时 Tk 侧可能失效（画面显示兜底色），新建的一定有效
            try:
                self.bg_module.invalidate_cache()
            except Exception:
                pass
            self._bg_photo = self.bg_module.scaled_photo(w, h)
            self._paint_header()
            self._paint_sidebar()
            try:
                self._paint_right()
            except Exception as e:
                self._log_err("_paint_right", e)
                # 即使内容绘制失败，也要保证右面板背景铺上
                try:
                    from ui import theme as T
                    cv = self.right_panel
                    cv.delete("all")
                    self.bg_module.paint(cv, self._bg_photo,
                                         self._win_w - RIGHT_W, HEADER_H)
                except Exception:
                    pass
            if self._current_page:
                try:
                    self._current_page.redraw(self._bg_photo, SIDEBAR_W, HEADER_H)
                    self._current_page.after(60, self._current_page.on_show)
                except Exception as e:
                    self._log_err("page_redraw", e)
        except Exception as e:
            self._log_err("_redraw_all", e)

    def _paint_header(self):
        from ui import theme as T
        cv = self.header
        w = cv.winfo_width()
        cv.delete("all")
        self.bg_module.paint(cv, self._bg_photo, 0, 0)
        T.c_text(cv, 20, 29, "优化工具箱 v6.1", size=13, bold=True, color=CYAN)
        x = w - 16
        ok = bool(getattr(self, "_adb_ok", False))
        dot_x = x - 216
        self._dot_item = cv.create_oval(dot_x, 20, dot_x + 8, 28,
                                        fill=GREEN if ok else TEXT_MUT, outline="")
        self._status_item = T.c_text(cv, dot_x - 14, 24,
                                     "已连接" if ok else "未连接", size=9,
                                     color=GREEN if ok else TEXT_MUT)
        # 评分组：标签与数字分开留白，避免"综合评分--"连读成乱码
        T.c_text(cv, x - 172, 24, "综合评分", size=9, color=TEXT_DIM)
        self._score_item = T.c_text(cv, x - 96, 24, "--", size=11, bold=True,
                                    color=CYAN, anchor="e")
        # 设备：显示全局操作模式（手机模式/电脑模式），右对齐最右
        mobile = bool(getattr(self, "_is_mobile", False))
        self._dev_item = T.c_text(cv, x - 30, 24, "手机" if mobile else "PC",
                                  size=9, bold=True,
                                  color=CYAN if mobile else ORANGE, anchor="e")

    def _paint_sidebar(self):
        from ui import theme as T
        cv = self.sidebar
        w = cv.winfo_width()
        h = cv.winfo_height()
        cv.delete("all")
        self.bg_module.paint(cv, self._bg_photo, 0, HEADER_H)
        T.c_text(cv, 20, 32, "优化工具箱", size=14, bold=True, color=CYAN)
        T.c_text(cv, 20, 54, "PC + 手机 统一优化", size=9, color=TEXT_DIM)
        T.c_round(cv, 20, 68, w - 20, 69, r=0, fill=BORDER, outline="")
        y = 92
        self._nav_items = {}
        for label, pid, color in NAV_ITEMS:
            sel = (pid == self._cur_page_id)
            # 整个导航项高亮：当前页常亮浅蓝块 + 左侧竖条 + 蓝色粗体文字
            bg = cv.create_rectangle(10, y, w - 10, y + 40, outline="",
                                     fill="#e3eeff" if sel else "")
            bar = T.c_round(cv, 14, y + 9, 17, y + 31, r=2,
                            fill=ACCENT if sel else "", outline="")
            tx = T.c_text(cv, 32, y + 20, label, size=11, bold=sel,
                          color=ACCENT if sel else TEXT_DIM)
            for it in (bg, bar, tx):
                cv.tag_bind(it, "<Button-1>", lambda e, p=pid: self.switch_page(p))
                cv.tag_bind(it, "<Enter>", lambda e, p=pid: self._nav_hover(p, True))
                cv.tag_bind(it, "<Leave>", lambda e, p=pid: self._nav_hover(p, False))
            self._nav_items[pid] = (bg, bar, tx)
            y += 44
        cv.configure(cursor="")  # 重绘后恢复全局光标，避免残留

    def _nav_hover(self, pid, on):
        """非当前导航项 hover 反馈：整项淡蓝 + 文字变蓝"""
        if pid == self._cur_page_id:
            return
        d = self._nav_items.get(pid)
        if not d:
            return
        cv = self.sidebar
        bg, bar, tx = d
        try:
            if on:
                cv.itemconfigure(bg, fill="#d8e8ff")
                cv.itemconfigure(bar, fill=ACCENT)
                cv.itemconfigure(tx, fill=ACCENT)
                cv.configure(cursor="hand2")
            else:
                cv.itemconfigure(bg, fill="")
                cv.itemconfigure(bar, fill="")
                cv.itemconfigure(tx, fill=TEXT_DIM)
                cv.configure(cursor="")
        except Exception:
            pass

    # ---------- 右侧面板：终端 + 运行结果（全部 Canvas 原生，背景处处透出） ----------
    def _paint_right(self):
        from ui import theme as T
        cv = self.right_panel
        w = cv.winfo_width()
        h = cv.winfo_height()
        if w < 30 or h < 30:
            return
        cv.delete("all")
        try:
            self.bg_module.paint(cv, self._bg_photo, self._win_w - RIGHT_W, HEADER_H)
        except Exception as e:
            self._log_err("_paint_right.bg", e)
        # 终端标题 + 清空
        T.c_text(cv, 14, 22, "[TERMINAL] 命令窗口", size=10, bold=True, color=GREEN)
        T.CanvasBtn(cv, w - 58, 10, 46, 22, "清空", BORDER, self._clear_terminal,
                    size=9, radius=9)
        th = self._term_h
        # 终端日志：文字直接浮于背景插画上
        self._draw_term_lines(cv, 8, 38, w - 16, th - 44)
        # 分隔条（可拖动）
        self._sep_item = T.c_round(cv, 8, th, w - 8, th + 6, r=3, fill="#9cc4ee", outline="")
        cv.tag_bind(self._sep_item, "<Button-1>", self._drag_start)
        cv.tag_bind(self._sep_item, "<B1-Motion>", self._drag_move)
        cv.tag_bind(self._sep_item, "<Enter>", lambda e: cv.configure(cursor="sb_v_double_arrow"))
        cv.tag_bind(self._sep_item, "<Leave>", lambda e: cv.configure(cursor=""))
        # 运行结果标题 + 清空（标题存 id，拖动时实时跟随）
        self._res_title_item = T.c_text(cv, 14, th + 18, "[RUN RES] 运行结果", size=10, bold=True, color=CYAN)
        T.CanvasBtn(cv, w - 58, th + 8, 46, 22, "清空", BORDER, self._clear_result,
                    size=9, radius=9)
        self._draw_res_lines(cv, 8, th + 34, w - 16, h - th - 42)
        cv.configure(cursor="")  # 重绘后恢复全局光标，避免"任何位置都是上下箭头"

    def _draw_term_lines(self, cv, x, y, w, h):
        """终端：PS> 输入行紧跟标题（靠近"命令窗口"），日志在下方；
        输入文字 Canvas 原生绘制浮于背景上，隐藏 1px Entry 仅负责捕获键盘/中文IME"""
        from ui import theme as T
        ch = 8
        max_chars = max(10, int(w / ch))
        in_y = y + 28  # 输入行中心，紧跟标题下方
        # PS> 提示 + 输入文字（来自隐藏 Entry，原生绘制不遮挡背景）
        T.c_text(cv, x, in_y, "PS> ", size=10, bold=True, color=TERM_PROMPT)
        inp = self.term_entry.get()
        inp = self._fit_text(inp, w - 4 * ch - 6, 10)
        self._term_input_item = T.c_text(cv, x + 4 * ch, in_y, inp, size=10, color=TERM_INPUT)
        # 光标竖线（输入文字末尾）
        cw = len(inp) * ch
        self._term_caret_item = cv.create_line(
            x + 4 * ch + cw + 2, in_y - 8, x + 4 * ch + cw + 2, in_y + 8,
            fill=CYAN, width=1)
        # 隐藏 Entry 移到输入行位置（1px，视觉不可见；供键盘输入与 IME 候选框定位）
        try:
            self.term_entry.place(x=max(1, x + 4 * ch), y=max(1, in_y - 11),
                                  width=1, height=22)
        except Exception:
            pass
        # 日志区（从 PS 下方开始，最新在底部；行少时紧贴 PS，多时滚动显示最新）
        log_top = y + 44
        log_h = max(20, (y + h) - log_top - 4)
        rows = max(1, log_h // _LINE_H)
        n_lines = len(self._term_lines)
        if n_lines <= rows:
            idx0 = 0
        else:
            idx0 = n_lines - rows - self._term_offset
            if idx0 < 0:
                idx0 = 0
        yy = log_top + _LINE_H // 2
        for i in range(rows):
            idx = idx0 + i
            if idx >= n_lines:
                break
            text, color = self._term_lines[idx]
            text = self._fit_text(text, w, 10)
            T.c_text(cv, x, yy, text, size=10, color=color, font=_TERM_FONT)
            yy += _LINE_H

    def _fit_text(self, text, max_w, size=10, family="Microsoft YaHei UI"):
        """按字体实际宽度截断文本（适配中文/英文混合），超宽加省略号"""
        if not text:
            return text
        try:
            if self._tf_font is None:
                import tkinter.font as tkfont
                self._tf_font = tkfont.Font(root=self.root, family=family, size=size)
            f = self._tf_font
            if f.measure(text) <= max_w:
                return text
            lo, hi = 0, len(text)
            while lo < hi:
                mid = (lo + hi + 1) // 2
                if f.measure(text[:mid] + "…") <= max_w:
                    lo = mid
                else:
                    hi = mid - 1
            return text[:lo] + "…"
        except Exception:
            lim = max(8, int(max_w / 12))
            return text[:lim] + "…" if len(text) > lim else text

    def _draw_res_lines(self, cv, x, y, w, h):
        """运行结果日志：最新在底部"""
        from ui import theme as T
        rows = max(1, h // _RES_LINE_H)
        lines = list(self._res_lines)
        start = len(lines) - rows - self._res_offset
        if start < 0:
            start = 0
        yy = y + _RES_LINE_H // 2
        for i in range(start, min(len(lines), start + rows)):
            text = self._fit_text(lines[i], w, 10)
            T.c_text(cv, x, yy, text, size=10, color=TEXT_DIM, font=_RES_FONT)
            yy += _RES_LINE_H

    def _layout_right_widgets(self):
        pass

    # ---------- 右面板交互 ----------
    def _drag_start(self, _e=None):
        self._drag_y0 = _e.y_root if _e else 0
        self._drag_h0 = self._term_h

    def _drag_move(self, e):
        dy = e.y_root - self._drag_y0
        self._term_h = max(50, min(self._win_h - HEADER_H - 50, self._drag_h0 + dy))
        # 轻量实时反馈：分隔条 + 运行结果标题跟手移动（不重建，松手后完整重绘）
        try:
            cv = self.right_panel
            w = cv.winfo_width()
            th = self._term_h
            if self._sep_item:
                cv.coords(self._sep_item, 8, th, w - 8, th + 6)
            if getattr(self, "_res_title_item", None):
                cv.coords(self._res_title_item, 14, th + 18)
        except Exception:
            pass
        if getattr(self, "_drag_redraw_after", None):
            try:
                self.root.after_cancel(self._drag_redraw_after)
            except Exception:
                pass
        self._drag_redraw_after = self.root.after(16, lambda: (setattr(self, '_drag_redraw_after', None), self._paint_right()))

    def _right_click(self, e):
        """点击终端区时聚焦输入框（双保险夺回焦点，阻止默认点击聚焦抢走）"""
        if e.y < self._term_h:
            try:
                self.term_entry.focus_set()
                self.root.after(0, self.term_entry.focus_set)
                self.root.after(50, self._refocus_term)
            except Exception:
                pass
        return "break"

    def _refocus_term(self):
        """确保终端输入框持有焦点"""
        try:
            if self.root.focus_get() is not self.term_entry:
                self.term_entry.focus_set()
        except Exception:
            pass

    def _entry_refresh(self, e=None):
        """按键后刷新输入行显示（Canvas 原生绘制，不遮挡背景）"""
        try:
            self._paint_right()
        except Exception:
            pass
        return None

    def _entry_return(self, e):
        cmd = self.term_entry.get().strip()
        if cmd:
            self._term_history.append(cmd)
            self._history_index = -1
            if cmd.lower() == "clear":
                self._clear_terminal()
            else:
                self._execute_command(cmd)
        else:
            self._term_log("", TEXT)
        self.term_entry.delete(0, tk.END)
        self._term_offset = 0
        self._paint_right()
        return "break"

    def _entry_up(self, e):
        if not self._term_history:
            return "break"
        if self._history_index < 0:
            self._history_index = len(self._term_history)
        self._history_index -= 1
        if self._history_index < 0:
            self._history_index = 0
        self.term_entry.delete(0, tk.END)
        self.term_entry.insert(0, self._term_history[self._history_index])
        return "break"

    def _entry_down(self, e):
        if not self._term_history:
            return "break"
        self._history_index += 1
        if self._history_index >= len(self._term_history):
            self._history_index = len(self._term_history)
            self.term_entry.delete(0, tk.END)
        else:
            self.term_entry.delete(0, tk.END)
            self.term_entry.insert(0, self._term_history[self._history_index])
        return "break"

    def _on_right_scroll(self, e):
        d = int(-e.delta / 120)
        if e.y < self._term_h + 20:
            self._term_offset += d * 3
            self._term_offset = max(0, min(self._term_offset, len(self._term_lines)))
        else:
            self._res_offset += d * 3
            self._res_offset = max(0, min(self._res_offset, len(self._res_lines)))
        self._paint_right()
        return "break"

    BUILD_TS = "2026-09-09 22:20"  # 构建时间戳（About 页显示，用于区分新旧版本）

    # ================= 终端命令（覆盖全部功能，可随时调用） =================
    def _execute_command(self, cmd):
        cmd_lower = cmd.lower().strip()
        parts = cmd_lower.split()
        base = parts[0] if parts else ""
        if base in ("help", "?"):
            self._term_log("可用命令:", CYAN)
            self._term_log("  help / clear / status / optimize", CYAN)
            self._term_log("  scan / clean / monitor / perf", CYAN)
            self._term_log("  game / video / download / dns", CYAN)
            self._term_log("  net-restart / apps / adb / about", CYAN)
            self._term_log("  exit", CYAN)
        elif base == "clear":
            self._clear_terminal()
        elif base == "status":
            self._show_status()
        elif base == "optimize":
            self.quick_optimize()
        elif base == "scan":
            self._cmd_scan()
        elif base == "clean":
            self._cmd_clean()
        elif base == "monitor":
            self._cmd_monitor()
        elif base == "perf":
            self._cmd_perf()
        elif base in ("game", "video", "download"):
            self._cmd_network_mode(base)
        elif base == "net-restart":
            self._cmd_net_restart()
        elif base == "dns":
            self._cmd_dns()
        elif base == "apps":
            self._cmd_apps()
        elif base == "adb":
            self._cmd_adb()
        elif base == "about":
            self.switch_page("about")
            self._term_log("[OK] 已打开关于页", GREEN)
        elif base == "exit":
            self.root.destroy()
        else:
            self._term_log("[INFO] 命令: " + cmd, TEXT)

    # ---------- 终端命令实现（调用引擎，随时可用） ----------
    def _cmd_scan(self):
        """扫描垃圾：后台线程扫描，完成后输出结果并切到清理页"""
        self._term_log("[SCAN] 开始扫描系统垃圾…", CYAN)
        self._res_log("[SCAN] 正在扫描，请稍候…")

        def work():
            try:
                items = self.smart_cleaner.scan_for_junk()
                total = sum(getattr(i, "size", 0) or 0 for i in items)
                self.root.after(0, lambda: self._cmd_scan_done(items, total))
            except Exception as e:
                self.root.after(0, lambda: self._term_log("[ERR] 扫描失败: " + str(e), RED))

        threading.Thread(target=work, daemon=True).start()

    def _cmd_scan_done(self, items, total):
        self._term_log("[SCAN] 完成：共 %d 项垃圾，可释放 %.1f MB" % (len(items), total / 1048576.0), GREEN)
        self._res_log("[SCAN] %d 项垃圾 / %.1f MB" % (len(items), total / 1048576.0))
        self.switch_page("cleanup")

    def _cmd_clean(self):
        """一键清理：切到清理页并触发清理"""
        self._term_log("[CLEAN] 打开智能清理并开始一键清理…", CYAN)
        self.switch_page("cleanup")
        self.root.after(350, self._cmd_clean_go)

    def _cmd_clean_go(self):
        try:
            page = self._current_page
            if page is not None and hasattr(page, "_clean_all"):
                page._clean_all()
            else:
                self._term_log("[ERR] 清理页面未就绪", ORANGE)
        except Exception as e:
            self._term_log("[ERR] 一键清理失败: " + str(e), RED)

    def _cmd_monitor(self):
        """性能监控：输出当前指标并切到监控页"""
        try:
            m = self.perf_monitor.get_system_metrics()
            disk = "%s 可用" % m.storage.free_space if getattr(m.storage, "free_space", "") else "—"
            self._term_log("CPU %.1f%% | 内存 %.1f%% | 磁盘 %s | 电池 %d%%" % (
                m.cpu.usage_percent, m.memory.usage_percent, disk, m.battery.level), CYAN)
            self._res_log("[MONITOR] CPU %.1f%% / 内存 %.1f%% / 电池 %d%%" % (
                m.cpu.usage_percent, m.memory.usage_percent, m.battery.level))
            self.switch_page("monitor")
        except Exception as e:
            self._term_log("[ERR] 监控失败: " + str(e), RED)

    def _cmd_perf(self):
        """性能评分与问题"""
        try:
            score = self.perf_monitor.get_performance_score()
            issues = self.perf_monitor.get_performance_issues() or []
            self._term_log("性能评分: %d/100（问题 %d 项）" % (score, len(issues)), GREEN)
            self._res_log("[PERF] 评分 %d/100" % score)
            for it in issues[:4]:
                self._term_log("  • " + str(it), TEXT)
        except Exception as e:
            self._term_log("[ERR] 性能评估失败: " + str(e), RED)

    def _cmd_network_mode(self, mode):
        """网络场景模式：game / video / download"""
        fn = {"game": self.net_optimizer.enable_game_mode,
              "video": self.net_optimizer.enable_video_mode,
              "download": self.net_optimizer.enable_download_mode}.get(mode)
        if fn is None:
            return
        try:
            r = fn()
            self._finish_opt_result(r, "模式")
        except Exception as e:
            self._term_log("[ERR] 网络优化失败: " + str(e), RED)

    def _cmd_net_restart(self):
        """立即重启网络适配器（使刚写入的 TCP 参数立即生效，无需重启电脑）"""
        self._term_log("[NET] 正在重启网络适配器…", CYAN)
        self._res_log("[NET] 正在重启网络适配器…")
        try:
            ok, msg = self.net_optimizer.restart_network_adapter()
        except Exception as e:
            ok, msg = False, str(e)[:80]
        color = GREEN if ok else ORANGE
        self._term_log(("[OK] " if ok else "[WARN] ") + msg, color)
        self._res_log("[NET] " + msg)

    def _cmd_dns(self):
        """DNS 优化"""
        try:
            r = self.net_optimizer.optimize_dns()
            self._finish_opt_result(r, "DNS")
        except Exception as e:
            self._term_log("[ERR] DNS 优化失败: " + str(e), RED)

    def _finish_opt_result(self, r, label):
        """网络优化结果输出 + 管理员提权询问"""
        color = GREEN if r.success else ORANGE
        self._term_log(("[OK] " if r.success else "[WARN] ") + r.description, color)
        self._res_log("[%s] %s" % (label, r.description))
        if not r.success and ("管理员" in r.description or "权限" in r.description):
            self._term_log("  ⚠ 需要管理员权限：请右键「以管理员身份运行」本程序后重试", ORANGE)
            self._res_log("  ⚠ 需要管理员权限：请右键「以管理员身份运行」本程序后重试")

    def _cmd_apps(self):
        """打开应用卸载页"""
        self._term_log("[APPS] 打开应用卸载页", CYAN)
        self.switch_page("apps")

    def _cmd_adb(self):
        """检查 ADB 设备"""
        try:
            if self.adb and self.adb.connect():
                self._term_log("[ADB] 设备已连接，手机端功能可用", GREEN)
                self._res_log("[ADB] 设备已连接")
            else:
                self._term_log("[ADB] 未检测到设备（请开启 USB 调试）", ORANGE)
                self._res_log("[ADB] 未检测到设备")
        except Exception as e:
            self._term_log("[ERR] ADB 检查失败: " + str(e), RED)

    def _show_status(self):
        try:
            m = self.perf_monitor.get_system_metrics()
            self._term_log("CPU %.1f%% | 内存 %.1f%% | 电池 %d%%" % (
                m.cpu.usage_percent, m.memory.usage_percent, m.battery.level), CYAN)
        except Exception as e:
            self._term_log("[ERR] " + str(e), RED)

    def quick_optimize(self):
        try:
            r = self.net_optimizer.optimize_network()
            color = GREEN if r.success else ORANGE
            self._term_log(("[OK] " if r.success else "[WARN] ") + r.description, color)
            self._res_log("[BOLT] 一键优化: " + r.description)
            if not r.success and ("管理员" in r.description or "权限" in r.description):
                self._term_log("  ⚠ 需要管理员权限：请右键「以管理员身份运行」本程序后重试", ORANGE)
                self._res_log("  ⚠ 需要管理员权限：请右键「以管理员身份运行」本程序后重试")
            return r
        except Exception as e:
            self._term_log("[ERROR] 一键优化失败: " + str(e), RED)
            return None

    # ================= 状态 =================
    def _chk_adb(self):
        try:
            if self.adb.connect():
                self._adb_ok = True
                self.header.itemconfigure(self._dot_item, fill=GREEN)
                self.header.itemconfigure(self._status_item, text="已连接", fill=GREEN)
            else:
                self._adb_ok = False
                self.header.itemconfigure(self._dot_item, fill=TEXT_MUT)
                self.header.itemconfigure(self._status_item, text="未连接", fill=TEXT_MUT)
        except Exception:
            pass

    def _periodic_chk(self):
        self._chk_adb()
        self.root.after(30000, self._periodic_chk)

    def restart_as_admin(self):
        """以管理员身份重新启动当前程序（保留原目录）"""
        try:
            import subprocess
            exe = sys.executable
            script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py")
            ctypes.windll.shell32.ShellExecuteW(
                None, "runas", exe, '"%s"' % script, os.path.dirname(script), 1)
            self.root.after(500, self.root.destroy)
        except Exception as e:
            try:
                messagebox.showerror("提权失败", "无法以管理员身份启动：" + str(e), parent=self.root)
            except Exception:
                pass

    def _on_close(self):
        if messagebox.askokcancel("退出", "确定要退出优化工具箱?"):
            self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = OptimizeApp()
    app.run()
