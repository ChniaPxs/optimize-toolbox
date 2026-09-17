# -*- coding: utf-8 -*-
"""ADB封装类（v6.32：全局命令锁防并发断连 + 批量 du 扫描提速 + 更多垃圾类型）"""
import subprocess, time, re, threading
from config import ADB_EXE, ADB_TIMEOUT, ADB_RETRIES

# 全局 ADB 命令锁：监控/清理/网络优化/应用页 各线程串行访问 adb，防止并发导致 USB 会话拥堵断连
ADB_LOCK = threading.Lock()


class ADBHelper:
    def __init__(self):
        self.connected = False
        self.model = ""
        self._adb_path = ADB_EXE
        self._last_err = ""

    def _run(self, args, timeout=10):
        """统一 adb 调用入口：全局锁 + 异常归一（超时/失败返回 None）"""
        with ADB_LOCK:
            try:
                return subprocess.run(args, capture_output=True, text=True,
                                      timeout=timeout, encoding="utf-8", errors="replace")
            except Exception:
                return None

    def start(self):
        if not self._adb_path: return False
        r = self._run([self._adb_path, "start-server"], timeout=10)
        return r is not None and r.returncode == 0

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
            r = self._run([self._adb_path, "get-state"], timeout=ADB_TIMEOUT)
            if r is not None and r.returncode == 0 and (r.stdout or "").strip() == "device":
                self._state = "device"
                self.connected = True
                self._fetch_model()
                return True
            self._state = (r.stdout or "").strip() if r is not None else ""
            self.connected = False
            if i < ADB_RETRIES - 1:
                time.sleep(0.5)
        return False

    def ensure_online(self, tries=2):
        """设备掉线时自动重启 ADB 服务重连（默认 2 次重试）"""
        if self.check():
            return True
        for _ in range(tries):
            self.start()
            time.sleep(0.8)
            if self.check():
                return True
        self._last_err = "设备未连接（%s）" % self.last_state()
        return False

    def last_state(self):
        """最近一次 adb 状态：device / unauthorized / offline / ''"""
        return getattr(self, "_state", "")

    def _fetch_model(self):
        for prop in ("ro.product.model", "ro.product.brand"):
            try:
                r = self._run([self._adb_path, "shell", "getprop", prop], timeout=5)
                if r is not None and r.stdout.strip() and not self.model:
                    self.model = r.stdout.strip()
            except Exception: pass
        if not self.model: self.model = "Android Device"

    def cpu(self):
        """返回 CPU 使用率（%）：用 top 一次性采样解析（多核 800%cpu 格式）"""
        try:
            r = self._run([self._adb_path, "shell", "top", "-b", "-n", "1"], timeout=8)
            if r is None:
                return ("0.0",)
            for line in r.stdout.splitlines():
                m = re.search(r"(\d+)%cpu\s+(\d+)%user\s+(\d+)%nice\s+(\d+)%sys\s+(\d+)%idle", line)
                if m:
                    ncpu = max(1, int(m.group(1)) / 100.0)
                    used = int(m.group(2)) + int(m.group(3)) + int(m.group(4))
                    return ("%.1f" % min(99.9, used / ncpu),)
            return ("0.0",)
        except Exception:
            return ("0.0",)

    def mem(self):
        try:
            r = self._run([self._adb_path, "shell", "cat", "/proc/meminfo"], timeout=5)
            t = a = 0
            if r is None:
                return 1, 0
            for line in r.stdout.splitlines():
                if "MemTotal" in line: t = int(line.split()[1]) * 1024
                elif "MemAvailable" in line: a = int(line.split()[1]) * 1024
            return t or 1, a or 0
        except Exception: return 1, 0

    def storage(self):
        """返回 (总量文本, 已用文本, 使用率%)：df /data 按列解析"""
        try:
            r = self._run([self._adb_path, "shell", "df", "/data"], timeout=5)
            if r is None:
                return "0B", "0B", 0
            for line in r.stdout.splitlines():
                p = line.split()
                if len(p) >= 5 and p[4].endswith("%"):
                    try:
                        total_b = int(p[1]) * 1024
                        used_b = int(p[2]) * 1024
                        return self._fmt_vol(total_b), self._fmt_vol(used_b), int(p[4][:-1])
                    except Exception:
                        continue
        except Exception:
            pass
        return "0B", "0B", 0

    @staticmethod
    def _fmt_vol(b):
        try:
            b = float(b)
            for u in ("B", "KB", "MB", "GB", "TB"):
                if b < 1024 or u == "TB":
                    s = ("%.1f" % b)
                    if s.endswith(".0"):
                        s = s[:-2]
                    return s + u
                b /= 1024.0
        except Exception:
            pass
        return "0B"

    def battery(self):
        try:
            r = self._run([self._adb_path, "shell", "dumpsys", "battery"], timeout=5)
            lv = tp = "?"
            if r is None:
                return lv, tp
            for line in r.stdout.splitlines():
                if "level" in line: lv = line.split(":")[-1].strip()
                elif "status" in line: tp = line.split(":")[-1].strip()
            return lv, tp
        except Exception: return "?", "?"

    def pkgs(self):
        """第三方应用列表：每项 {pkg, label}（label 为中文/系统应用名，解析失败回退包名）"""
        try:
            r = self._run([self._adb_path, "shell", "pm", "list", "packages", "-3"], timeout=10)
            if r is None:
                return []
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
            r = self._run([self._adb_path, "shell", "dumpsys", "package"], timeout=30)
            if r is None:
                return {}
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
            r = self._run([self._adb_path, "uninstall", pkg], timeout=20)
            if r is None:
                return False, "卸载失败：adb 无响应"
            out = (r.stdout or r.stderr or "").strip()
            if r.returncode == 0 and ("success" in out.lower() or not out):
                return True, "已卸载 " + pkg
            return False, ("卸载失败：" + out[:80]) if out else "卸载失败"
        except Exception as e:
            return False, "卸载出错：" + str(e)

    def cls_log(self): return self._shell("logcat -c")
    def cls_thumb(self): return self._shell("rm -rf /sdcard/DCIM/.thumbnails/*")
    def kill_all(self): return self._shell("am kill-all")

    def shell_out(self, cmd, timeout=15):
        """执行 adb shell 并返回文本输出（去掉 \\r 与末尾空白）"""
        if not self._adb_path:
            return ""
        r = self._run([self._adb_path, "shell", cmd], timeout=timeout)
        if r is None:
            return ""
        return (r.stdout or "").replace("\r", "").strip()

    def scan_junk(self, timeout=60):
        """扫描手机垃圾（免 root 可访问的安全目录）：
        基础缓存 + 应用缓存 + 下载安装包，批量 du 一次统计（提速且减少 adb 调用防断连）
        返回 [(路径, 字节, 描述)]"""
        if not self.ensure_online(tries=2):
            return []
        self._last_err = ""
        items = []

        def _parse_du(out, valid_paths=None):
            """解析 toybox du 输出（每行 '<size>\\t<path>'）"""
            res = []
            if not out:
                return res
            for line in out.splitlines():
                parts = line.split("\t")
                if len(parts) < 2:
                    continue
                try:
                    sz = int(parts[0].strip()) * 1024
                except Exception:
                    continue
                path = parts[1].strip().strip("'")
                if valid_paths is None or path in valid_paths:
                    if sz > 0:
                        res.append((path, sz))
            return res

        # 1) 基础缓存目录：一次 du 批量统计
        base = [
            ("/data/local/tmp", "ADB 临时文件"),
            ("/sdcard/DCIM/.thumbnails", "相册缩略图缓存"),
            ("/sdcard/.thumbnails", "通用缩略图缓存"),
            ("/sdcard/cache", "系统缓存目录"),
        ]
        out = self.shell_out("du -sk " + " ".join("'%s'" % p for p, _ in base) +
                             " 2>/dev/null", timeout=timeout)
        base_map = dict(base)
        for path, sz in _parse_du(out):
            if path in base_map:
                items.append((path, sz, base_map[path]))

        # 2) 应用缓存目录：ls 一次 + du 一次
        out = self.shell_out("ls -d /sdcard/Android/data/*/cache 2>/dev/null", timeout=timeout)
        dirs = [l.strip() for l in out.splitlines()
                if l.strip() and " " not in l.strip()]
        if dirs:
            out = self.shell_out("du -sk " + " ".join("'%s'" % d for d in dirs) +
                                 " 2>/dev/null", timeout=timeout)
            dir_set = set(dirs)
            for path, sz in _parse_du(out, dir_set):
                app = path.split("/")[-2] if "/" in path else path
                items.append((path, sz, "应用缓存·" + app))

        # 3) 下载安装包：find 一次 + du 一次（只统计 >50KB 的 apk）
        out = self.shell_out(
            "find /sdcard/Download /sdcard/Download2 /sdcard/0 -maxdepth 3 "
            "-name '*.apk' -size +50k 2>/dev/null", timeout=timeout)
        apks = [l.strip() for l in out.splitlines()
                if l.strip() and " " not in l.strip()]
        if apks:
            out = self.shell_out("du -sk " + " ".join("'%s'" % a for a in apks) +
                                 " 2>/dev/null", timeout=timeout)
            apk_set = set(apks)
            for path, sz in _parse_du(out, apk_set):
                name = path.rsplit("/", 1)[-1]
                items.append((path, sz, "下载安装包·" + name))
        return items

    def clean_junk(self, paths, timeout=60):
        """删除手机垃圾目录：返回 (成功数, 失败列表)；逐项容错，失败不中断"""
        if not paths:
            return 0, []
        if not self.ensure_online(tries=2):
            return 0, [self._last_err or "设备未连接"]
        ok, fail = 0, []
        for p in paths:
            try:
                r = self._run([self._adb_path, "shell", "rm -rf '%s'" % p], timeout=timeout)
                if r is not None and r.returncode == 0:
                    ok += 1
                else:
                    fail.append("删除失败：" + p)
            except Exception as e:
                fail.append(str(e)[:100])
        return ok, fail

    def _shell(self, cmd):
        if not self._adb_path: return False
        r = self._run([self._adb_path, "shell", cmd], timeout=10)
        return r is not None and r.returncode == 0
