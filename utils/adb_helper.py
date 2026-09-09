# -*- coding: utf-8 -*-
"""ADB封装类"""
import subprocess, time
from config import ADB_EXE, ADB_TIMEOUT, ADB_RETRIES

class ADBHelper:
    def __init__(self):
        self.connected = False
        self.model = ""
        self._adb_path = ADB_EXE

    def start(self):
        if not self._adb_path: return False
        try:
            r = subprocess.run([self._adb_path, "start-server"], capture_output=True, text=True, timeout=10, encoding="utf-8", errors="replace")
            return r.returncode == 0
        except Exception: return False

    def connect(self):
        """启动 ADB 服务并检测设备（顶栏/首页/终端入口统一调用）"""
        if not self._adb_path: return False
        self.start()
        return self.check()

    def check(self):
        if not self._adb_path:
            self.connected = False
            self._state = ""
            return False
        for i in range(ADB_RETRIES):
            try:
                r = subprocess.run([self._adb_path, "get-state"], capture_output=True, text=True, timeout=ADB_TIMEOUT, encoding="utf-8", errors="replace")
                self._state = (r.stdout or "").strip()
                self.connected = (r.returncode == 0 and self._state == "device")
                if self.connected:
                    self._fetch_model()
                return self.connected
            except Exception:
                if i == ADB_RETRIES - 1:
                    self.connected = False
                    self._state = ""
                time.sleep(0.5)
        return False

    def ensure_online(self, tries=2):
        """设备掉线时自动重启 ADB 服务重连（应用页/监控页刷新入口统一调用）"""
        if self.check():
            return True
        for _ in range(tries):
            self.start()
            time.sleep(0.8)
            if self.check():
                return True
        return False

    def last_state(self):
        """最近一次 adb 状态：device / unauthorized / offline / ''"""
        return getattr(self, "_state", "")

    def _fetch_model(self):
        for prop in ("ro.product.model", "ro.product.brand"):
            try:
                r = subprocess.run([self._adb_path, "shell", "getprop", prop], capture_output=True, text=True, timeout=5, encoding="utf-8", errors="replace")
                if r.stdout.strip() and not self.model: self.model = r.stdout.strip()
            except Exception: pass
        if not self.model: self.model = "Android Device"

    def cpu(self):
        try:
            r = subprocess.run([self._adb_path, "shell", "cat", "/proc/loadavg"], capture_output=True, text=True, timeout=5, encoding="utf-8", errors="replace")
            p = r.stdout.strip().split()
            if len(p) >= 3: return p[0], p[1], p[2]
        except Exception: pass
        return "0", "0", "0"

    def mem(self):
        try:
            r = subprocess.run([self._adb_path, "shell", "cat", "/proc/meminfo"], capture_output=True, text=True, timeout=5, encoding="utf-8", errors="replace")
            t = a = 0
            for line in r.stdout.splitlines():
                if "MemTotal" in line: t = int(line.split()[1]) * 1024
                elif "MemAvailable" in line: a = int(line.split()[1]) * 1024
            return t or 1, a or 0
        except Exception: return 1, 0

    def storage(self):
        try:
            import re
            r = subprocess.run([self._adb_path, "shell", "df", "-h", "/data"], capture_output=True, text=True, timeout=5, encoding="utf-8", errors="replace")
            m = re.search(r"(\\d+)%\\s+(\\S+)\\s+(\\S+)", r.stdout)
            if m: return m.group(2), m.group(3), int(m.group(1))
        except Exception: pass
        return "0B", "0B", 0

    def battery(self):
        try:
            r = subprocess.run([self._adb_path, "shell", "dumpsys", "battery"], capture_output=True, text=True, timeout=5, encoding="utf-8", errors="replace")
            lv = tp = "?"
            for line in r.stdout.splitlines():
                if "level" in line: lv = line.split(":")[-1].strip()
                elif "status" in line: tp = line.split(":")[-1].strip()
            return lv, tp
        except Exception: return "?", "?"

    def pkgs(self):
        """第三方应用列表：每项 {pkg, label}（label 为中文/系统应用名，解析失败回退包名）"""
        try:
            r = subprocess.run([self._adb_path, "shell", "pm", "list", "packages", "-3"],
                               capture_output=True, text=True, timeout=10,
                               encoding="utf-8", errors="replace")
            pkgs = [l.strip().replace("package:", "").strip()
                    for l in r.stdout.splitlines() if l.strip()]
            labels = self._fetch_labels()
            return [{"pkg": p, "label": (labels.get(p) or p)} for p in pkgs]
        except Exception:
            return []

    def _fetch_labels(self):
        """dumpsys package 全量解析应用名（application-label），缓存 60 秒"""
        now = time.time()
        if getattr(self, "_labels_ts", 0) and now - self._labels_ts < 60:
            return self._labels
        labels = {}
        try:
            r = subprocess.run([self._adb_path, "shell", "dumpsys", "package"],
                               capture_output=True, text=True, timeout=30,
                               encoding="utf-8", errors="replace")
            cur = None
            for line in r.stdout.splitlines():
                s = line.strip()
                if s.startswith("Package ["):
                    cur = s[9:-1].strip()
                elif cur and s.startswith("application-label:"):
                    lab = s.split(":", 1)[1].strip()
                    if lab and cur not in labels:
                        labels[cur] = lab
                    cur = None
        except Exception:
            pass
        self._labels = labels
        self._labels_ts = now
        return labels

    def uninstall(self, pkg):
        """卸载手机第三方应用；返回 (成功?, 提示消息)"""
        if not self._adb_path:
            return False, "无 ADB 环境"
        try:
            r = subprocess.run([self._adb_path, "uninstall", pkg],
                               capture_output=True, text=True, timeout=20,
                               encoding="utf-8", errors="replace")
            out = (r.stdout or r.stderr or "").strip()
            if r.returncode == 0 and ("success" in out.lower() or not out):
                return True, "已卸载 " + pkg
            return False, ("卸载失败：" + out[:80]) if out else "卸载失败"
        except subprocess.TimeoutExpired:
            return False, "卸载超时"
        except Exception as e:
            return False, "卸载出错：" + str(e)

    def cls_log(self): return self._shell("logcat -c")
    def cls_thumb(self): return self._shell("rm -rf /sdcard/DCIM/.thumbnails/*")
    def kill_all(self): return self._shell("am kill-all")

    def shell_out(self, cmd, timeout=15):
        """执行 adb shell 并返回文本输出（去掉 \\r 与末尾空白）"""
        if not self._adb_path:
            return ""
        try:
            r = subprocess.run([self._adb_path, "shell", cmd],
                               capture_output=True, text=True, timeout=timeout,
                               encoding="utf-8", errors="replace")
            return (r.stdout or "").replace("\r", "").strip()
        except Exception:
            return ""

    def scan_junk(self, timeout=60):
        """扫描手机垃圾（无需 root 可访问的安全目录）：返回 [(路径, 字节, 描述)]"""
        if not self.ensure_online(tries=1):
            return []
        items = []

        def _du(path):
            out = self.shell_out("du -sk '%s' 2>/dev/null" % path, timeout=timeout)
            if not out:
                return 0
            try:
                first = out.splitlines()[-1].split()
                return int(first[0]) * 1024
            except Exception:
                return 0

        for path, desc in [
            ("/data/local/tmp", "ADB 临时文件"),
            ("/sdcard/DCIM/.thumbnails", "相册缩略图缓存"),
        ]:
            sz = _du(path)
            if sz > 0:
                items.append((path, sz, desc))
        # 各应用缓存目录 /sdcard/Android/data/*/cache（可安全清理）
        out = self.shell_out("ls -d /sdcard/Android/data/*/cache 2>/dev/null", timeout=timeout)
        if out:
            seen = set()
            for line in out.splitlines():
                p = line.strip()
                if not p or p in seen or " " in p:
                    continue
                seen.add(p)
                sz = _du(p)
                if sz > 0:
                    app = p.split("/")[-2] if "/" in p else p
                    items.append((p, sz, "应用缓存·" + app))
        return items

    def clean_junk(self, paths, timeout=60):
        """删除手机垃圾目录：返回 (成功数, 失败列表)"""
        if not paths:
            return 0, []
        if not self.ensure_online(tries=1):
            return 0, ["设备未连接"]
        ok, fail = 0, []
        for p in paths:
            try:
                self.shell_out("rm -rf '%s'" % p, timeout=timeout)
                ok += 1
            except Exception as e:
                fail.append(str(e))
        return ok, fail

    def _shell(self, cmd):
        if not self._adb_path: return False
        try:
            r = subprocess.run([self._adb_path, "shell", cmd], capture_output=True, text=True, timeout=10, encoding="utf-8", errors="replace")
            return r.returncode == 0
        except Exception: return False
