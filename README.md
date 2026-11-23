# Name Picker 🎲

> 一个带有宠物动画和插件系统的随机点名器桌面应用。

Name Picker 是一款用 Python 编写的轻量级桌面工具，专为课堂互动、抽奖、团队任务分配等场景设计。它不仅能快速随机抽取名字，还内置了可自定义的宠物动画和插件机制，让点名过程更有趣。

---

## ✨ 功能特性

- **随机点名** — 一键从名单中随机抽取，公平公正。
- **宠物动画** — 8 帧宠物行走动画（`pet_walk_*.png`），合成为带 60fps 交叉补间的 `pet_walk.svg`，走动更连贯。
- **宠物互动** — 左键抽名、中键摸头；右键可喂小鱼干、逗一逗、切换「自由散步 / 跟着鼠标 / 原地待机」。宠物空闲时会看向鼠标、悬停会打招呼、偶尔自言自语，被拖拽放下后也会有反应。
- **插件系统** — 通过 `plugins.py` 支持功能扩展，可根据需要灵活定制。
- **图形化设置** — 提供直观的设置对话框（`settings_dialog.py`），方便管理名单和偏好。
- **配置开箱即用** — `pet_config.json` / `dismiss_config.json` 缺失时自动生成默认配置，首次运行无需手动准备。桌宠的行走时间表与气泡提醒合并保存在同一个 `pet_config.json` 中。
- **开机自启** — 支持配置开机自动运行（`autostart.py`），随开随用。
- **自动更新** — 内置更新检查模块（`updater.py`），方便获取新版本。

---

## 🛠️ 技术栈

| 层级 | 技术 |
|------|------|
| 语言 | Python 3 |
| GUI 框架 | PyQt5（基于 `.ui` 文件构建界面） |
| 动画资源 | PNG 序列帧 + SVG 动画（`pet_walk.svg`，60fps 交叉补间） |
| 插件机制 | 自定义 `plugins.py` 模块 |

---

## 🚀 快速开始

### 环境要求

- Python 3.8 或更高版本
- 支持 Windows / macOS / Linux（桌面环境）

### 安装与运行

```bash
# 1. 克隆仓库
git clone https://github.com/zfscjch/name_picker.git
cd name_picker

# 2. 安装 GUI 依赖（二选一）
pip install -r requirements.txt

# 3. 进入客户端目录并启动
cd client
python -m name_picker
```

---

## ⚙️ 配置文件

首次启动（或配置文件被删除后重启）会自动生成下面两个配置，无需手动创建：

| 文件 | 作用 | 缺失时 |
|------|------|--------|
| `client/pet_config.json` | 桌宠行走时间表 + 气泡提醒 | 自动生成默认配置；若存在旧版 `pet_walk.json` / `pet_reminders.json`，会先合并迁移 |
| `client/dismiss_config.json` | 防拖堂开关、下课时间、演示进程 | 自动生成默认配置 |

`pet_config.json` 结构示例：

```json
{
  "walk": {
    "walk_speed": 5,
    "walk_time_ranges": [{"start": "07:55", "end": "08:00"}]
  },
  "reminders": [
    {"start": "08:00", "end": "09:20", "text": "早上好！", "duration": 6},
    {"time": "14:00", "text": "下午上课啦", "duration": 6}
  ]
}
```

- `walk.walk_time_ranges`：桌宠只在这些时间段内散步，`start` / `end` 为 `HH:MM`，支持跨零点（如 `22:00` ~ `01:00`）；空列表表示不按时间表散步。
- `walk.walk_speed`：每 50ms 移动的像素数（最小 1）。
- `reminders`：区间式用 `start` + `end`，定点式用 `time`；`duration` 为气泡显示秒数。
- 两个配置文件都属于本机配置（已加入 `.gitignore`），由程序自动维护，删掉后会重新生成。
- 打包后的程序把配置放在程序目录下（PyInstaller 6 的 `_internal` 子目录），升级时会保留用户配置。

---

## 📁 项目结构

```
name_picker/
├── client/
│   ├── name_picker/
│   │   ├── __init__.py
│   │   ├── __main__.py          # 程序入口
│   │   ├── autostart.py         # 开机自启逻辑
│   │   ├── config.py            # 配置管理
│   │   ├── dismiss.py           # 窗口关闭/隐藏处理
│   │   ├── main_window.py       # 主窗口逻辑
│   │   ├── pet_config.py        # 桌宠配置（pet_config.json 读写 / 旧文件迁移）
│   │   ├── plugins.py           # 插件系统
│   │   ├── settings_dialog.py   # 设置对话框
│   │   ├── updater.py           # 更新检查
│   │   ├── utils.py             # 通用工具函数
│   │   └── widgets/             # 自定义界面组件
│   ├── admin_window.ui          # Qt Designer 界面文件（管理员）
│   ├── dismiss_config.json      # 防拖堂配置（缺失时自动生成）
│   ├── main_window.ui           # Qt Designer 界面文件（主窗口）
│   ├── name_picker.py           # 客户端启动脚本
│   ├── pet.png                  # 宠物静态图
│   ├── pet_config.json          # 桌宠配置：行走时间表 + 气泡提醒（缺失时自动生成）
│   ├── pet_walk_*.png           # 宠物行走动画帧（8 帧原画，兜底用）
│   └── pet_walk.svg             # 60fps 行走动画（utils/build_pet_walk_svg.py 生成）
├── utils/
│   └── build_pet_walk_svg.py    # 把 8 帧原画合成为 pet_walk.svg
├── .gitignore
└── LICENSE
```

---

## 🧩 插件开发

项目内置了插件机制。你可以在 `client/name_picker/plugins.py` 中查看插件接口的定义方式，然后按照约定编写自己的插件模块。目前插件系统的具体 API 取决于该文件的实现细节。

---

## 🤝 贡献指南

欢迎提交 Issue 或 Pull Request。如果你发现了 Bug 或有功能建议，请在 [Issues](https://github.com/zfscjch/name_picker/issues) 中提出。

---

## 📄 许可证

本项目采用仓库根目录 `LICENSE` 文件中声明的许可证。