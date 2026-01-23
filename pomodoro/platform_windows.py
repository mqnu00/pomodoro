from __future__ import annotations

import sys
import time
import traceback


def detect_windows_dark_mode() -> bool:
    """
    检测 Windows 10+ 系统的“应用主题”是否为深色。
    True = 深色，False = 浅色；如果检测失败，默认使用深色。
    """
    if not sys.platform.startswith("win"):
        return True
    try:
        import winreg  # type: ignore[import-not-found]

        key_path = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:  # type: ignore[attr-defined]
            # AppsUseLightTheme: 1 = 浅色, 0 = 深色
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")  # type: ignore[attr-defined]
        return value == 0
    except Exception:
        return True


def try_set_dpi_awareness() -> None:
    # Windows 更清晰的 DPI 适配（尽力而为）
    if not sys.platform.startswith("win"):
        return
    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(1)  # SYSTEM_DPI_AWARE
    except Exception:
        pass


def play_done_sound(enabled: bool) -> None:
    if not enabled:
        return
    if not sys.platform.startswith("win"):
        return
    try:
        import winsound

        winsound.MessageBeep(winsound.MB_ICONASTERISK)
    except Exception:
        pass


def show_windows_toast(title: str, message: str, duration: int = 5, require_confirmation: bool = False) -> bool:
    """
    显示 Windows Toast 通知（Windows 10/11 右侧消息栏提醒）。
    尝试使用 windows-toasts 库，如果不可用则回退到传统MessageBox。
    
    参数:
        title: 通知标题
        message: 通知内容
        duration: 显示时长（秒），默认5秒
        require_confirmation: 是否需要用户确认（添加确认按钮）
        
    返回:
        bool: 用户是否确认（True表示用户点击了确认，False表示用户取消或关闭了通知）
              当require_confirmation=False时，返回True表示Toast显示成功
    """
    if not sys.platform.startswith("win"):
        return False
    
    # 首先尝试使用 windows-toasts 库显示真正的Toast通知
    try:
        import windows_toasts
        
        # 创建Toast通知
        # text_fields参数接受一个字符串列表，第一个是标题，第二个是内容
        toast = windows_toasts.Toast(text_fields=[title, message])
        
        # 设置显示时长（windows-toasts库使用ToastDuration枚举）
        # Short = 默认 (~7秒), Long = 约25秒
        if duration > 10:
            toast.duration = windows_toasts.ToastDuration.Long
        else:
            toast.duration = windows_toasts.ToastDuration.Short
        
        # 如果需要确认，添加确认按钮
        if require_confirmation:
            # 创建一个确认按钮
            confirm_button = windows_toasts.ToastButton("确认", "confirm")
            toast.AddAction(confirm_button)
            
            # 使用事件标志来跟踪用户响应
            user_confirmed = False
            event_received = False
            
            def on_activated(activated_args):
                nonlocal user_confirmed, event_received
                event_received = True
                # 检查用户是否点击了确认按钮
                if activated_args.arguments == 'confirm':
                    user_confirmed = True
                    print("✓ 用户在Toast中点击了确认按钮")
                else:
                    print(f"✗ 用户点击了其他按钮: {activated_args.arguments}")
            
            def on_dismissed(dismissed_args):
                nonlocal event_received
                if not event_received:
                    print("✗ 用户关闭了Toast通知")
                event_received = True
            
            # 设置回调函数
            toast.on_activated = on_activated
            toast.on_dismissed = on_dismissed
            
            # 使用InteractableWindowsToaster来支持交互式按钮
            notifier = windows_toasts.InteractableWindowsToaster("Pomodoro")
            
            print(f"✓ 已显示交互式Windows Toast通知: {title} - {message}")
            notifier.show_toast(toast)
            
            # 等待一段时间让用户交互（最大等待时间）
            max_wait_time = duration if duration > 0 else 10
            wait_start = time.time()
            while not event_received and (time.time() - wait_start) < max_wait_time:
                time.sleep(0.1)
            
            return user_confirmed
        else:
            # 不需要确认，使用普通的WindowsToaster
            notifier = windows_toasts.WindowsToaster("Pomodoro")
            notifier.show_toast(toast)
            
            print(f"✓ 已显示Windows Toast通知: {title} - {message}")
            return True
        
    except ImportError:
        # windows-toasts模块不可用，提示用户安装
        print("⚠️ 无法显示Windows Toast通知：缺少windows-toasts模块")
        print("   要启用真正的Toast通知，请运行: pip install windows-toasts")
        print("   将回退到传统MessageBox对话框")
    except Exception as e:
        print(f"⚠️ Toast通知失败: {e}")
        print("   将回退到传统MessageBox对话框")
    
    # 回退方案：使用传统MessageBox
    try:
        import ctypes
        
        # 使用MB_TOPMOST | MB_SETFOREGROUND | MB_ICONINFORMATION标志
        MB_OK = 0x00000000
        MB_ICONINFORMATION = 0x00000040
        MB_SETFOREGROUND = 0x00010000
        MB_TOPMOST = 0x00040000
        
        flags = MB_OK | MB_ICONINFORMATION | MB_SETFOREGROUND | MB_TOPMOST
        
        # 如果需要确认，使用MB_OKCANCEL而不是MB_OK
        if require_confirmation:
            MB_OKCANCEL = 0x00000001
            flags = MB_OKCANCEL | MB_ICONINFORMATION | MB_SETFOREGROUND | MB_TOPMOST
        
        # 调用MessageBoxW显示通知
        result = ctypes.windll.user32.MessageBoxW(
            0,  # 没有父窗口
            message,
            title,
            flags
        )
        
        print(f"✓ 已显示MessageBox通知: {title} - {message}")
        
        # 如果需要确认，检查用户是否点击了确认
        if require_confirmation:
            # IDOK = 1, IDCANCEL = 2
            return result == 1  # 返回True表示用户点击了确认
        
        return False  # 返回False表示使用了回退方案
        
    except Exception as e:
        print(f"✗ 所有通知方法都失败: {e}")
        traceback.print_exc()
        return False


if __name__ == "__main__":
    # 测试显示Toast通知
    success = show_windows_toast("测试通知", "这是一个来自Pomodoro的测试通知。", duration=5)
    print("Toast通知显示成功：" if success else "Toast通知显示失败。")
