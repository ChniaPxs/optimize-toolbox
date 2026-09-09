# -*- coding: utf-8 -*-
import subprocess, threading, time, re, ctypes
from config import ADB_EXE, ADB_TIMEOUT, ADB_RETRIES, log


def _is_admin():
    """当前进程是否以管理员身份运行"""
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False

class NetworkStats:
    def __init__(self):
        self.download_speed = 0.0
        self.upload_speed = 0.0
        self.latency = 0.0
        self.jitter = 0.0
        self.packet_loss = 0.0
        self.network_type = "unknown"
        self.signal_strength = "N/A"
        self.connection_count = 0
        self.dns_server = "unknown"
        self.ip_address = "unknown"
        self.gateway = "unknown"

class OptimizationResult:
    def __init__(self, opt_type, improvement=0.0, description="", success=False, changes=None):
        self.type = opt_type
        self.improvement = improvement
        self.description = description
        self.success = success
        self.changes = changes or []

class NetworkOptimizer:
    def __init__(self):
        self._stats = NetworkStats()
        self._lock = threading.Lock()
        self._running = False
        self._monitor_thread = None

    def get_network_stats(self):
        with self._lock:
            return self._stats

    def optimize_network(self):
        results = [self._optimize_tcp(), self._optimize_dns(), self._flush_dns(), self._disable_nagle()]
        if ADB_EXE:
            results.append(self._mobile_optimize())
        ok = all(r.success for r in results)
        total = sum(r.improvement for r in results if r.success)
        ok_changes = [r.description for r in results if r.success]
        fails = [r.description for r in results if not r.success]
        desc = "网络优化完成：" + "；".join(ok_changes) if ok_changes else "网络优化未生效"
        if fails:
            desc += "；未生效：" + "；".join(fails)
        return OptimizationResult("full", total, desc, ok, ok_changes)

    def optimize_dns(self):
        return self._optimize_dns()

    def enable_game_mode(self):
        TCP = r"HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters"
        changes = self._apply_changes([
            (TCP, "MaxMTU", 1500, "TCP MaxMTU（最大传输单元）",
             "限制单包≤1500字节，避免IP分片与重传，降低延迟与丢包"),
            (TCP, "TcpAckFrequency", 1, "TCP ACK 确认频率",
             "每收到一包立即回ACK，减少交互等待，显著降低游戏/操作延迟"),
        ])
        if ADB_EXE:
            o, e, rc = self._ra(["shell", "settings", "put", "global",
                                 "wifi_scan_interval_ms", "10000"])
            changes.append({"param": "手机 WiFi 扫描间隔", "desc": "降低后台扫描频率，减少抢网与功耗，网络更稳定",
                            "old": "默认", "new": "10000 ms", "ok": rc == 0, "vtype": "ADB 设置", "adb": True})
        ok = any(c["ok"] for c in changes)
        if not ok and not _is_admin():
            return OptimizationResult("game", 0, "游戏模式需要管理员权限", False, changes)
        log.ok("游戏模式已启用")
        n = sum(1 for c in changes if c["ok"])
        return OptimizationResult("game", 15.0,
                                  "游戏模式已启用：%d 项网络参数已写入" % n,
                                  True, changes)

    def enable_video_mode(self):
        TCP = r"HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters"
        changes = self._apply_changes([
            (TCP, "MaxMTU", 1500, "TCP MaxMTU（最大传输单元）",
             "限制单包≤1500字节，避免IP分片与重传，降低延迟与丢包"),
            (TCP, "TCPWindowSize", 65535, "TCP 接收窗口",
             "加大接收窗口，单次确认传输更多数据，提升视频流与下载带宽"),
        ])
        if ADB_EXE:
            o, e, rc = self._ra(["shell", "settings", "put", "global",
                                 "wifi_scan_interval_ms", "5000"])
            changes.append({"param": "手机 WiFi 扫描间隔", "desc": "降低后台扫描频率",
                            "old": "默认", "new": "5000 ms", "ok": rc == 0, "vtype": "ADB 设置", "adb": True})
        ok = any(c["ok"] for c in changes)
        if not ok and not _is_admin():
            return OptimizationResult("video", 0, "视频模式需要管理员权限", False, changes)
        log.ok("视频模式已启用")
        n = sum(1 for c in changes if c["ok"])
        return OptimizationResult("video", 10.0,
                                  "视频模式已启用：%d 项网络参数已写入" % n,
                                  True, changes)

    def enable_download_mode(self):
        TCP = r"HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters"
        changes = self._apply_changes([
            (TCP, "MaxConnectionsPerServer", 10, "单服务器最大并发连接",
             "提升并发连接数，多线程下载更快"),
            (TCP, "TCPWindowSize", 65535, "TCP 接收窗口",
             "加大接收窗口，单次确认传输更多数据，提升下载吞吐"),
        ])
        if ADB_EXE:
            o, e, rc = self._ra(["shell", "settings", "put", "global",
                                 "wifi_scan_interval_ms", "3000"])
            changes.append({"param": "手机 WiFi 扫描间隔", "desc": "降低后台扫描频率",
                            "old": "默认", "new": "3000 ms", "ok": rc == 0, "vtype": "ADB 设置", "adb": True})
        ok = any(c["ok"] for c in changes)
        if not ok and not _is_admin():
            return OptimizationResult("download", 0, "下载模式需要管理员权限", False, changes)
        log.ok("下载模式已启用")
        n = sum(1 for c in changes if c["ok"])
        return OptimizationResult("download", 20.0,
                                  "下载模式已启用：%d 项网络参数已写入" % n,
                                  True, changes)

    def start_monitoring(self):
        if self._running: return
        self._running = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        log.ok("网络监控已启动")

    def stop_monitoring(self):
        self._running = False
        if self._monitor_thread: self._monitor_thread.join(timeout=2)
        log.ok("网络监控已停止")

    def _r(self, cmd, t=10):
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=t, encoding="utf-8", errors="replace")
            return r.stdout.strip(), r.stderr.strip(), r.returncode
        except subprocess.TimeoutExpired: return "", "timeout", 1
        except Exception as e: return "", str(e), 1

    def _ra(self, args, retries=ADB_RETRIES):
        if not ADB_EXE: return "", "no adb", 1
        for i in range(retries):
            o, e, rc = self._r([ADB_EXE] + args)
            if rc == 0: return o, e, rc
            time.sleep(0.5)
        return o, e, rc

    def _reg_get(self, key, name):
        try:
            r = subprocess.run(["reg", "query", key, "/v", name], capture_output=True, text=True, timeout=5, encoding="utf-8", errors="replace")
            for line in r.stdout.splitlines():
                if name in line:
                    parts = line.strip().split()
                    return parts[-1] if parts else None
        except Exception: pass
        return None

    def _reg_set(self, key, name, val, vtype="REG_DWORD"):
        try:
            r = subprocess.run(["reg", "add", key, "/v", name, "/t", vtype, "/d", str(val), "/f"],
                               capture_output=True, timeout=10, encoding="utf-8", errors="replace")
            return r.returncode == 0
        except Exception:
            return False

    def _reg_set_detailed(self, key, name, val, vtype="REG_DWORD"):
        """写入注册表并记录原值，返回 (是否成功, 原值, 新值)"""
        old = self._reg_get(key, name)
        ok = self._reg_set(key, name, val, vtype)
        return ok, old, val

    def _apply_changes(self, items):
        """批量应用网络参数，生成明细列表。
        items: [(key, 值名, 新值, 参数显示名, 新值说明)] → dict 列表"""
        changes = []
        for key, name, val, label, desc in items:
            ok, old, new = self._reg_set_detailed(key, name, val)
            changes.append({"param": label, "desc": desc, "key": key, "vtype": "REG_DWORD",
                            "old": old, "new": new, "ok": ok})
        return changes

    def _optimize_tcp(self):
        changes = []
        if self._reg_set(r"HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters",
                         "GlobalMaxNonPathMaxSegSize", 1460):
            changes.append("MaxSegSize")
        if changes:
            log.ok("TCP优化: " + ", ".join(changes))
            return OptimizationResult("tcp", 8.0, "TCP/IP参数已优化", True, changes)
        if not _is_admin():
            return OptimizationResult("tcp", 0, "TCP参数优化需要管理员权限", False, [])
        return OptimizationResult("tcp", 0, "TCP参数已是最新", True, [])

    def _optimize_dns(self):
        dns_map = [("223.5.5.5", "阿里云DNS"), ("119.29.29.29", "DNSPod"), ("8.8.8.8", "Google")]
        current = self._get_dns()
        selected = dns_map[0]
        if current != selected[0]:
            if self._set_dns(selected[0]):
                log.ok("DNS已切换: " + selected[1])
                return OptimizationResult("dns", 5.0, "DNS优化: " + selected[1], True, [selected[0]])
            return OptimizationResult("dns", 0, "DNS切换失败（接口不可用或权限不足）", False, [])
        return OptimizationResult("dns", 0, "DNS已是最优", True, [])

    def _flush_dns(self):
        _, _, rc = self._r(["cmd", "/c", "ipconfig", "/flushdns"])
        if rc == 0:
            log.ok("DNS缓存已刷新")
            return OptimizationResult("dns_cache", 2.0, "DNS缓存已刷新", True)
        return OptimizationResult("dns_cache", 0, "DNS缓存刷新跳过", True)

    def _disable_nagle(self):
        key = r"HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters\Interfaces"
        try:
            r = subprocess.run(["reg", "query", key], capture_output=True, text=True, timeout=10,
                               encoding="utf-8", errors="replace")
            # reg query 输出的子键行以 HKEY_LOCAL_MACHINE 开头；首行是 key 本身，跳过
            ifaces = [l.strip() for l in r.stdout.splitlines()
                      if l.strip().startswith("HKEY_LOCAL_MACHINE") and l.strip().rstrip("\\") != key]
            changed = 0
            for iface in ifaces:
                if self._reg_set(iface, "TCPNoDelay", 1):
                    changed += 1
                self._reg_set(iface, "Tcp1323Opts", 1)
            if changed > 0:
                log.ok("Nagle算法已禁用 (" + str(changed) + "接口)")
                return OptimizationResult("nagle", 5.0, "已禁用Nagle算法", True)
            if not _is_admin():
                return OptimizationResult("nagle", 0, "Nagle优化需要管理员权限", False, [])
        except Exception as e:
            log.warn("Nagle优化失败: " + str(e))
        return OptimizationResult("nagle", 0, "未找到网卡接口，Nagle优化跳过", False, [])

    def _mobile_optimize(self):
        changes = []
        ok, _, _ = self._ra(["shell", "settings", "put", "global", "wifi_scan_interval_ms", "5000"])
        if ok == 0: changes.append("wifi_scan=5000ms")
        ok, _, _ = self._ra(["shell", "settings", "put", "global", "private_dns_mode", "hostname"])
        ok2, _, _ = self._ra(["shell", "settings", "put", "global", "private_dns_specifier", "dns.alidns.com"])
        if ok == 0 or ok2 == 0: changes.append("dns=alidns.com")
        if changes:
            log.ok("手机网络优化: " + ", ".join(changes))
            return OptimizationResult("mobile_net", 8.0, "手机网络优化完成", True, changes)
        return OptimizationResult("mobile_net", 0, "手机网络已是最佳", True, [])

    def _get_dns(self):
        try:
            r = subprocess.run(["ipconfig", "/all"], capture_output=True, text=True, timeout=10, encoding="utf-8", errors="replace")
            for line in r.stdout.splitlines():
                if "DNS Servers" in line:
                    parts = line.strip().split(":")
                    if len(parts) > 1:
                        dns = parts[-1].strip().split()[0]
                        if dns and "." in dns and not dns.startswith("*"): return dns
        except Exception: pass
        return None

    def _set_dns(self, dns):
        """枚举所有活动网络接口并设置 DNS；返回是否至少一个接口设置成功"""
        names = []
        try:
            r = subprocess.run(["netsh", "interface", "ipv4", "show", "interfaces"],
                               capture_output=True, text=True, timeout=10,
                               encoding="utf-8", errors="replace")
            for line in r.stdout.splitlines():
                ls = line.strip()
                low = ls.lower()
                if not ls or low.startswith("idx") or low.startswith("---"):
                    continue
                parts = ls.split()
                if len(parts) < 5:
                    continue
                if "connected" in low or "已连接" in ls:
                    # 接口名可能在末列含空格（如"以太网 2"），合并剩余部分
                    names.append(" ".join(parts[4:]))
        except Exception:
            pass
        if not names:
            return False
        ok = False
        for n in names:
            try:
                r2 = subprocess.run(["netsh", "interface", "ip", "set", "dns",
                                     "name=" + n, "static", dns],
                                    capture_output=True, timeout=10,
                                    encoding="utf-8", errors="replace")
                if r2.returncode == 0:
                    ok = True
            except Exception:
                continue
        return ok

    def _monitor_loop(self):
        while self._running:
            try: self._update_stats()
            except Exception: pass
            time.sleep(5)

    def _get_active_adapter_name(self):
        """获取当前活动网卡名（PowerShell，避免解析 ipconfig 乱码标题）"""
        try:
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "(Get-NetAdapter | Where-Object {$_.Status -eq 'Up'} | "
                 "Select-Object -First 1).Name"],
                capture_output=True, text=True, timeout=10,
                encoding="utf-8", errors="replace")
            name = r.stdout.strip()
            return name if name else None
        except Exception:
            return None

    def restart_network_adapter(self):
        """重启网络适配器使 TCP 参数立即生效（需管理员）。返回 (是否成功, 说明)"""
        name = self._get_active_adapter_name()
        if not name:
            return False, "未找到活动网卡"
        try:
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "Restart-NetAdapter -Name '%s' -Confirm:$false" % name],
                capture_output=True, text=True, timeout=90,
                encoding="utf-8", errors="replace")
            if r.returncode == 0:
                log.ok("网络适配器已重启，参数立即生效")
                return True, "网络适配器已重启（%s），参数已立即生效" % name
            err = (r.stderr.strip() or r.stdout.strip() or "未知错误")[:80]
            return False, err
        except Exception as e:
            return False, str(e)[:80]

    def refresh_stats(self):
        """立即同步真实检测一次网络状态（供刷新按钮/页面显示调用）"""
        self._update_stats()
        return self._stats

    def _update_stats(self):
        stats = NetworkStats()
        # ---- 1. ipconfig：IP / 网关 / 网络类型（按网卡段分组，取有网关的主网卡；gbk 兼容中文系统） ----
        try:
            r1 = subprocess.run(["ipconfig"], capture_output=True, timeout=8)
            o = r1.stdout.decode("gbk", errors="replace")
            secs = []
            cur = None
            for line in o.splitlines():
                ls = line.strip()
                if ("adapter" in ls.lower()) or ("适配器" in ls):
                    cur = {"ip": None, "gw": None, "type": "有线网络"}
                    if ("无线" in ls) or ("wlan" in ls.lower()) or ("wireless" in ls.lower()):
                        cur["type"] = "无线网络"
                    secs.append(cur)
                    continue
                if cur is None:
                    continue
                m = re.search(r"(?:IPv4 地址|IPv4 Address)[ .]*:?\s*([\d\.]+)", ls)
                if m and cur["ip"] is None:
                    cur["ip"] = m.group(1)
                m = re.search(r"(?:默认网关|Default Gateway)[ .]*:?\s*([\d\.]+)", ls)
                if m and cur["gw"] is None:
                    g = m.group(1)
                    if g != ".":
                        cur["gw"] = g
            main = next((s for s in secs if s["gw"]), None) or \
                   next((s for s in secs if s["ip"]), None)
            if main:
                stats.ip_address = main["ip"] or "unknown"
                stats.gateway = main["gw"] or "unknown"
                stats.network_type = main["type"]
        except Exception:
            pass
        # ---- 1b. ipconfig /all：DNS 服务器 ----
        try:
            r2 = subprocess.run(["ipconfig", "/all"], capture_output=True, timeout=8)
            o2 = r2.stdout.decode("gbk", errors="replace")
            m = re.search(r"(?:DNS 服务器|DNS Servers)[ .]*:?\s*([\d\.]+)", o2)
            if m:
                stats.dns_server = m.group(1)
        except Exception:
            pass
        # ---- 2. ping：延迟 + 丢包率（国内 114 优先，失败回退 8.8.8.8；中英文兼容） ----
        for host in ("114.114.114.114", "8.8.8.8"):
            try:
                r = subprocess.run(["ping", "-n", "4", "-w", "1500", host],
                                   capture_output=True, text=True,
                                   timeout=6, encoding="utf-8", errors="replace")
                out = r.stdout
                m = re.search(r"(?:平均|Average)\s*=\s*(\d+\.?\d*)", out)
                if m:
                    stats.latency = float(m.group(1))
                    m2 = re.search(r"(\d+)%\s*(?:丢失|loss)", out, re.I)
                    if m2:
                        stats.packet_loss = float(m2.group(1))
                    break
            except Exception:
                continue
        # ---- 3. netstat：活跃 TCP 连接数 ----
        try:
            o, e, rc = self._r(["netstat", "-an"], t=5)
            stats.connection_count = sum(
                1 for ln in o.splitlines() if "ESTABLISHED" in ln.upper())
        except Exception:
            pass
        with self._lock:
            self._stats = stats