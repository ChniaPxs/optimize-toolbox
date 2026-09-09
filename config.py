# -*- coding: utf-8 -*-
"""优化工具箱 v6.0 - 配置模块"""
import os, sys, json
from pathlib import Path
from datetime import datetime

os.environ.setdefault("PYTHONIOENCODING", "utf-8")

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys._MEIPASS)
else:
    BASE_DIR = Path(__file__).resolve().parent

TOOLS_DIR = BASE_DIR / "tools"
ASSETS_DIR = BASE_DIR / "assets"
DB_PATH = BASE_DIR / "data" / "optimize.db"
LOG_DIR = BASE_DIR / "logs"
USER_CFG_DIR = Path.home() / ".optimize_toolbox"
USER_CFG_FILE = USER_CFG_DIR / "config.json"
for d in [BASE_DIR / "data", LOG_DIR, USER_CFG_DIR]:
    d.mkdir(parents=True, exist_ok=True)

PLATFORM_TOOLS = TOOLS_DIR / "platform-tools"
ADB_EXE = str(PLATFORM_TOOLS / "adb.exe") if PLATFORM_TOOLS.exists() else None

CLR = {
    "bg_deep": "#010102", "bg_main": "#010102", "bg_card": "#010102",
    "bg_hover": "#010102", "border": "#bfd9f5", "border_light": "#9cc4ee",
    "accent": "#2f6fed", "accent_lt": "#5b8ff5", "cyan": "#0ea5e9",
    "green": "#0fb981", "orange": "#f59e0b", "red": "#ef4444",
    "pink": "#ec4899", "purple": "#8b5cf6",
    "text": "#1e2a44", "text_dim": "#3d5470", "text_muted": "#6b82a0",
    "input_bg": "#010102",
}

FONT_TITLE = ("Microsoft YaHei UI", 16, "bold")
FONT_HEADING = ("Microsoft YaHei UI", 13, "bold")
FONT_SUB = FONT_SUBTITLE = ("Microsoft YaHei UI", 10)
FONT_BODY = ("Microsoft YaHei UI", 9)
FONT_LOG = ("Consolas", 9)
FONT_NUM = ("Microsoft YaHei UI", 22, "bold")

WIN_W, WIN_H = 1280, 800
MIN_W, MIN_H = 960, 640
HDR_H, SIDES_W = 56, 200
STAT_H, LOG_H = 32, 160
FADE_MS = 250
ADB_TIMEOUT = 10
ADB_RETRIES = 3

THRESH = {"cpu_warn":70.0, "cpu_crit":90.0, "mem_warn":75.0, "mem_crit":90.0, "disk_warn":80.0, "disk_crit":95.0}

CLEAN_CATS = {
    "system_temp":  {"name": "系统临时文件", "safe": True},
    "browser_cache": {"name": "浏览器缓存", "safe": True},
    "app_cache":    {"name": "应用缓存", "safe": True},
    "download_jnk": {"name": "下载垃圾", "safe": True},
    "media_cache":  {"name": "媒体缓存", "safe": True},
    "duplicate":    {"name": "重复文件", "safe": False},
    "large_files":  {"name": "大文件分析", "safe": False},
}

class UserSettings:
    def __init__(self):
        self.s = self._load()
    def _load(self):
        if USER_CFG_FILE.exists():
            try:
                with open(USER_CFG_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception: pass
        return {"theme":"dark_ocean","auto_start":False,"min_tray":True,"sound":True,"last_clean":None,"scheduled":False,"dns":"auto","net_mode":"balanced"}
    def _save(self):
        try:
            with open(USER_CFG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.s, f, ensure_ascii=False, indent=2)
        except Exception: pass
    def get(self, k, d=None): return self.s.get(k, d)
    def set(self, k, v): self.s[k] = v; self._save()
    def toggle(self, k): self.set(k, not self.get(k, False)); return self.get(k)

settings = UserSettings()

class Logger:
    def __init__(self):
        self.path = LOG_DIR / "app.log"
        self.buf = []
    def _ts(self): return datetime.now().strftime("%H:%M:%S")
    def info(self, m): l="[%s] INFO  %s"%(self._ts(),m); self.buf.append(l); self._w(l)
    def ok(self, m):   l="[%s] OK    %s"%(self._ts(),m); self.buf.append(l); self._w(l)
    def warn(self, m): l="[%s] WARN  %s"%(self._ts(),m); self.buf.append(l); self._w(l)
    def error(self, m):l="[%s] ERROR %s"%(self._ts(),m); self.buf.append(l); self._w(l)
    def _w(self, l):
        try:
            with open(self.path, "a", encoding="utf-8") as f: f.write(l+"\n")
        except Exception: pass
    def clear(self):
        self.buf.clear()
        try: self.path.unlink(missing_ok=True)
        except Exception: pass

log = Logger()