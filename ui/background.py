# -*- coding: utf-8 -*-
"""窗口背景图模块

在不改变现有深色主题与任何页面布局的前提下，为内容区铺设一张压暗后的背景图。
设计要点：
1. tkinter 普通容器不支持透明，因此背景图铺在页面最底层，深色卡片/面板浮于其上，
   缝隙与留白处透出壁纸（壁纸型 UI）。
2. 原图为浅色插画，统一叠加一层主题深色蒙版压暗，保证与深色 UI 协调、文字可读。
3. 等比缩放 + 居中裁剪（cover），窗口尺寸变化时防抖重绘，且缓存最近一次结果。
4. 任何异常（图片缺失 / Pillow 不可用 / 绘制失败）都静默回退纯色背景，绝不让程序崩溃。
"""
import os
import tkinter as tk

# 主题浅色（与 ui.theme.BG_MAIN 一致，此处独立取值避免循环导入）
_MASK_RGB = (255, 255, 255)   # 白色柔化蒙版：提亮统一亮度，保留水彩质感
_MASK_ALPHA = 15              # 蒙版不透明度 0~255，越小图片越清晰
_RESIZE_DEBOUNCE_MS = 100  # 窗口拖动时的重绘防抖

_SRC_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "assets", "bg.png")

_src_image = None          # 原始 PIL 图（只加载/压暗一次）
_src_tried = False
_darkened = None           # 压暗后的原图


def _load_darkened():
    """加载原图并叠加深色蒙版，全程容错；失败返回 None"""
    global _src_image, _src_tried, _darkened
    if _src_tried:
        return _darkened
    _src_tried = True
    try:
        from PIL import Image
        if not os.path.isfile(_SRC_PATH):
            return None
        img = Image.open(_SRC_PATH).convert("RGBA")
        _src_image = img
        mask = Image.new("RGBA", img.size, _MASK_RGB + (_MASK_ALPHA,))
        _darkened = Image.alpha_composite(img, mask).convert("RGB")
    except Exception:
        _darkened = None
    return _darkened


def _cover_resize(img, w, h):
    """等比缩放并居中裁剪到 w×h（cover 填充，不变形）"""
    if w <= 1 or h <= 1:
        return None
    src_w, src_h = img.size
    scale = max(w / src_w, h / src_h)
    new_w, new_h = max(w, int(src_w * scale + 0.5)), max(h, int(src_h * scale + 0.5))
    try:
        resized = img.resize((new_w, new_h), Image.LANCZOS)
    except Exception:
        resized = img.resize((new_w, new_h))
    left = (new_w - w) // 2
    top = (new_h - h) // 2
    return resized.crop((left, top, left + w, top + h))


def install(parent, bg_color="#f2f8ff"):
    """在 parent 内最底层铺设背景 Canvas，返回该 Canvas（失败返回 None）。

    parent: 背景所在的容器（通常是 BasePage）
    bg_color: 图片不可用时的兜底纯色
    """
    darkened = _load_darkened()
    canvas = tk.Canvas(parent, bg=bg_color, highlightthickness=0, bd=0,
                       relief="flat", borderwidth=0)
    # place 脱离 pack/grid 布局流，铺满父容器且不挤占其它子控件
    canvas.place(x=0, y=0, relwidth=1.0, relheight=1.0)
    # 降到最底层（注意：Canvas 类覆盖了 lower()，必须用底层 Tk 命令）
    canvas.tk.call('lower', canvas._w)

    if darkened is None:
        return canvas  # 纯色兜底，不绑定重绘

    state = {"photo": None, "after_id": None, "last": (0, 0)}

    def _redraw():
        state["after_id"] = None
        try:
            w = canvas.winfo_width()
            h = canvas.winfo_height()
            if w <= 1 or h <= 1:
                return
            if state["last"] == (w, h) and state["photo"] is not None:
                return
            state["last"] = (w, h)
            from PIL import ImageTk
            cropped = _cover_resize(darkened, w, h)
            if cropped is None:
                return
            # 保留引用防止被 GC 回收导致画面消失
            state["photo"] = ImageTk.PhotoImage(cropped)
            canvas.delete("all")
            canvas.create_image(0, 0, anchor="nw", image=state["photo"])
        except Exception:
            pass  # 任何绘制异常都不影响主程序

    def _on_configure(_evt=None):
        if state["after_id"] is not None:
            try:
                canvas.after_cancel(state["after_id"])
            except Exception:
                pass
        state["after_id"] = canvas.after(_RESIZE_DEBOUNCE_MS, _redraw)

    canvas.bind("<Configure>", _on_configure)
    canvas.after(30, _redraw)
    canvas._bg_state = state
    return canvas


# ================= 原生背景绘制（单窗口 Canvas 皮肤） =================
# 背景图缩放为窗口尺寸，各区域 Canvas 用负偏移绘制对应片段，
# 元素绘制在背景之上，实现“背景图 + UI 元素”同一窗口原生渲染。

_win_cache = {"size": None, "photo": None}


def _log(line):
    """背景模块日志（exe 无控制台，写入 _debug.log 便于定位）"""
    try:
        import time
        with open(os.path.join(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__))), "_debug.log"),
                "a", encoding="utf-8") as f:
            f.write("[%s] %s\n" % (time.strftime("%m-%d %H:%M:%S"), line))
    except Exception:
        pass


def scaled_photo(win_w, win_h):
    """返回拉伸到窗口尺寸 w×h 的背景图 PhotoImage（带缓存；失败回退旧图，绝不空白）"""
    if win_w <= 1 or win_h <= 1:
        return _win_cache["photo"]
    if _win_cache["size"] == (win_w, win_h) and _win_cache["photo"] is not None:
        return _win_cache["photo"]
    darkened = _load_darkened()
    if darkened is None:
        _log("[bg] darkened None, keep old=%s" % (_win_cache["photo"] is not None))
        return _win_cache["photo"]
    import time as _t
    t0 = _t.time()
    try:
        from PIL import ImageTk
        cropped = _cover_resize(darkened, win_w, win_h)
        if cropped is None:
            _log("[bg] crop None, keep old=%s" % (_win_cache["photo"] is not None))
            return _win_cache["photo"]
        photo = ImageTk.PhotoImage(cropped)
        _win_cache["size"] = (win_w, win_h)
        _win_cache["photo"] = photo
        _log("[bg] scaled %dx%d ok %.0fms" % (win_w, win_h, (_t.time() - t0) * 1000))
        return photo
    except Exception as e:
        _log("[bg] scaled %dx%d FAIL %r keep old=%s" % (
            win_w, win_h, e, _win_cache["photo"] is not None))
        return _win_cache["photo"]


def invalidate_cache():
    """窗口尺寸变化或背景图更换时调用，强制下次重新缩放"""
    _win_cache["size"] = None
    _win_cache["photo"] = None


def paint(cv, photo, win_x, win_y):
    """在 Canvas 上绘制窗口背景图的对应片段（win_x/win_y 为该 Canvas 相对窗口左上角偏移）。
    调用前应先 cv.delete('all')；本函数只负责背景层。"""
    if photo is None:
        _log("[bg] paint skip None at (%d,%d)" % (win_x, win_y))
        return
    try:
        cv.create_image(-win_x, -win_y, image=photo, anchor="nw")
    except Exception as e:
        _log("[bg] paint FAIL (%d,%d) %r" % (win_x, win_y, e))
