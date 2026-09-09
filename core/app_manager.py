# -*- coding: utf-8 -*-
"""应用管理引擎：扫描 / 卸载电脑应用（基于注册表卸载项）"""
import os
import re
import shlex
import subprocess
import winreg


class PCApp:
    """一条电脑已安装应用信息"""
    def __init__(self, name, version="", publisher="", size_mb=0.0,
                 uninstall_cmd="", quiet_cmd="", is_msi=False, key=""):
        self.name = name
        self.version = version
        self.publisher = publisher
        self.size_mb = size_mb
        self.uninstall_cmd = uninstall_cmd
        self.quiet_cmd = quiet_cmd
        self.is_msi = is_msi
        self.key = key

    def display_size(self):
        if self.size_mb >= 1024:
            return "%.1f GB" % (self.size_mb / 1024.0)
        if self.size_mb >= 1:
            return "%.0f MB" % self.size_mb
        return ""

    def summary(self):
        parts = []
        if self.version:
            parts.append(self.version)
        if self.publisher:
            parts.append(self.publisher)
        if self.display_size():
            parts.append(self.display_size())
        return " · ".join(parts)


class AppManager:
    """电脑应用扫描与卸载"""

    UNINSTALL_KEYS = [
        (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]

    # ---------- 扫描 ----------
    def list_pc_apps(self):
        """扫描已安装应用列表（过滤系统组件/驱动/补丁）"""
        apps = []
        seen = set()
        for hive, path in self.UNINSTALL_KEYS:
            try:
                with winreg.OpenKey(hive, path) as root:
                    for i in range(winreg.QueryInfoKey(root)[0]):
                        try:
                            sub = winreg.EnumKey(root, i)
                            with winreg.OpenKey(root, sub) as k:
                                vals = self._read_values(k)
                            if not vals:
                                continue
                            if not vals.get("DisplayName"):
                                continue
                            # 过滤：系统组件、驱动、父程序组件、更新补丁
                            if str(vals.get("SystemComponent", "")).strip() in ("1", "2"):
                                continue
                            if vals.get("ParentKeyName") or vals.get("ParentDisplayName"):
                                continue
                            if vals.get("ReleaseType") and str(vals.get("ReleaseType")).strip():
                                continue
                            name = str(vals["DisplayName"]).strip()
                            if not name or name in seen:
                                continue
                            seen.add(name)
                            cmd = str(vals.get("UninstallString", "") or "").strip()
                            quiet = str(vals.get("QuietUninstallString", "") or "").strip()
                            if not cmd and not quiet:
                                continue
                            is_msi = ("msiexec" in cmd.lower()) or ("msiexec" in quiet.lower())
                            try:
                                size_mb = round(int(vals.get("EstimatedSize") or 0) / 1024.0, 1)
                            except (TypeError, ValueError):
                                size_mb = 0.0
                            apps.append(PCApp(
                                name=name,
                                version=str(vals.get("DisplayVersion", "") or "").strip(),
                                publisher=str(vals.get("Publisher", "") or "").strip(),
                                size_mb=size_mb,
                                uninstall_cmd=cmd,
                                quiet_cmd=quiet,
                                is_msi=is_msi,
                                key=sub,
                            ))
                        except OSError:
                            continue
            except OSError:
                continue
        apps.sort(key=lambda a: a.name.lower())
        return apps

    @staticmethod
    def _read_values(key):
        vals = {}
        try:
            n = winreg.QueryInfoKey(key)[1]
            for j in range(n):
                try:
                    name, data, _ = winreg.EnumValue(key, j)
                    vals[name] = data
                except OSError:
                    break
        except OSError:
            pass
        return vals

    # ---------- 卸载 ----------
    @staticmethod
    def _parse_uninstall_cmd(cmd):
        """解析 Windows 卸载命令为参数列表；无法定位文件时返回 None。
        兼容：引号包裹路径 / 无引号含空格路径 / 已带参数等格式。"""
        cmd = cmd.strip()
        if not cmd:
            return None
        # 引号包裹的路径（如 "C:\Program Files\X\unins000.exe" /S）
        if cmd.startswith('"'):
            end = cmd.find('"', 1)
            if end > 0:
                exe = cmd[1:end]
                args = cmd[end + 1:].strip()
                if os.path.isfile(exe):
                    return [exe] + (shlex.split(args, posix=False) if args else [])
                return None
        # 无引号：先尝试整体（路径含空格未加引号的情况）
        if os.path.isfile(cmd):
            return [cmd]
        # 再按第一个空格拆分（Windows 惯例：首个 token 为程序路径）
        parts = cmd.split(None, 1)
        exe = parts[0]
        if os.path.isfile(exe):
            args = parts[1].strip() if len(parts) > 1 and parts[1].strip() else ""
            return [exe] + (shlex.split(args, posix=False) if args else [])
        # 带引号但与其它内容混合（如 MsiExec.exe /X{GUID}）
        exe2 = exe.strip('"')
        if os.path.isfile(exe2):
            args = parts[1].strip() if len(parts) > 1 and parts[1].strip() else ""
            return [exe2] + (shlex.split(args, posix=False) if args else [])
        return None

    def uninstall_pc(self, app):
        """卸载指定应用；返回 (成功?, 提示消息)"""
        cmd = app.quiet_cmd or app.uninstall_cmd
        if not cmd:
            return False, "该应用没有提供卸载命令，无法自动卸载"

        # MSI 应用：统一走 msiexec 静默卸载
        if app.is_msi:
            m = re.search(r"\{[0-9A-Fa-f\-]{36}\}", cmd)
            if not m:
                return False, "MSI 卸载信息不完整（缺少产品代码）"
            argv = ["msiexec", "/x", m.group(0), "/qn", "/norestart"]
        else:
            argv = self._parse_uninstall_cmd(cmd)
            if argv is None:
                return False, "卸载程序文件不存在（应用可能已被手动删除，注册表残留）"
            if len(argv) == 1 and argv[0].lower().endswith(".exe"):
                argv.append("/S")

        try:
            r = subprocess.run(argv, capture_output=True, text=True,
                               timeout=180, encoding="utf-8", errors="replace")
            ok = r.returncode == 0
            msg = (r.stdout or r.stderr or "").strip()
            if ok:
                return True, "卸载命令已执行完成"
            return False, ("卸载失败（退出码 %s）" % r.returncode) + (("：" + msg[:80]) if msg else "")
        except subprocess.TimeoutExpired:
            return False, "卸载超时（部分卸载器需要手动完成）"
        except FileNotFoundError:
            return False, "卸载程序文件不存在（应用可能已被手动删除，注册表残留）"
        except Exception as e:
            return False, "卸载出错：" + str(e)
