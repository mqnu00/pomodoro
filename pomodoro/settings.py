from __future__ import annotations

import json
import os
import shutil
import sys
from dataclasses import asdict, dataclass


def default_settings_path() -> str:
    """
    配置文件路径策略（解决 PyInstaller onefile 临时目录导致“配置丢失”）：
    - 优先：EXE 同目录（便携、可拷走）
    - 其次：%APPDATA%\\Pomodoro\\pomodoro_settings.json
    - 开发运行时：项目根目录 pomodoro_settings.json
    """

    filename = "pomodoro_settings.json"

    # PyInstaller: sys.frozen=True, sys.executable=...\\Pomodoro.exe
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        exe_path = os.path.join(exe_dir, filename)
        if _can_write_dir(exe_dir):
            _migrate_legacy_settings(exe_path)
            return exe_path

        appdata = os.environ.get("APPDATA") or os.path.expanduser("~")
        target_dir = os.path.join(appdata, "Pomodoro")
        os.makedirs(target_dir, exist_ok=True)
        target_path = os.path.join(target_dir, filename)
        _migrate_legacy_settings(target_path)
        return target_path

    # 开发态：项目根目录
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, filename)


def _can_write_dir(directory: str) -> bool:
    try:
        os.makedirs(directory, exist_ok=True)
        probe = os.path.join(directory, ".__pomodoro_write_test__")
        with open(probe, "w", encoding="utf-8") as f:
            f.write("ok")
        os.remove(probe)
        return True
    except Exception:
        return False


def _migrate_legacy_settings(target_path: str) -> None:
    """
    迁移旧配置：
    - 老版本在“当前工作目录”旁写入 pomodoro_settings.json
    - 打包后第一次启动时，把旧文件复制到新位置（如果新位置不存在）
    """
    try:
        if os.path.exists(target_path):
            return
        legacy = os.path.join(os.getcwd(), "pomodoro_settings.json")
        if os.path.exists(legacy):
            shutil.copy2(legacy, target_path)
    except Exception:
        pass


@dataclass
class Settings:
    work_minutes: int = 25
    short_break_minutes: int = 5
    long_break_minutes: int = 15
    long_break_every: int = 4  # 每完成 N 个工作番茄 -> 长休
    auto_start_next: bool = True
    sound_on: bool = True


def _clamp_settings(s: Settings) -> Settings:
    # 允许最小工作时间为0.05分钟（3秒），方便测试
    s.work_minutes = max(0.05, int(s.work_minutes))
    s.short_break_minutes = max(1, int(s.short_break_minutes))
    s.long_break_minutes = max(1, int(s.long_break_minutes))
    s.long_break_every = max(1, int(s.long_break_every))
    s.auto_start_next = bool(s.auto_start_next)
    s.sound_on = bool(s.sound_on)
    return s


def load_settings(path: str) -> Settings:
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return _clamp_settings(Settings(**raw))
    except Exception:
        return Settings()


def save_settings(path: str, s: Settings) -> None:
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(s), f, ensure_ascii=False, indent=2)
    except Exception:
        # 保存失败不影响使用
        pass


