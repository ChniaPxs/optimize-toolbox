import tkinter as tk
# ===== 蓝白水彩风格（与背景插画一致）=====
# TRANS：全局透明色。配合 root.attributes("-transparentcolor", TRANS)，
# 所有以此色为背景的容器都会透明，透出底层背景图；文字/边框不受影响。
TRANS = "#010102"
BG_DEEP = TRANS          # 侧边栏 / 头部（透明，透出背景图）
BG_MAIN = TRANS          # 主背景（透明）
BG_CARD = TRANS          # 卡片（透明，透出背景图）
BG_CARD2 = TRANS         # 卡片交替（透明）
BG_HOVER = TRANS         # 悬停（透明）
BORDER = "#bfd9f5"       # 边框 淡蓝（不透明，勾勒轮廓）
BORDER_LT = "#9cc4ee"    # 亮边框
ACCENT = "#2f6fed"       # 主色 海蓝
ACCENT_LT = "#5b8ff5"    # 主色亮
CYAN = "#0ea5e9"         # 天蓝
GREEN = "#0fb981"        # 清新绿
ORANGE = "#f59e0b"
RED = "#ef4444"
PINK = "#ec4899"
PURPLE = "#8b5cf6"
TEXT = "#1e2a44"         # 深蓝黑 主文字
TEXT_DIM = "#3d5470"     # 次级文字
TEXT_MUT = "#6b82a0"     # 弱化文字
F_TITLE = ("Microsoft YaHei UI", 17, "bold")
F_HEAD = ("Microsoft YaHei UI", 13, "bold")
F_SUB = ("Microsoft YaHei UI", 10)
F_BODY = ("Microsoft YaHei UI", 9)
F_NUM = ("Microsoft YaHei UI", 27, "bold")
F_MONO = ("Consolas", 10)
def round_rect(cv, x1, y1, x2, y2, r, **kw):
    r = max(0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    pts = [x1+r, y1, x2-r, y1, x2, y1, x2, y1+r, x2, y2-r, x2, y2,
           x2-r, y2, x1+r, y2, x1, y2, x1, y2-r, x1, y1+r, x1, y1]
    return cv.create_polygon(pts, smooth=True, **kw)
def _lighten(hex_color, amount=22):
    hex_color = hex_color.lstrip("#")
    r = min(255, int(hex_color[0:2], 16) + amount)
    g = min(255, int(hex_color[2:4], 16) + amount)
    b = min(255, int(hex_color[4:6], 16) + amount)
    return "#{:02x}{:02x}{:02x}".format(r, g, b)
class TitleBar:
    """页面标题栏：标题 + 副标题，颜色可指定"""
    def __init__(self, parent, title, subtitle="", color=ACCENT, bg=None):
        self.frame = tk.Frame(parent, bg=bg or parent.cget("bg"))
        self.title = tk.Label(self.frame, text=title, font=F_HEAD, bg=self.frame.cget("bg"), fg=color)
        self.title.pack(anchor="w")
        if subtitle:
            self.sub = tk.Label(self.frame, text=subtitle, font=F_BODY,
                                bg=self.frame.cget("bg"), fg=TEXT_MUT)
            self.sub.pack(anchor="w", pady=(2, 0))
        else:
            self.sub = None
    def pack(self, **kw):
        self.frame.pack(**kw)
        return self
class Dot:
    def __init__(self, parent, color=TEXT_MUT, size=10):
        self.cv = tk.Canvas(parent, width=size, height=size, bg=parent.cget("bg"), highlightthickness=0)
        self.cv.create_oval(1, 1, size-1, size-1, fill=color, outline="")
    def set_color(self, color):
        self.cv.itemconfigure(0, fill=color)
    def pack(self, **kw):
        self.cv.pack(**kw)
        return self
class Section:
    def __init__(self, parent, text, color=ACCENT, bg=None):
        self.frame = tk.Frame(parent, bg=bg or parent.cget("bg"))
        self.label = tk.Label(self.frame, text=text, font=F_SUB, bg=self.frame.cget("bg"), fg=color)
        self.label.pack(side=tk.LEFT)
    def pack(self, **kw):
        self.frame.pack(**kw)
        return self
class Card:
    def __init__(self, parent, fill=None, radius=12, padx=12, pady=10):
        bg = fill or parent.cget("bg")
        # 卡片透明透出背景图，用淡蓝描边勾勒轮廓
        self.frame = tk.Frame(parent, bg=bg, highlightthickness=1,
                              highlightbackground=BORDER, highlightcolor=BORDER)
        self.body = tk.Frame(self.frame, bg=bg)
        self._radius = radius
        self._padx = padx
        self._pady = pady
    def pack(self, **kw):
        self.frame.pack(**kw)
        self.body.pack(fill=tk.BOTH, expand=True, padx=self._padx, pady=self._pady)
        return self
    def grid(self, **kw):
        self.frame.grid(**kw)
        self.body.pack(fill=tk.BOTH, expand=True, padx=self._padx, pady=self._pady)
        return self
    def bind(self, sequence, func):
        self.frame.bind(sequence, func)
        return self
    def configure(self, **kw):
        self.frame.configure(**kw)
        return self
    def itemconfigure(self, *args, **kw):
        # 兼容 Canvas 风格调用：outline/width 映射为 Frame 高亮描边
        if "outline" in kw:
            self.frame.configure(highlightbackground=kw.pop("outline"))
        if "width" in kw:
            w = kw.pop("width")
            self.frame.configure(highlightthickness=1 if w else 0)
        if kw:
            self.frame.configure(**kw)
        return self
    def sync(self):
        pass
class RoundedButton:
    """ghost 按钮：透明底 + 彩色文字 + 彩色描边，透出背景图；悬停时实体高亮"""
    def __init__(self, parent, text, command=None, bg=None, fg=TEXT, padx=12, pady=4, font=None):
        base = bg or BG_HOVER
        self._base = base
        fg_color = fg if fg is not TEXT else (base if base not in (TRANS, "#010102") else TEXT)
        self.btn = tk.Button(parent, text=text, command=command,
                             bg=TRANS, fg=fg_color,
                             activebackground=base, activeforeground="#ffffff",
                             font=font or F_BODY, relief="flat", cursor="hand2",
                             padx=padx, pady=pady,
                             highlightthickness=1, highlightbackground=base,
                             highlightcolor=base)
        self.btn.bind("<Enter>", lambda e: self.btn.configure(bg=base, fg="#ffffff"))
        self.btn.bind("<Leave>", lambda e: self.btn.configure(bg=TRANS, fg=fg_color))
        self.btn.pack(side=tk.LEFT, padx=3)
    def pack(self, **kw):
        self.btn.pack(**kw)
        return self
    def set_text(self, text):
        self.btn.configure(text=text)
    def set_state(self, state):
        self.btn.configure(state=state)
class Pill:
    def __init__(self, parent, text, bg=None, fg=ACCENT, font=None):
        self.frame = tk.Frame(parent, bg=bg or BG_HOVER, height=22)
        self.frame.pack_propagate(False)
        self.label = tk.Label(self.frame, text=text, font=font or F_BODY, bg=self.frame.cget("bg"), fg=fg)
        self.label.pack(expand=True)
    def pack(self, **kw):
        self.frame.pack(**kw)
        return self
class MetricBar:
    """横向进度条：set(ratio, color) 更新"""
    def __init__(self, parent, width=150, height=8, fill=ACCENT, bg=None):
        self._fill = fill
        self.cv = tk.Canvas(parent, width=width, height=height,
                            bg=bg or BG_HOVER, highlightthickness=0, bd=0)
        self._bar = self.cv.create_rectangle(0, 0, 0, height, fill=fill, outline="")
        self._w = width
    def set(self, ratio, color=None):
        ratio = max(0.0, min(1.0, ratio if ratio is not None else 0.0))
        w = max(1, int(self._w * ratio))
        self.cv.coords(self._bar, 0, 0, w, self.cv.winfo_reqheight() or 8)
        self.cv.itemconfigure(self._bar, fill=color or self._fill)
    def pack(self, **kw):
        self.cv.pack(**kw)
        return self
class Toggle:
    """开关：command(value_bool)；on_color 高亮色"""
    def __init__(self, parent, command=None, on_color=ACCENT, off_color=None, size=(44, 22)):
        self._on = False
        self._cmd = command
        self._on_color = on_color
        self._off_color = off_color or BG_HOVER
        self._size = size
        self.cv = tk.Canvas(parent, width=size[0], height=size[1],
                            bg=parent.cget("bg"), highlightthickness=0, bd=0)
        self.cv.bind("<Button-1>", lambda _e: self.toggle())
        self._draw()
    def _draw(self):
        w, h = self._size
        r = h // 2
        bg = self._on_color if self._on else self._off_color
        self.cv.delete("all")
        self.cv.create_oval(1, 1, h - 1, h - 1, fill=bg, outline="")
        self.cv.create_oval(w - h + 1, 1, w - 1, h - 1, fill=bg, outline="")
        self.cv.create_rectangle(r, 1, w - r, h - 1, fill=bg, outline="")
        knob_x = w - h + 3 if self._on else 3
        self.cv.create_oval(knob_x, 3, knob_x + h - 6, h - 3, fill="#f1f5f9", outline="")
    def toggle(self):
        self._on = not self._on
        self._draw()
        if self._cmd:
            try:
                self._cmd(self._on)
            except Exception:
                pass
    def get(self):
        return self._on
    def set(self, value):
        self._on = bool(value)
        self._draw()
    def pack(self, **kw):
        self.cv.pack(**kw)
        return self


# ================= Canvas 原生绘制（单窗口皮肤，背景图与 UI 元素同窗口渲染） =================

def c_font(size=12, bold=False):
    return ("Microsoft YaHei UI", size, "bold" if bold else "normal")


def c_round(cv, x1, y1, x2, y2, r=10, fill=None, outline=None, width=1, tags=None):
    """Canvas 圆角矩形"""
    r = max(0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
           x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return cv.create_polygon(pts, smooth=True, fill=fill, outline=outline, width=width, tags=tags)


def _is_whiteish(color):
    """判断颜色是否接近白色（白字不需要白描边）"""
    if color is None:
        return True
    try:
        c = str(color).lower()
        if c in ("white", "#fff", "#ffffff"):
            return True
        if c.startswith("#") and len(c) == 7:
            r = int(c[1:3], 16); g = int(c[3:5], 16); b = int(c[5:7], 16)
            return r > 235 and g > 235 and b > 235
    except Exception:
        pass
    return False


def c_text(cv, x, y, text, size=12, bold=False, color=TEXT, anchor="w", tags=None,
           font=None, outline=True):
    """Canvas 文字。outline=True 时加白色描边（4 方向偏移白字 + 主字），
    让汉字在插画背景上更清晰易辨，不遮挡背景。"""
    if font is None:
        font = c_font(size, bold)
    if outline and not _is_whiteish(color):
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            cv.create_text(x + dx, y + dy, text=text, font=font, fill="#ffffff",
                           anchor=anchor, tags=tags)
    return cv.create_text(x, y, text=text, font=font, fill=color,
                          anchor=anchor, tags=tags)


def c_card(cv, x, y, w, h, radius=12, outline=BORDER, width=1):
    """透明卡片：只画淡蓝描边，内部透出背景图"""
    return c_round(cv, x, y, x + w, y + h, r=radius, outline=outline, width=width, fill="")


def c_section(cv, x, y, text, color=ACCENT, size=13):
    """小节标题：左侧色条 + 文字"""
    c_round(cv, x, y - 9, x + 4, y + 9, r=2, fill=color, outline="")
    return c_text(cv, x + 14, y, text, size=size, bold=True, color=TEXT)


def c_titlebar(cv, x, y, title, sub=None, color=ACCENT):
    """页标题 + 副标题（返回副标题 item）"""
    c_text(cv, x, y, title, size=20, bold=True, color=TEXT)
    if sub:
        return c_text(cv, x, y + 28, sub, size=11, color=TEXT_MUT)
    return None


def c_wrap(cv, x, y, text, size=10, color=TEXT_MUT, max_w=460, line_h=18):
    """自动换行文本（按近似字符宽换行），返回 item 列表"""
    items = []
    if not text:
        return items
    ch = size * 1.06
    lines = []
    for para in text.split("\n"):
        cur = ""
        for c in para:
            if len(cur) * ch > max_w:
                lines.append(cur)
                cur = c
            else:
                cur += c
        lines.append(cur)
    yy = y
    for ln in lines:
        items.append(c_text(cv, x, yy, ln, size=size, color=color))
        yy += line_h
    return items


class CanvasBtn:
    """Canvas 原生按钮：圆角 + 文字，ghost 风格（透明底+彩色描边，hover 填充）。
    支持 set_text / set_color / set_state / bind_click。"""

    def __init__(self, cv, x, y, w, h, text, color, command=None, size=11,
                 radius=14, solid=False, fg="#ffffff"):
        self.cv = cv
        self.color = color
        self._solid = solid
        self._disabled = False
        self._bg_item = c_round(cv, x, y, x + w, y + h, r=radius,
                                fill=color if solid else "", outline="" if solid else color, width=1)
        self._tx_item = c_text(cv, x + w / 2, y + h / 2 + 1, text, size=size, bold=True,
                               color=fg if solid else color, anchor="center",
                               outline=not solid)
        # 透明命中区：覆盖整个按钮矩形（ghost 按钮圆角多边形只有描边可点，
        # 空白区域需要这个透明矩形才能整块响应点击）
        self._hit_item = cv.create_rectangle(x, y, x + w, y + h,
                                             fill="", outline="")
        self._bind(command)

    def _bind(self, command):
        for it in (self._bg_item, self._tx_item, self._hit_item):
            self.cv.tag_bind(it, "<Enter>", lambda e: self._enter())
            self.cv.tag_bind(it, "<Leave>", lambda e: self._leave())
            if command:
                self.cv.tag_bind(it, "<Button-1>", lambda e: self._click(command))

    def _click(self, command):
        if not self._disabled:
            command()

    def _enter(self):
        self.cv.configure(cursor="hand2")
        if not self._disabled and not self._solid:
            self.cv.itemconfigure(self._bg_item, fill=self.color)
            self.cv.itemconfigure(self._tx_item, fill="#ffffff")

    def _leave(self):
        self.cv.configure(cursor="")
        if not self._disabled and not self._solid:
            self.cv.itemconfigure(self._bg_item, fill="")
            self.cv.itemconfigure(self._tx_item, fill=self.color)

    def set_text(self, text):
        self.cv.itemconfigure(self._tx_item, text=text)

    def set_color(self, color):
        self.color = color
        if self._solid:
            self.cv.itemconfigure(self._bg_item, fill=color)
        else:
            self.cv.itemconfigure(self._bg_item, outline=color)
            self.cv.itemconfigure(self._tx_item, fill=color)

    def set_state(self, state):
        self._disabled = (state == "disabled")
        st = "hidden" if self._disabled else "normal"
        self.cv.itemconfigure(self._bg_item, state=st)
        self.cv.itemconfigure(self._tx_item, state=st)
        self.cv.itemconfigure(self._hit_item, state=st)