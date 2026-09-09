# -*- coding: utf-8 -*-
"""智能垃圾清理引擎 - 全类型扫描 + 并行加速版"""
import os
import time
import subprocess
import shutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import psutil
from config import ADB_EXE, log

MAX_FILES = 40000  # 单类目文件数上限，防超大目录卡死
_WORKERS = 6      # 扫描并行度


class CleanTarget:
    def __init__(self, category, name, description, size=0, file_count=0,
                 selected=False, is_safe=True, files=None):
        self.category = category
        self.name = name
        self.description = description
        self.size = size
        self.file_count = file_count
        self.is_selected = selected
        self.is_safe = is_safe
        self.files = files or []


class CleanResult:
    def __init__(self, success=False, message='', steps=None, total_size=0, total_files=0,
                 failed_files=0, need_admin=False):
        self.success = success
        self.message = message
        self.steps = steps or []
        self.total_size = total_size
        self.total_files = total_files
        self.failed_files = failed_files
        self.need_admin = need_admin


def _walk_fast(root, max_files=MAX_FILES, ext_filter=None, skip_dirs=None,
               max_depth=None, only_size=False):
    """快速遍历目录：os.scandir 栈式实现，返回 (files, total_size)
    files: list[(path, size)]；ext_filter: 小写后缀集合或 None；max_depth: None 不限深
    """
    files = []
    total = 0
    root = str(root)
    if not os.path.isdir(root):
        return files, total
    try:
        st = os.stat(root)
        if only_size and st.st_size > 0 and not os.path.isdir(root):
            return [(root, st.st_size)], st.st_size
    except Exception:
        pass
    stack = [(root, 0)]
    skip = set(skip_dirs or ())
    while stack and len(files) < max_files:
        d, depth = stack.pop()
        if max_depth is not None and depth >= max_depth:
            continue
        try:
            with os.scandir(d) as it:
                for e in it:
                    if len(files) >= max_files:
                        break
                    try:
                        if e.is_dir(follow_symlinks=False):
                            if skip and e.name.lower() in skip:
                                continue
                            stack.append((e.path, depth + 1))
                        else:
                            if ext_filter is not None:
                                ext = os.path.splitext(e.name)[1].lower()
                                if ext not in ext_filter:
                                    continue
                            try:
                                sz = e.stat(follow_symlinks=False).st_size
                            except Exception:
                                sz = 0
                            files.append((e.path, sz))
                            total += sz
                    except OSError:
                        continue
        except (OSError, PermissionError):
            continue
    return files, total


def _fast_delete(paths):
    """批量删除文件（跳过 stat，直接 unlink），返回 (删除数, 释放大小, 失败数)"""
    n = 0
    size = 0
    failed = 0
    for p, sz in paths:
        try:
            os.unlink(p)
            n += 1
            size += sz
        except Exception:
            failed += 1
    return n, size, failed


class SmartCleaner:
    def __init__(self):
        self._lock = None
        self._targets = []
        self._log_steps = []

    # ================= 扫描（全类型、并行） =================
    def scan_for_junk(self):
        """扫描垃圾文件 - 全类型并行扫描，返回 CleanTarget 列表"""
        self._log_steps = []
        self._log_steps.append("[扫描] 并行扫描 10 类垃圾...")
        t0 = time.time()
        targets = self._scan_pc_junk()
        self._log_steps.append("[扫描] 完成，共 %d 类 %d 项（%.2f 秒）"
                               % (len(targets),
                                  sum(t.file_count for t in targets),
                                  time.time() - t0))
        return targets

    def _scan_pc_junk(self):
        """扫描 PC 全部垃圾类型 - 线程池并行，只统计不删除"""
        tasks = [
            self._scan_system_temp,
            self._scan_win_update,
            self._scan_prefetch,
            self._scan_minidump,
            self._scan_browser_cache,
            self._scan_icon_cache,
            self._scan_thumbs,
            self._scan_recycle,
            self._scan_drive_junk,
            self._scan_download_junk,
            self._scan_logs,
        ]
        targets = []
        with ThreadPoolExecutor(max_workers=_WORKERS) as ex:
            for t in ex.map(lambda f: f(), tasks):
                if t is not None and t.file_count > 0:
                    targets.append(t)
        self._targets = targets
        return targets

    # ---- 各类型扫描 ----
    def _scan_system_temp(self):
        temp_dirs = [os.environ.get('TEMP', ''), os.environ.get('TMP', ''),
                     os.path.join(os.environ.get('WINDIR', 'C:/Windows'), 'Temp')]
        size = files = 0
        for d in dict.fromkeys(x for x in temp_dirs if x and os.path.isdir(x)):
            fl, sz = _walk_fast(d, max_files=MAX_FILES)
            files += len(fl)
            size += sz
        if files:
            return CleanTarget('system_temp', '系统临时文件',
                               '用户 Temp 与 Windows\\Temp 中的临时文件',
                               size, files, True, True)
        return None

    def _scan_win_update(self):
        d = os.path.join(os.environ.get('WINDIR', 'C:/Windows'),
                         'SoftwareDistribution', 'Download')
        if not os.path.isdir(d):
            return None
        fl, sz = _walk_fast(d, max_files=MAX_FILES)
        if fl:
            return CleanTarget('win_update', 'Windows 更新缓存',
                               'Windows 更新下载缓存（SoftwareDistribution\\Download）',
                               sz, len(fl), True, True)
        return None

    def _scan_prefetch(self):
        d = os.path.join(os.environ.get('WINDIR', 'C:/Windows'), 'Prefetch')
        if not os.path.isdir(d):
            return None
        fl, sz = _walk_fast(d, ext_filter={'.pf'})
        if fl:
            return CleanTarget('prefetch', '预取文件缓存',
                               'C:\\Windows\\Prefetch 程序预取文件',
                               sz, len(fl), True, True)
        return None

    def _scan_minidump(self):
        d = os.path.join(os.environ.get('WINDIR', 'C:/Windows'), 'Minidump')
        size = files = 0
        if os.path.isdir(d):
            fl, sz = _walk_fast(d)
            size += sz
            files += len(fl)
        mem = os.path.join(os.environ.get('WINDIR', 'C:/Windows'), 'MEMORY.DMP')
        try:
            if os.path.isfile(mem):
                size += os.path.getsize(mem)
                files += 1
        except Exception:
            pass
        if files:
            return CleanTarget('minidump', '系统错误转储',
                               'Minidump 崩溃转储 / MEMORY.DMP 内存转储',
                               size, files, True, True)
        return None

    def _scan_browser_cache(self):
        local_app = os.environ.get('LOCALAPPDATA', '')
        app_data = os.environ.get('APPDATA', '')
        dirs = [
            (os.path.join(local_app, 'Google/Chrome/User Data/Default/Cache'), 'Chrome'),
            (os.path.join(local_app, 'Google/Chrome/User Data/Default/Code Cache'), 'Chrome'),
            (os.path.join(local_app, 'Google/Chrome/User Data/Default/GPUCache'), 'Chrome'),
            (os.path.join(local_app, 'Microsoft/Edge/User Data/Default/Cache'), 'Edge'),
            (os.path.join(local_app, 'Microsoft/Edge/User Data/Default/Code Cache'), 'Edge'),
            (os.path.join(local_app, 'Microsoft/Edge/User Data/Default/GPUCache'), 'Edge'),
        ]
        # Firefox 配置目录
        ff_root = os.path.join(app_data, 'Mozilla/Firefox/Profiles') if app_data else ''
        if os.path.isdir(ff_root):
            try:
                for e in os.scandir(ff_root):
                    if e.is_dir():
                        dirs.append((os.path.join(e.path, 'cache2'), 'Firefox'))
                        dirs.append((os.path.join(e.path, 'thumbnails'), 'Firefox'))
                        dirs.append((os.path.join(e.path, 'offlinecache'), 'Firefox'))
            except OSError:
                pass
        size = files = 0
        names = set()
        for d, label in dirs:
            if not os.path.isdir(d):
                continue
            names.add(label)
            fl, sz = _walk_fast(d, max_files=MAX_FILES)
            files += len(fl)
            size += sz
        if files:
            return CleanTarget('browser_cache', '浏览器缓存',
                               ' / '.join(sorted(names)) + ' 网页缓存与代码缓存',
                               size, files, True, True)
        return None

    def _scan_icon_cache(self):
        size = files = 0
        local_app = os.environ.get('LOCALAPPDATA', '')
        icon = os.path.join(local_app, 'IconCache.db')
        try:
            if os.path.isfile(icon):
                size += os.path.getsize(icon)
                files += 1
        except Exception:
            pass
        ex = os.path.join(local_app, 'Microsoft/Windows/Explorer')
        if os.path.isdir(ex):
            try:
                for e in os.scandir(ex):
                    if e.name.lower().startswith('iconcache_') and e.is_file():
                        try:
                            size += e.stat().st_size
                            files += 1
                        except Exception:
                            pass
            except OSError:
                pass
        if files:
            return CleanTarget('icon_cache', '图标缓存',
                               'IconCache.db 与 Explorer 图标缓存',
                               size, files, True, True)
        return None

    def _scan_thumbs(self):
        """缩略图缓存：Explorer thumbcache + 用户常用目录浅层 Thumbs.db"""
        size = files = 0
        local_app = os.environ.get('LOCALAPPDATA', '')
        ex = os.path.join(local_app, 'Microsoft/Windows/Explorer')
        if os.path.isdir(ex):
            try:
                for e in os.scandir(ex):
                    if e.name.lower().startswith('thumbcache_') and e.is_file():
                        try:
                            size += e.stat().st_size
                            files += 1
                        except Exception:
                            pass
            except OSError:
                pass
        home = os.path.expanduser('~')
        for sub in ('Desktop', 'Documents', 'Downloads', 'Pictures', 'Music', 'Videos'):
            dd = os.path.join(home, sub)
            if os.path.isdir(dd):
                fl, sz = _walk_fast(dd, ext_filter={'.db'}, max_depth=2)
                for p, s in fl:
                    if os.path.basename(p).lower() == 'thumbs.db':
                        size += s
                        files += 1
        if files:
            return CleanTarget('thumbs', '缩略图缓存',
                               'Thumbcache 缩略图库与 Thumbs.db',
                               size, files, True, True)
        return None

    def _scan_recycle(self):
        """回收站（只统计，默认不勾选——删除不可恢复）"""
        size = files = 0
        for drive in ['C:', 'D:', 'E:', 'F:']:
            rb = os.path.join(drive + os.sep, '$Recycle.Bin')
            if os.path.isdir(rb):
                fl, sz = _walk_fast(rb, max_files=MAX_FILES)
                files += len(fl)
                size += sz
        if files:
            return CleanTarget('recycle', '回收站',
                               '回收站中待删除文件（清空后不可恢复）',
                               size, files, False, False)
        return None

    def _scan_drive_junk(self):
        size = files = 0
        for drive in ['C:', 'D:', 'E:', 'F:']:
            root = drive + os.sep
            try:
                with os.scandir(root) as it:
                    for e in it:
                        try:
                            if e.is_file():
                                low = e.name.lower()
                                if low.endswith('.tmp') or low.startswith('~$') or low == 'thumbs.db':
                                    try:
                                        size += e.stat().st_size
                                    except Exception:
                                        pass
                                    files += 1
                        except OSError:
                            continue
            except OSError:
                continue
        if files:
            return CleanTarget('drive_junk', '磁盘根目录散件',
                               '各盘根目录的 *.tmp、~$ 临时文件',
                               size, files, True, True)
        return None

    def _scan_download_junk(self):
        dl = os.path.join(os.path.expanduser('~'), 'Downloads')
        if not os.path.isdir(dl):
            return None
        size = files = 0
        try:
            with os.scandir(dl) as it:
                for e in it:
                    try:
                        if e.is_file() and os.path.splitext(e.name)[1].lower() in (
                                '.tmp', '.part', '.crdownload', '.download'):
                            size += e.stat().st_size
                            files += 1
                    except OSError:
                        pass
        except OSError:
            pass
        if files:
            return CleanTarget('download_jnk', '下载垃圾文件',
                               '下载目录中的未完成/临时文件',
                               size, files, True, True)
        return None

    def _scan_logs(self):
        d = os.path.join(os.environ.get('WINDIR', 'C:/Windows'), 'Logs')
        if not os.path.isdir(d):
            return None
        fl, sz = _walk_fast(d, ext_filter={'.log', '.etl'}, max_depth=3)
        if fl:
            return CleanTarget('system_logs', '系统日志文件',
                               'Windows\\Logs 下的旧日志 (.log/.etl)',
                               sz, len(fl), True, True)
        return None

    # ================= 清理（并行加速） =================
    def clean_all(self):
        """一键清理 - 并行清理全部类型，保留 8 步日志"""
        self._log_steps = []
        self._log_steps.append("=" * 80)
        self._log_steps.append("[开始] 电脑开始清理")
        self._log_steps.append("=" * 80)

        self._scan_pc_junk()  # 只扫描，不清空本方法日志
        total_size = total_files = total_failed = 0
        admin_jobs = ('[2/8]', '[4/8]', '[5/8]', '[6/8]')  # 需管理员权限的系统目录
        need_admin = False
        self._log_steps.append("")
        self._log_steps.append("--- 执行清理（并行） ---")
        self._log_steps.append("")

        jobs = [
            ("[1/8] 清理临时文件夹(Temp)...", self._clean_temp_folders, False),
            ("[2/8] 清理系统临时文件...", self._clean_win_temp, True),
            ("[3/8] 清理浏览器缓存...", self._clean_browser_cache, False),
            ("[4/8] 清理 Windows 更新缓存...", self._clean_win_update, True),
            ("[5/8] 清理预取与缩略图/图标缓存...", self._clean_prefetch_thumbs, True),
            ("[6/8] 清理错误转储与系统日志...", self._clean_dumps_logs, True),
            ("[7/8] 清理磁盘根目录散件与下载垃圾...", self._clean_drive_download, False),
            ("[8/8] 刷新 DNS 缓存...", self._flush_dns, False),
        ]
        with ThreadPoolExecutor(max_workers=4) as ex:
            futs = {}
            for label, fn, need in jobs:
                futs[ex.submit(fn)] = (label, need)
            for f in futs:
                label, need = futs[f]
                try:
                    r = f.result()
                    total_size += r.get('size', 0)
                    total_files += r.get('files', 0)
                    fd = r.get('failed', 0)
                    total_failed += fd
                    if need and fd > 0:
                        need_admin = True
                    tip = "%s 完成：%d 个文件，%s" % (
                        label, r.get('files', 0), self._fmt_size(r.get('size', 0)))
                    if fd:
                        tip += "（%d 项跳过）" % fd
                    self._log_steps.append(tip)
                except Exception as e:
                    self._log_steps.append("%s 出错：%s" % (label, e))

        self._log_steps.append("")
        self._log_steps.append("=" * 80)
        self._log_steps.append("[完成] 电脑安全优化 (退出码: 0)")
        self._log_steps.append("=" * 80)
        self._log_steps.append("")
        self._log_steps.append("已执行的安全操作:")
        for label, _, _ in jobs:
            self._log_steps.append("  - " + label.split("] ")[1].rstrip("..."))
        self._log_steps.append("")
        self._log_steps.append("本工具不会删除:")
        self._log_steps.append("  回收站、个人文件、Windows.old、系统还原点。")

        msg = ('清理完成: %d个文件, %s' % (total_files, self._fmt_size(total_size))
               if total_files > 0 else '无清理项')
        if total_failed:
            msg += '（%d 项跳过）' % total_failed
        return CleanResult(success=total_files > 0, message=msg, steps=self._log_steps,
                           total_size=total_size, total_files=total_files,
                           failed_files=total_failed, need_admin=need_admin)

    # ---- 各类型清理 ----
    def _clean_temp_folders(self):
        temp_dirs = [os.environ.get('TEMP', ''), os.environ.get('TMP', '')]
        total_size = total_files = total_failed = 0
        for d in dict.fromkeys(x for x in temp_dirs if x and os.path.isdir(x)):
            fl, sz = _walk_fast(d, max_files=MAX_FILES)
            n, s, fd = _fast_delete(fl)
            total_files += n
            total_size += s
            total_failed += fd
        return {'size': total_size, 'files': total_files, 'failed': total_failed}

    def _clean_win_temp(self):
        win_tmp = os.path.join(os.environ.get('WINDIR', 'C:/Windows'), 'Temp')
        fl, sz = _walk_fast(win_tmp, max_files=MAX_FILES)
        n, s, fd = _fast_delete(fl)
        return {'size': s, 'files': n, 'failed': fd}

    def _clean_browser_cache(self):
        local_app = os.environ.get('LOCALAPPDATA', '')
        app_data = os.environ.get('APPDATA', '')
        dirs = [
            os.path.join(local_app, 'Google/Chrome/User Data/Default/Cache'),
            os.path.join(local_app, 'Google/Chrome/User Data/Default/Code Cache'),
            os.path.join(local_app, 'Google/Chrome/User Data/Default/GPUCache'),
            os.path.join(local_app, 'Microsoft/Edge/User Data/Default/Cache'),
            os.path.join(local_app, 'Microsoft/Edge/User Data/Default/Code Cache'),
            os.path.join(local_app, 'Microsoft/Edge/User Data/Default/GPUCache'),
        ]
        ff_root = os.path.join(app_data, 'Mozilla/Firefox/Profiles') if app_data else ''
        if os.path.isdir(ff_root):
            try:
                for e in os.scandir(ff_root):
                    if e.is_dir():
                        dirs += [os.path.join(e.path, 'cache2'),
                                 os.path.join(e.path, 'thumbnails'),
                                 os.path.join(e.path, 'offlinecache')]
            except OSError:
                pass
        total_size = total_files = total_failed = 0
        for d in dirs:
            if os.path.isdir(d):
                fl, sz = _walk_fast(d, max_files=MAX_FILES)
                n, s, fd = _fast_delete(fl)
                total_files += n
                total_size += s
                total_failed += fd
        return {'size': total_size, 'files': total_files, 'failed': total_failed}

    def _clean_win_update(self):
        d = os.path.join(os.environ.get('WINDIR', 'C:/Windows'),
                         'SoftwareDistribution', 'Download')
        fl, sz = _walk_fast(d, max_files=MAX_FILES)
        n, s, fd = _fast_delete(fl)
        return {'size': s, 'files': n, 'failed': fd}

    def _clean_prefetch_thumbs(self):
        """清理预取 + 缩略图/图标缓存"""
        total_size = total_files = total_failed = 0
        prefetch = os.path.join(os.environ.get('WINDIR', 'C:/Windows'), 'Prefetch')
        fl, sz = _walk_fast(prefetch, ext_filter={'.pf'})
        n, s, fd = _fast_delete(fl)
        total_files += n
        total_size += s
        total_failed += fd
        local_app = os.environ.get('LOCALAPPDATA', '')
        targets = [os.path.join(local_app, 'IconCache.db')]
        ex = os.path.join(local_app, 'Microsoft/Windows/Explorer')
        if os.path.isdir(ex):
            try:
                for e in os.scandir(ex):
                    low = e.name.lower()
                    if (low.startswith('iconcache_') or low.startswith('thumbcache_')) and e.is_file():
                        targets.append(e.path)
            except OSError:
                pass
        for p in targets:
            try:
                sz = os.path.getsize(p)
                os.unlink(p)
                total_files += 1
                total_size += sz
            except Exception:
                total_failed += 1
        return {'size': total_size, 'files': total_files, 'failed': total_failed}

    def _clean_dumps_logs(self):
        """清理错误转储 + 系统日志"""
        total_size = total_files = total_failed = 0
        win = os.environ.get('WINDIR', 'C:/Windows')
        for d in (os.path.join(win, 'Minidump'),):
            if os.path.isdir(d):
                fl, sz = _walk_fast(d)
                n, s, fd = _fast_delete(fl)
                total_files += n
                total_size += s
                total_failed += fd
        mem = os.path.join(win, 'MEMORY.DMP')
        try:
            if os.path.isfile(mem):
                sz = os.path.getsize(mem)
                os.unlink(mem)
                total_files += 1
                total_size += sz
        except Exception:
            total_failed += 1
        logs = os.path.join(win, 'Logs')
        if os.path.isdir(logs):
            fl, sz = _walk_fast(logs, ext_filter={'.log', '.etl'}, max_depth=3)
            n, s, fd = _fast_delete(fl)
            total_files += n
            total_size += s
            total_failed += fd
        return {'size': total_size, 'files': total_files, 'failed': total_failed}

    def _clean_drive_download(self):
        """清理盘根散件 + 下载未完成文件"""
        total_size = total_files = total_failed = 0
        for drive in ['C:', 'D:', 'E:', 'F:']:
            root = drive + os.sep
            try:
                with os.scandir(root) as it:
                    for e in it:
                        try:
                            if e.is_file():
                                low = e.name.lower()
                                if low.endswith('.tmp') or low.startswith('~$') or low == 'thumbs.db':
                                    try:
                                        sz = e.stat().st_size
                                    except Exception:
                                        sz = 0
                                    try:
                                        os.unlink(e.path)
                                        total_files += 1
                                        total_size += sz
                                    except Exception:
                                        total_failed += 1
                        except OSError:
                            continue
            except OSError:
                continue
        dl = os.path.join(os.path.expanduser('~'), 'Downloads')
        if os.path.isdir(dl):
            try:
                with os.scandir(dl) as it:
                    for e in it:
                        try:
                            if e.is_file() and os.path.splitext(e.name)[1].lower() in (
                                    '.tmp', '.part', '.crdownload', '.download'):
                                sz = e.stat().st_size
                                os.unlink(e.path)
                                total_files += 1
                                total_size += sz
                        except Exception:
                            total_failed += 1
            except OSError:
                pass
        return {'size': total_size, 'files': total_files, 'failed': total_failed}

    def _flush_dns(self):
        try:
            subprocess.run(['cmd', '/c', 'ipconfig', '/flushdns'],
                           capture_output=True, timeout=10,
                           encoding='utf-8', errors='replace')
        except Exception:
            pass
        return {'size': 0, 'files': 0}

    def _fmt_size(self, b):
        b = float(b or 0)
        for u in ["B", "KB", "MB", "GB"]:
            if b < 1024:
                return "%.1f %s" % (b, u)
            b /= 1024
        return "%.1f TB" % b

    def get_smart_recommendations(self):
        targets = list(self._targets)
        recs = [t for t in targets if t.is_safe and t.size > 10 * 1024 * 1024]
        for t in recs:
            t.is_selected = True
        return recs

    def schedule_smart_clean(self):
        from config import settings
        scheduled = settings.toggle('scheduled')
        log.ok('定时清理已' + ('启用' if scheduled else '关闭'))
        return scheduled
