# -*- coding: utf-8 -*-
"""PC系统信息工具"""
import subprocess, psutil
from pathlib import Path

def get_disk_info():
    disks = []
    for part in psutil.disk_partitions():
        if "cdrom" in part.opts or part.fstype == "iso9660": continue
        try:
            usage = psutil.disk_usage(part.mountpoint)
            disks.append({"device": part.device, "mountpoint": part.mountpoint,
                         "total": usage.total, "used": usage.used, "free": usage.free, "percent": usage.percent})
        except Exception: pass
    return disks

def get_network_info():
    nets = {}
    for name, addrs in psutil.net_if_addrs().items():
        if name == "lo": continue
        for addr in addrs:
            if addr.family.name == "AF_INET":
                nets[name] = {"ip": addr.address}
                break
    return nets

def get_process_list():
    procs = []
    for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
        try:
            procs.append({"pid": p.info["pid"], "name": p.info["name"],
                         "cpu": p.info["cpu_percent"] or 0, "memory": p.info["memory_percent"] or 0})
        except (psutil.NoSuchProcess, psutil.AccessDenied): pass
    return sorted(procs, key=lambda x: x["memory"], reverse=True)[:20]
