# 优化工具箱 v6.16（最终版）

> PC + 手机端统一系统优化工具 · 全 Canvas 原生皮肤 · 背景图处处可见

一款纯 `tkinter` + `Canvas` 绘制的 Windows 系统优化工具箱，同时管理**电脑**与 **Android 手机**（ADB 直连）：
统一水彩二次元视觉（蓝发少女 + 鲸鱼），从桌面图标、窗口图标到界面控件全部原生绘制，**不遮挡背景图**。

---

## ✨ 功能一览

| 功能 | 说明 |
|---|---|
| ⚡ 一键优化 | 网络 + 性能一键处理 |
| 🌐 网络优化 | DNS 切换 / 场景模式（下载/游戏/均衡）/ 网络参数实时修改 |
| 🧹 智能清理 | 系统垃圾 / 浏览器缓存 / 重复文件 / 大文件分析 / **手机垃圾扫描** |
| 📊 性能监控 | CPU / 内存 / 磁盘 / 电池实时采样 + 综合评分 + 人性化问题与建议 |
| 📱 应用卸载 | 电脑应用卸载 + 手机（ADB）应用卸载，中文应用名自动解析 |
| 🔌 手机连接 | ADB 直连，自动检测手机在线状态，切换手机/电脑模式 |

### 手机端能力（ADB）
- 真机自动连接与状态检测（`adb connect` + 在线检查）
- 第三方应用枚举与**中文名解析**（纯 Python 解析 APK 的 AXML/ARSC，不依赖 dumpsys）
- 手机垃圾扫描：`/sdcard/Android/data/*/cache`、ADB 临时文件、相册缩略图等

---

## 🎨 界面特性

- **全 Canvas 原生绘制**：无 Toplevel 贴图、无透明色 hack，控件区域背景图依然可见
- **背景图**：`assets/bg.png`（DSH.jpeg 蓝发少女水彩风，全窗口四区拼接可见）
- **统一图标体系**：桌面图标（蓝发少女）、窗口图标（iconphoto PNG）、界面图标（水彩鲸鱼）
- **可自由缩放**：窗口 1280×800 默认，最小 1024×660，各面板可拖拽调整

---

## 🚀 运行

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 运行（需要 Python 3.10+）
python main.py
```

> 手机功能需要 `tools/platform-tools/` 下的官方 `adb.exe`（Google Platform Tools，仓库未包含，请自行放入）。

---

## 📦 打包发布

使用 PyInstaller 6.x：

```powershell
# 目录版
python -m PyInstaller -D -w -y --name "优化工具箱v6.1" --icon icon.ico `
  --add-data "assets;assets" --add-data "tools;tools" `
  --distpath dist --workpath build main.py

# 单文件版
python -m PyInstaller -F -w -y --name "优化工具箱v6.1" --icon icon.ico `
  --add-data "assets;assets" --add-data "tools;tools" `
  --distpath dist --workpath build main.py
```

---

## 📁 目录结构

```
优化工具箱/
├── main.py                 # 入口：主窗口 / 四区 Canvas / 顶栏 / 终端日志 / 打包时间
├── config.py               # 配置：路径、阈值、字体、设置持久化
├── core/                   # 业务核心
│   ├── network_optimizer.py  # 网络优化（DNS/场景/参数）
│   ├── smart_cleaner.py      # 垃圾清理（电脑+手机）
│   ├── performance_monitor.py# 性能监控（采样/评分/建议）
│   └── app_manager.py        # 应用卸载（电脑+手机）
├── ui/
│   ├── background.py       # 背景图加载（PIL → PhotoImage，缓存与回退）
│   ├── theme.py            # Canvas 原生控件（卡片/按钮/文字/透明命中区）
│   ├── styles.py
│   ├── widgets/            # 导航面板 / 状态卡 / 操作按钮
│   └── pages/              # 首页/网络/清理/监控/卸载/关于
├── utils/
│   ├── adb_helper.py       # ADB 封装（连接/扫描/卸载/手机垃圾）
│   └── apk_label.py        # APK 中文名解析（纯 Python AXML+ARSC）
├── assets/                 # 背景图 / 桌面图标 / 界面图标
├── tools/platform-tools/   # adb.exe（自备，未入仓库）
├── icon.ico                # exe 桌面图标（多尺寸）
└── 优化工具箱v6.1.spec       # PyInstaller spec
```

---

## 🗂️ 版本记录

| 版本 | 说明 |
|---|---|
| v6.3 | 手机/电脑模式全局化（顶栏同步） |
| v6.4 | 手机垃圾扫描（ADB） |
| v6.5 | 按钮透明命中区（整块可点） |
| v6.6 | 性能问题/建议人性化 |
| v6.7 | 监控页真实采样（不点按钮也能看） |
| v6.8–v6.11 | 设备卡防重叠两行布局 / 一键优化透明化 / 发光指示灯 |
| v6.12–v6.13 | 桌面图标（蓝发少女水彩）+ 界面鲸鱼图标 |
| v6.14–v6.15 | 图标 PIL 加载加固 / 窗口图标（任务栏） |
| **v6.16** | **最终版：全图标体系统一 + 完整整理** |

完整历史打包备份见 `优化工具箱_全版本备份_20260909.zip`（86MB，含所有版本 exe 与源码）。

---

## 📄 License

MIT License — 见 [LICENSE](LICENSE)。
