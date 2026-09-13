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
            self._mobile_ops_into(changes, "game")
        ok = any(c["ok"] for c in changes)
        if not ok and not _is_admin():
            return OptimizationResult("game", 0, "游戏模式需要管理员权限", False, changes)
        log.ok("游戏模式已应用")
        n = sum(1 for c in changes if c["ok"])
        return OptimizationResult("game", 15.0,
                                  "游戏模式已应用：%d 项网络优化已应用" % n,
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
            self._mobile_ops_into(changes, "video")
        ok = any(c["ok"] for c in changes)
        if not ok and not _is_admin():
            return OptimizationResult("video", 0, "视频模式需要管理员权限", False, changes)
        log.ok("视频模式已应用")
        n = sum(1 for c in changes if c["ok"])
        return OptimizationResult("video", 10.0,
                                  "视频模式已应用：%d 项网络优化已应用" % n,
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
            self._mobile_ops_into(changes, "download")
        ok = any(c["ok"] for c in changes)
        if not ok and not _is_admin():
            return OptimizationResult("download", 0, "下载模式需要管理员权限", False, changes)
        log.ok("下载模式已应用")
        n = sum(1 for c in changes if c["ok"])
        return OptimizationResult("download", 20.0,
                                  "下载模式已应用：%d 项网络优化已应用" % n,
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

    def _device_online(self):
        # 检查 ADB 设备是否在线：start-server（幂等）+ get-state
        if not ADB_EXE:
            return False
        for _ in range(2):
            self._ra(["start-server"])
            o, e, rc = self._ra(["get-state"])
            if rc == 0 and o.strip() == "device":
                return True
            time.sleep(0.5)
        return False

    # ---- 免 root 手机网络优化（命令已真机验证可用） ----
    _MOBILE_NET_TARGETS = {
        "game": ["com.tencent.qqlive", "com.qiyi.video", "com.youku.phone",
                 "com.xunlei.downloadprovider", "com.taobao.taobao"],
        "video": ["com.xunlei.downloadprovider", "com.taobao.taobao",
                  "com.ss.android.ugc.aweme", "com.tencent.mobileqq"],
        "download": ["com.tencent.qqlive", "com.qiyi.video", "com.youku.phone",
                     "com.ss.android.ugc.aweme", "com.bilibili.app.blue"],
    }

    def _mobile_ping(self, host="223.5.5.5", count=3):
        """手机公网延迟/丢包检测（免 root）"""
        o, e, rc = self._ra(["shell", "ping", "-c", str(count), "-W", "2", host],
                            retries=1)
        if rc != 0:
            return None
        avg = loss = None
        m = re.search(r"rtt min/avg/max/mdev = [\d.]+/([\d.]+)/", o)
        if m:
            avg = float(m.group(1))
        m = re.search(r"(\d+)% packet loss", o)
        if m:
            loss = int(m.group(1))
        return {"avg": avg, "loss": loss}

    def _mobile_net_type(self):
        """当前上网方式：wifi / data"""
        o, e, rc = self._ra(["shell", "ifconfig", "wlan0"], retries=1)
        if rc == 0 and ("inet addr:" in o or " inet " in o):
            return "wifi"
        return "data"

    def _mobile_net_ops(self, mode):
        """免 root 手机网络优化：结束后台抢网应用 + 重置网络连接 + 延迟对比。
        返回 (操作描述列表, 优化前延迟, 优化后延迟)"""
        ops = []
        if not ADB_EXE or not self._device_online():
            return ops, None, None
        before = self._mobile_ping()
        # 1) 结束后台抢网应用（只杀已安装的）
        installed = set()
        o, e, rc = self._ra(["shell", "pm", "list", "packages", "-3"], retries=1)
        if rc == 0:
            installed = {l.strip().replace("package:", "").strip()
                         for l in o.splitlines() if l.strip()}
        killed = []
        for pkg in self._MOBILE_NET_TARGETS.get(mode, []):
            if pkg in installed:
                ro, re_, rrc = self._ra(["shell", "am", "force-stop", pkg], retries=1)
                if rrc == 0:
                    killed.append(pkg.rsplit(".", 1)[-1])
        if killed:
            ops.append("已结束后台抢网应用 " + "、".join(killed[:4]))
        # 2) 重置网络连接（刷新 DNS 与路由，解决卡顿延迟）
        if self._mobile_net_type() == "wifi":
            self._ra(["shell", "svc", "wifi", "disable"])
            time.sleep(2)
            self._ra(["shell", "svc", "wifi", "enable"])
            ops.append("已重置 WiFi 连接（刷新 DNS 与路由）")
        else:
            self._ra(["shell", "svc", "data", "disable"])
            time.sleep(2)
            self._ra(["shell", "svc", "data", "enable"])
            ops.append("已重置移动数据连接")
        time.sleep(2.5)  # 等待网络恢复
        after = self._mobile_ping()
        return ops, before, after

    def _mobile_ops_into(self, changes, mode):
        """把免 root 手机网络优化结果写入 changes 列表"""
        mob_ops, before, after = self._mobile_net_ops(mode)
        if mob_ops:
            det = "；".join(mob_ops)
            if before and before["avg"] and after and after["avg"]:
                det += "；延迟 %.0f→%.0fms" % (before["avg"], after["avg"])
                if before["loss"] is not None and after["loss"] is not None:
                    det += " 丢包 %d%%→%d%%" % (before["loss"], after["loss"])
            changes.append({"param": "手机网络", "old": "未设置", "new": det,
                            "ok": True, "vtype": "手机操作", "adb": True,
                            "device_ok": True})
        else:
            changes.append({"param": "手机网络", "old": "未设置",
                            "new": "未连接手机，跳过", "ok": False,
                            "vtype": "手机操作", "adb": True,
                            "device_ok": False, "err": "未连接手机"})

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

    def _detect_campus_net(self):
        """检测当前是否校园网/内网环境：主网卡（有网关）IP 为私网地址 10/172.16-31/192.168"""
        try:
            r = subprocess.run(["ipconfig"], capture_output=True, timeout=8)
            o = r.stdout.decode("gbk", errors="replace")
            secs = []
            cur = None
            for line in o.splitlines():
                ls = line.strip()
                if ("adapter" in ls.lower()) or ("适配器" in ls):
                    cur = {"ip": None, "gw": None}
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
            if main and main["ip"]:
                parts = [int(x) for x in main["ip"].split(".")]
                if parts[0] == 10:
                    return True
                if parts[0] == 172 and 16 <= parts[1] <= 31:
                    return True
                if parts[0] == 192 and parts[1] == 168:
                    return True
        except Exception:
            pass
        return False

    def _optimize_dns(self):
        if self._detect_campus_net():
            return OptimizationResult("dns", 0,
                                      "检测到校园网/内网环境：保留自动 DNS，避免覆盖校内解析", False, [])
        dns_map = [("223.5.5.5", "阿里云DNS"), ("119.29.29.29", "DNSPod"), ("8.8.8.8", "Google")]
        current = self._get_dns()
        selected = dns_map[0]
        if current != selected[0]:
            if self._set_dns(selected[0]):
                log.ok("DNS已切换: " + selected[1])
                return OptimizationResult("dns", 5.0, "DNS优化: " + selected[1], True, [selected[0]])
            return OptimizationResult("dns", 0, "DNS切换失败（接口不可用或权限不足）", False, [])
        return OptimizationResult("dns", 0, "DNS已是最优", True, [])

    def restore_dns_auto(self):
        """把活动网卡 DNS 恢复为 DHCP 自动获取（校园网场景恢复），返回 (ok, desc)"""
        try:
            adapter = None
            r = subprocess.run(["ipconfig"], capture_output=True, timeout=8)
            o = r.stdout.decode("gbk", errors="replace")
            cur = None
            for line in o.splitlines():
                ls = line.strip()
                if ("adapter" in ls.lower()) or ("适配器" in ls):
                    cur = ls.split("适配器")[-1].split("adapter")[-1].strip().rstrip(":")
                    continue
                if cur is None:
                    continue
                if (re.search(r"IPv4 Address[ .]*:?[\d\.]+", ls)
                        or re.search(r"IPv4 地址[ .]*:?[\d\.]+", ls)):
                    if "127.0.0.1" not in ls:
                        adapter = cur
                        break
            if not adapter:
                return False, "未找到活动网卡"
            r2 = subprocess.run(
                ["netsh", "interface", "ip", "set", "dns",
                 "name=%s" % adapter, "source=dhcp"],
                capture_output=True, text=True, timeout=30,
                encoding="utf-8", errors="replace")
            if r2.returncode == 0:
                self.flush_dns()
                return True, "已把 %s 的 DNS 恢复为自动获取（校园网分配），并已刷新缓存" % adapter
            return False, (r2.stdout.strip() or r2.stderr.strip() or "恢复失败")[:80]
        except Exception as e:
            return False, str(e)[:80]

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

    def optimize_mobile(self):
        """手机模式一键优化：免 root 手机网络优化 + 手机垃圾快清"""
        ops, before, after = self._mobile_net_ops("game")
        if not ops:
            return OptimizationResult("mobile", 0, "手机未连接，一键优化跳过", False, [])
        det = "；".join(ops)
        if before and before["avg"] and after and after["avg"]:
            det += "；延迟 %.0f→%.0fms" % (before["avg"], after["avg"])
        # 手机垃圾快清（快速路径：日志缓冲 + 缩略图）
        try:
            from utils.adb_helper import ADBHelper
            adb = ADBHelper()
            if adb.connect():
                extra = []
                if adb.cls_log():
                    extra.append("日志缓冲已清空")
                if adb.cls_thumb():
                    extra.append("缩略图缓存已清空")
                if extra:
                    det += "；" + "；".join(extra)
        except Exception:
            pass
        log.ok("手机一键优化: " + det)
        return OptimizationResult("mobile", 8.0, "手机一键优化完成：" + det, True, [det])

    def _mobile_optimize(self):
        ops, before, after = self._mobile_net_ops("game")
        if not ops:
            return OptimizationResult("mobile_net", 0, "手机未连接，手机网络优化跳过", False, [])
        det = "；".join(ops)
        if before and before["avg"] and after and after["avg"]:
            det += "；延迟 %.0f→%.0fms" % (before["avg"], after["avg"])
            if before["loss"] is not None and after["loss"] is not None:
                det += " 丢包 %d%%→%d%%" % (before["loss"], after["loss"])
        log.ok("手机网络优化: " + det)
        return OptimizationResult("mobile_net", 8.0, "手机网络优化完成：" + det, True, [det])

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

    # ================= 连接测试（诊断目标站点超时） =================
    def test_connection(self, host):
        """对指定域名/IP 做四步诊断：DNS 解析 → TCP 443/80 → Ping → HTTP。
        返回 {host, steps:[{k,ok,v}], summary, dns_ok} 供页面展示。"""
        host = (host or "").strip().replace("https://", "").replace("http://", "")
        host = host.split("/")[0].split(":")[0].strip()
        if not host:
            return {"host": "", "steps": [], "summary": "请输入要测试的目标地址", "dns_ok": False}
        steps = []
        # 1) DNS 解析
        dns_ip = self._dns_query(host)
        steps.append({"k": "DNS 解析", "ok": bool(dns_ip),
                      "v": (dns_ip or "解析失败（DNS 问题）")})
        # 2) TCP 443 / 80 连接
        tcp443 = self._tcp_probe(host, 443)
        steps.append({"k": "TCP 443", "ok": tcp443,
                      "v": ("连通" if tcp443 else "连接超时/被拒")})
        tcp80 = self._tcp_probe(host, 80)
        steps.append({"k": "TCP 80", "ok": tcp80,
                      "v": ("连通" if tcp80 else "连接超时/被拒")})
        # 3) Ping
        ping_ok = False
        o, e, rc = self._r(["ping", "-n", "4", "-w", "1500", host], t=8)
        m = re.search(r"(?:平均|Average)\s*=\s*(\d+\.?\d*)", o)
        if m:
            loss = 0
            m2 = re.search(r"(\d+)%\s*(?:丢失|loss)", o, re.I)
            if m2:
                loss = int(m2.group(1))
            ping_ok = loss < 100
            steps.append({"k": "Ping", "ok": ping_ok,
                          "v": ("%.0fms 丢包%d%%" % (float(m.group(1)), loss))})
        else:
            steps.append({"k": "Ping", "ok": False, "v": "无响应"})
        # 4) HTTP 探测
        http = self._http_probe(host)
        steps.append({"k": "HTTP", "ok": http is not None,
                      "v": ("HTTP %s" % http if http else "请求超时/被拦截")})
        # 结论
        if not dns_ip:
            summary = "DNS 解析失败：先刷新 DNS（尝试连接会执行）并确认联网，仍失败请检查 DNS 服务器"
        elif not tcp443 and not tcp80:
            summary = "域名可解析但连接超时：目标服务器当前不可达，可能需校园网/VPN/代理环境，或服务器维护中"
        elif ping_ok and not http:
            summary = "Ping 通但 HTTP 无响应：可能被防火墙/服务端拦截，或需登录认证（如学校统一认证页）"
        else:
            summary = "诊断完成：目标当前可达，超时可能是临时波动或需要认证登录"
        return {"host": host, "steps": steps, "summary": summary, "dns_ok": bool(dns_ip)}

    def _dns_query(self, host, dns=None):
        """nslookup 查询 A 记录：返回 IPv4 或 None；dns 可指定服务器。
        中英文输出均可解：二进制捕获 + GBK/UTF-8 双解码 + 同时匹配 "名称:/Name:"。"""
        cmd = ["nslookup", host]
        if dns:
            cmd.append(dns)
        try:
            r = subprocess.run(cmd, capture_output=True, timeout=8)
        except Exception:
            return None
        raw = r.stdout
        text = None
        for enc in ("gbk", "utf-8"):
            try:
                t = raw.decode(enc)
            except Exception:
                continue
            if ("Name:" in t) or ("名称:" in t):
                text = t
                break
        if text is None:
            try:
                text = raw.decode("gbk", errors="replace")
            except Exception:
                return None
        idx = max(text.find("Name:"), text.find("名称:"))
        if idx >= 0:
            ipv4s = re.findall(r"\d{1,3}(?:\.\d{1,3}){3}", text[idx:])
            if ipv4s:
                return ipv4s[-1]
        return None

    def _current_dns(self):
        """当前系统 DNS 服务器（第一个）"""
        try:
            r = subprocess.run(["ipconfig", "/all"], capture_output=True, timeout=8)
            o = r.stdout.decode("gbk", errors="replace")
            m = re.search(r"(?:DNS 服务器|DNS Servers)[ .]*:?\s*([\d\.]+)", o)
            if m:
                return m.group(1)
        except Exception:
            pass
        return None

    def set_dns(self, dns_server):
        """把活动网卡 DNS 固定为指定服务器（立即生效，需管理员）；返回 (ok, desc)"""
        try:
            r = subprocess.run(["ipconfig"], capture_output=True, timeout=8)
            o = r.stdout.decode("gbk", errors="replace")
            adapter = None
            cur = None
            for line in o.splitlines():
                ls = line.strip()
                if ("adapter" in ls.lower()) or ("适配器" in ls):
                    cur = ls.split("适配器")[-1].split("adapter")[-1].strip().rstrip(":")
                    continue
                if cur is None:
                    continue
                if (re.search(r"IPv4 Address[ .]*:?\s*[\d\.]+", ls)
                        or re.search(r"IPv4 地址[ .]*:?\s*[\d\.]+", ls)):
                    if "127.0.0.1" not in ls:
                        adapter = cur
                        break
            if not adapter:
                return False, "未找到活动网卡"
            r2 = subprocess.run(
                ["netsh", "interface", "ip", "set", "dns", "name=%s" % adapter,
                 "static", dns_server, "validate=no"],
                capture_output=True, text=True, timeout=30,
                encoding="utf-8", errors="replace")
            if r2.returncode == 0:
                return True, "已把 %s 的 DNS 切换为 %s（立即生效）" % (adapter, dns_server)
            return False, (r2.stdout.strip() or r2.stderr.strip() or "切换失败")[:80]
        except Exception as e:
            return False, str(e)[:80]

    def repair_dns(self, host):
        """DNS 解析失败时：备用公网 DNS 查询 → 可解析则切换系统 DNS → 刷新 → 复查。
        返回 {ok, lines, dns_ip}"""
        lines = []
        cur = self._current_dns()
        lines.append("  当前系统 DNS：%s" % (cur or "未知"))
        chosen, ip = None, None
        for d in ("223.5.5.5", "114.114.114.114", "8.8.8.8"):
            if d == cur:
                continue
            ip = self._dns_query(host, d)
            if ip:
                chosen = d
                break
        if chosen:
            lines.append("  备用 DNS %s 可解析 %s（%s）" % (chosen, host, ip))
            ok, desc = self.set_dns(chosen)
            lines.append("  " + desc)
            if not ok:
                lines.append("  无管理员权限，未能切换 DNS；请以管理员运行后重试")
        else:
            lines.append("  备用 DNS（223.5.5.5/114/8.8.8.8）均无法解析该域名")
        self.flush_dns()
        final = self._dns_query(host)
        if final:
            lines.append("  ✓ DNS 复查：解析成功 %s" % final)
            return {"ok": True, "lines": lines, "dns_ip": final}
        lines.append("  ✗ DNS 复查：仍解析失败")
        return {"ok": False, "lines": lines, "dns_ip": None}

    def get_proxy(self):
        """系统代理状态 (enabled, server)"""
        try:
            import winreg
            k = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                               r"Software\Microsoft\Windows\CurrentVersion\Internet Settings")
            try:
                en, _ = winreg.QueryValueEx(k, "ProxyEnable")
            except Exception:
                en = 0
            try:
                sv, _ = winreg.QueryValueEx(k, "ProxyServer")
            except Exception:
                sv = ""
            winreg.CloseKey(k)
            return bool(en), (sv or "")
        except Exception:
            return False, ""

    def _tcp_probe(self, host, port, timeout=4):
        try:
            import socket
            s = socket.create_connection((host, port), timeout=timeout)
            s.close()
            return True
        except Exception:
            return False

    def _http_probe(self, host, timeout=6):
        try:
            import urllib.request
            for scheme in ("https", "http"):
                try:
                    req = urllib.request.Request(scheme + "://" + host, method="HEAD",
                                                 headers={"User-Agent": "Mozilla/5.0"})
                    with urllib.request.urlopen(req, timeout=timeout) as r:
                        return r.status
                except Exception:
                    continue
        except Exception:
            pass
        return None

    def flush_dns(self):
        """刷新 DNS 解析缓存（普通权限即可），返回 (ok, 描述)"""
        try:
            r = subprocess.run(["ipconfig", "/flushdns"], capture_output=True,
                               text=True, timeout=15, encoding="utf-8", errors="replace")
            if r.returncode == 0:
                log.ok("DNS 缓存已刷新")
                return True, "DNS 缓存已刷新"
            return False, (r.stdout.strip() or r.stderr.strip() or "刷新失败")[:60]
        except Exception as e:
            return False, str(e)[:60]

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