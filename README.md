# 番茄钟（Pomodoro）— Python / Windows / Tkinter(ttk)

一个可在 **Windows** 直接运行的番茄钟 GUI，具有完整的系统托盘支持，小巧、最小第三方依赖。

## 功能特性

- **工作 / 短休 / 长休** 自动切换
- **开始 / 暂停 / 重置 / 跳过** 控制
- **进度条**显示当前阶段进度
- **Windows Toast 通知**（右侧消息栏提醒）
- **系统托盘图标**（支持右键菜单和双击切换）
- **提示音**（可关闭）
- **跟随系统浅色/深色主题**（Windows 应用主题）
- **设置自动保存**到 `pomodoro_settings.json`

## 依赖

### 核心依赖
- **Python 3.10+**（建议）
- **windows-toasts**：用于显示 Windows Toast 通知
- **infi.systray**：用于系统托盘图标支持（Windows兼容性更好）

### 安装依赖
```bash
pip install -r requirements.txt
```

### 标准库依赖（无需安装）
项目主要使用 Python 标准库：
- `tkinter` - GUI 框架
- `time` - 时间处理
- `json` - 配置文件读写
- `os`, `shutil`, `sys` - 系统操作
- `dataclasses` - 数据类（Python 3.7+）
- `winsound`, `ctypes`, `winreg` - Windows 特定功能
- `threading` - 多线程支持

## 运行

确保已安装 Python（建议 3.10+）和依赖，在项目目录执行：

```bash
python main.py
```

## 系统托盘功能

应用启动后会在 Windows 任务栏系统托盘区域显示红色圆形图标：

### 托盘菜单功能
- **显示窗口**：显示主窗口
- **隐藏窗口**：隐藏窗口到托盘
- **开始/暂停**：开始或暂停当前计时
- **重置当前**：重置当前阶段计时
- **跳过当前**：跳过当前阶段
- **双击托盘图标**：切换窗口显示/隐藏
- **右键菜单**：显示完整功能菜单

### 窗口行为
- **点击关闭按钮**：隐藏窗口到托盘（不会退出应用）
- **最小化窗口**：自动隐藏到托盘
- **从托盘退出**：右键托盘图标选择退出功能

## 配置文件

首次运行后会在项目同目录生成/更新：

- `pomodoro_settings.json`

如果你运行的是打包后的 `Pomodoro.exe`，配置文件路径为：

- **优先**：`Pomodoro.exe` 同目录的 `pomodoro_settings.json`（便携）
- **否则**：`%APPDATA%\Pomodoro\pomodoro_settings.json`

字段说明：

- `work_minutes`: 工作分钟数（默认：25）
- `short_break_minutes`: 短休分钟数（默认：5）
- `long_break_minutes`: 长休分钟数（默认：15）
- `long_break_every`: 每完成 N 个工作番茄进入一次长休（默认：4）
- `auto_start_next`: 是否自动开始下一阶段（默认：True）
- `sound_on`: 是否开启提示音（默认：True）

## 代码结构

- `main.py`：程序入口（启动窗口）
- `pomodoro/app.py`：Tk/ttk GUI + 番茄钟逻辑（主类 `PomodoroApp`）
- `pomodoro/settings.py`：配置读写与默认路径
- `pomodoro/theme.py`：浅/深色主题与模式强调色
- `pomodoro/platform_windows.py`：Windows 相关能力（DPI、主题检测、提示音、Toast通知）
- `pomodoro/utils.py`：小工具函数
- `pomodoro/tray_icon.ico`：系统托盘图标文件

## 主题跟随说明

应用在启动时读取 Windows 的 "应用主题"（浅色/深色）并选择对应配色。

- 切换系统主题后：**重启应用即可生效**。

## 打包成 EXE（可选）

你可以用 PyInstaller 打包

```bash
pip install pyinstaller windows-toasts infi.systray
python -m PyInstaller --onefile --windowed --icon=pomodoro/tray_icon.ico --name="Pomodoro" --add-data="pomodoro;." main.py
```

生成的可执行文件在 `dist/` 目录。

### 常见问题

- **双击 EXE 没反应/被拦截**：Windows Defender/SmartScreen 可能拦截未签名程序，先选择"仍要运行"或加入信任。
- **打包很慢**：首次安装/下载依赖较慢；之后会快很多。
- **想要目录版（启动更快）**：把 `--onefile` 换成 `--onedir`。
- **系统托盘图标不显示**：确保打包时包含了 `tray_icon.ico` 文件，并正确设置了 `--add-data` 参数。

## 许可证

MIT License
