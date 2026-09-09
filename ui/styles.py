
# -*- coding: utf-8 -*-
"""UI样式配置 - 暗色深海主题"""
import tkinter as tk
from tkinter import ttk
from config import CLR, FONT_TITLE, FONT_SUBTITLE, FONT_BODY, FONT_LOG, FONT_NUM

def apply_styles(root):
    style = ttk.Style(root)
    style.theme_use('clam')
    style.configure('TFrame', background=CLR['bg_main'])
    style.configure('TLabel', background=CLR['bg_main'], foreground=CLR['text'], font=FONT_BODY)
    style.configure('TButton', background=CLR['accent'], foreground='white',
                    font=FONT_SUBTITLE, padding=(14, 6))
    style.map('TButton', background=[('active', CLR['accent_lt']), ('pressed', '#4f46e5')])
    style.configure('TEntry', fieldbackground=CLR['input_bg'], foreground=CLR['text'],
                    font=FONT_BODY, insertcolor=CLR['cyan'])
    style.configure('TScale', background=CLR['bg_card'], troughcolor=CLR['bg_hover'],
                    highlightthickness=0)
    style.configure('Horizontal.TScrollbar', background=CLR['bg_card'],
                    troughcolor=CLR['bg_hover'], arrowcolor=CLR['text_muted'])
    style.configure('Title.TLabel', background=CLR['bg_main'], foreground=CLR['cyan'], font=FONT_TITLE)
    style.configure('Heading.TLabel', background=CLR['bg_main'], foreground=CLR['text'], font=FONT_SUBTITLE)
    style.configure('Body.TLabel', background=CLR['bg_main'], foreground=CLR['text_dim'], font=FONT_BODY)
    style.configure('Num.TLabel', background=CLR['bg_main'], foreground=CLR['cyan'], font=FONT_NUM)
    style.configure('Green.TLabel', foreground=CLR['green'])
    style.configure('Orange.TLabel', foreground=CLR['orange'])
    style.configure('Red.TLabel', foreground=CLR['red'])
    style.configure('Card.TFrame', background=CLR['bg_card'], relief='solid', borderwidth=1)
    style.configure('Nav.TButton', background=CLR['bg_main'], foreground=CLR['text_dim'],
                    font=FONT_SUBTITLE, padding=(12, 8))
    style.map('Nav.TButton', background=[('active', CLR['bg_hover']), ('pressed', CLR['border'])],
              foreground=[('active', CLR['text']), ('pressed', CLR['cyan'])])
    style.configure('Act.TButton', background=CLR['accent'], foreground='white',
                    font=FONT_SUBTITLE, padding=(14, 6))
    style.map('Act.TButton', background=[('active', CLR['accent_lt']), ('pressed', '#4f46e5')])
    style.configure('Dng.TButton', background=CLR['red'], foreground='white',
                    font=FONT_SUBTITLE, padding=(14, 6))
    style.configure('Suc.TButton', background=CLR['green'], foreground='white',
                    font=FONT_SUBTITLE, padding=(14, 6))
    return style
