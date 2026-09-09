# -*- coding: utf-8 -*-
"""性能监控引擎"""
import threading
import time
import psutil
from config import THRESH, log

class SystemMetrics:
    class CPU:
        def __init__(self):
            self.usage_percent = 0.0
            self.temperature = 0.0
            self.core_count = psutil.cpu_count() or 1
            self.core_usage = [0.0]
            self.frequency = 0.0
    class Memory:
        def __init__(self):
            self.usage_percent = 0.0
            self.total_memory = 0
            self.available_memory = 0
            self.used_memory = 0
            self.cached_memory = 0
    class Storage:
        def __init__(self):
            self.total_space = '0 B'
            self.free_space = '0 B'
            self.used_space = '0 B'
            self.read_speed = 0.0
            self.write_speed = 0.0
    class Battery:
        def __init__(self):
            self.level = 100
            self.temperature = 0
            self.is_charging = False
            self.is_health_good = True
    def __init__(self):
        self.cpu = self.CPU()
        self.memory = self.Memory()
        self.storage = self.Storage()
        self.battery = self.Battery()

class PerformanceMonitor:
    def __init__(self):
        self._metrics = SystemMetrics()
        self._running = False
        self._monitor_thread = None

    def get_system_metrics(self):
        return self._metrics

    def get_performance_score(self):
        m = self._metrics
        score = 100.0
        if m.cpu.usage_percent > THRESH['cpu_warn']:
            score -= min(30, (m.cpu.usage_percent - THRESH['cpu_warn']) * 1.5)
        if m.cpu.usage_percent > THRESH['cpu_crit']:
            score -= 20
        if m.memory.usage_percent > THRESH['mem_warn']:
            score -= min(30, (m.memory.usage_percent - THRESH['mem_warn']) * 1.5)
        if m.memory.usage_percent > THRESH['mem_crit']:
            score -= 20
        try:
            pct = float(m.storage.used_space.replace('%', '')) if '%' in m.storage.used_space else 0
            if pct > THRESH['disk_warn']:
                score -= min(20, (pct - THRESH['disk_warn']) * 1.0)
        except: pass
        return max(0, min(100, score))

    def get_performance_issues(self):
        # 人性化性能问题描述：按严重程度分级，覆盖 CPU / 内存 / 磁盘 / 电池
        m = self._metrics
        issues = []
        cpu = m.cpu.usage_percent
        mem = m.memory.usage_percent
        disk_pct = 0.0
        try:
            disk_pct = float(m.storage.used_space.replace('%', '')) if '%' in m.storage.used_space else 0.0
        except Exception:
            pass
        # ---- CPU ----
        if cpu > THRESH['cpu_crit']:
            issues.append('电脑 CPU 已经接近满载（%.0f%%），现在用起来会明显卡顿，建议马上看看是哪个程序在"偷跑"' % cpu)
        elif cpu > THRESH['cpu_warn']:
            issues.append('CPU 占用有点偏高（%.0f%%），后台可能有一些程序在悄悄运行' % cpu)
        # ---- 内存 ----
        if mem > THRESH['mem_crit']:
            issues.append('内存快被占满了（%.0f%%），开着的程序太多，系统会越来越吃力' % mem)
        elif mem > THRESH['mem_warn']:
            issues.append('内存占用偏高（%.0f%%），再开几个大程序可能就会变卡' % mem)
        # ---- 磁盘 ----
        if disk_pct > THRESH['disk_crit']:
            issues.append('磁盘空间快用完了（%.0f%%），这会影响系统和软件的正常读写' % disk_pct)
        elif disk_pct > THRESH['disk_warn']:
            issues.append('磁盘使用率到 %.0f%% 了，建议抽空清理一下，给系统留点余地' % disk_pct)
        # ---- 电池 ----
        if m.battery.level < 20 and not m.battery.is_charging:
            issues.append('电池电量只剩 %d%%，建议连上充电器，免得突然断电丢工作' % m.battery.level)
        elif m.battery.level < 50 and not m.battery.is_charging:
            issues.append('电池电量还剩 %d%%，可以留意一下，方便时插上电源' % m.battery.level)
        if not issues:
            issues.append('各项指标都很健康，电脑状态不错，继续保持就好')
        return issues

    def get_optimization_suggestions(self):
        # 人性化优化建议：与问题一一呼应，给出具体可操作的动作
        m = self._metrics
        tips = []
        cpu = m.cpu.usage_percent
        mem = m.memory.usage_percent
        disk_pct = 0.0
        try:
            disk_pct = float(m.storage.used_space.replace('%', '')) if '%' in m.storage.used_space else 0.0
        except Exception:
            pass
        # ---- CPU ----
        if cpu > THRESH['cpu_warn']:
            tips.append('按 Ctrl+Shift+Esc 打开任务管理器，把占用最高的程序关掉，CPU 立刻轻松')
            tips.append('浏览器标签页别开太多，不看的随手关掉，也能省不少 CPU')
        # ---- 内存 ----
        if mem > THRESH['mem_warn']:
            tips.append('把不用的后台软件退掉（看右下角托盘图标，右键退出），内存马上就宽裕')
            tips.append('如果程序实在关不完，重启一次电脑是最快释放内存的办法')
        # ---- 磁盘 ----
        if disk_pct > THRESH['disk_warn']:
            tips.append('到「智能清理」里一键清理垃圾文件，能腾出不少空间')
            tips.append('把不常用的大文件移到其他磁盘或网盘，给系统盘减减压')
        # ---- 电池 ----
        if m.battery.level < 20 and not m.battery.is_charging:
            tips.append('插上充电器，让电脑安心工作，也可以全速运行')
        elif m.battery.level < 50 and not m.battery.is_charging:
            tips.append('电量不算多，方便时插上电源更稳妥')
        if not tips:
            tips.append('一切正常！有空可以用「智能清理」扫扫垃圾，保持好状态')
        return tips

    def start_monitoring(self):
        if self._running: return
        self._running = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        log.ok('性能监控已启动')

    def stop_monitoring(self):
        self._running = False
        if self._monitor_thread: self._monitor_thread.join(timeout=2)
        log.ok('性能监控已停止')

    def _monitor_loop(self):
        while self._running:
            try: self._update_metrics()
            except Exception: pass
            time.sleep(2)

    def _update_metrics(self):
        m = self._metrics
        m.cpu.usage_percent = psutil.cpu_percent(interval=0.5)
        m.core_usage = psutil.cpu_percent(interval=0, percpu=True)
        freq = psutil.cpu_freq()
        m.cpu.frequency = freq.current / 1000.0 if freq else 0.0
        m.cpu.temperature = 0
        vm = psutil.virtual_memory()
        m.memory.usage_percent = vm.percent
        m.memory.total_memory = vm.total
        m.memory.available_memory = vm.available
        m.memory.used_memory = vm.used
        m.memory.cached_memory = getattr(vm, 'cached', 0) or getattr(vm, 'buffers', 0)
        for part in psutil.disk_partitions():
            if 'cdrom' in part.opts or part.fstype == 'iso9660': continue
            try:
                u = psutil.disk_usage(part.mountpoint)
                m.storage.total_space = self._fmt(u.total)
                m.storage.free_space = self._fmt(u.free)
                m.storage.used_space = '%.1f%%' % u.percent
                break
            except: pass
        try:
            io = psutil.disk_io_counters()
            if io:
                m.storage.read_speed = io.read_bytes / 1048576
                m.storage.write_speed = io.write_bytes / 1048576
        except: pass
        bat = psutil.sensors_battery()
        if bat:
            m.battery.level = bat.percent
            m.battery.is_charging = bat.power_plugged
        else:
            m.battery.level = 100
            m.battery.is_charging = False

    def _fmt(self, b):
        for u in ['B', 'KB', 'MB', 'GB']:
            if b < 1024: return '%.1f %s' % (b, u)
            b /= 1024
        return '%.1f TB' % b