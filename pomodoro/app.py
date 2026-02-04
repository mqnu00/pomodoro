from __future__ import annotations

import time
import tkinter as tk
from tkinter import messagebox, ttk
import threading
import os
from infi.systray import SysTrayIcon

from .platform_windows import detect_windows_dark_mode, play_done_sound, show_windows_toast
from .settings import Settings, load_settings, save_settings
from .theme import accent_for_mode, theme_for_system
from .utils import format_mmss, safe_int


APP_TITLE = "番茄钟 (Pomodoro)"


class PomodoroApp:
    def __init__(self, root: tk.Tk, settings_path: str) -> None:
        self.root = root
        self.settings_path = settings_path
        self.root.title(APP_TITLE)
        self.root.minsize(460, 390)

        self.settings: Settings = load_settings(self.settings_path)

        # 运行状态
        self.mode = "work"  # work / short_break / long_break
        self.is_running = False
        self.after_id: str | None = None
        self.remaining_seconds = self.settings.work_minutes * 60
        self.total_seconds = self.remaining_seconds
        self.completed_work_sessions = 0
        self.skipped_work_sessions = 0  # 跳过的番茄钟计数
        self.last_tick_monotonic: float | None = None
        self._elapsed_carry = 0.0  # 累积不足 1 秒的时间
        self.is_window_visible = True  # 窗口可见状态

        # 跟随系统主题
        self._is_dark = detect_windows_dark_mode()
        self._theme = theme_for_system(self._is_dark)
        self._accent = accent_for_mode(self.mode)

        self._init_style()
        self._build_ui()
        self._refresh_ui()

        # 系统托盘相关
        self.tray_icon = None
        self.tray_thread = None
        
        # 设置窗口最小化事件处理
        self.root.bind("<Unmap>", self._on_window_minimize)
        
        # 延迟设置窗口关闭协议，避免在初始化时被触发
        self.root.after(200, self._setup_window_protocol)
        
        # 延迟创建托盘图标，确保窗口完全显示后再创建
        self.root.after(500, self._create_tray_icon)

    def _init_style(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except Exception:
            pass

        self.root.configure(bg=self._theme.bg)

        style.configure("TFrame", background=self._theme.bg)
        style.configure("Panel.TFrame", background=self._theme.panel)
        style.configure("TLabel", background=self._theme.bg, foreground=self._theme.fg, font=("Segoe UI", 11))
        style.configure("Muted.TLabel", background=self._theme.bg, foreground=self._theme.muted, font=("Segoe UI", 10))
        style.configure("Title.TLabel", background=self._theme.bg, foreground=self._theme.fg, font=("Segoe UI", 16, "bold"))
        style.configure("Timer.TLabel", background=self._theme.bg, foreground=self._theme.fg, font=("Consolas", 52, "bold"))

        style.configure("Accent.TButton", padding=(14, 10), font=("Segoe UI", 11, "bold"))
        style.configure("TButton", padding=(14, 10), font=("Segoe UI", 11))
        style.configure("TEntry", padding=(8, 6))

        style.configure(
            "Pomodoro.Horizontal.TProgressbar",
            troughcolor=self._theme.panel,
            background=self._accent,
            thickness=10,
        )

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=18)
        outer.pack(fill="both", expand=True)

        top = ttk.Frame(outer)
        top.pack(fill="x")

        self.mode_label = ttk.Label(top, text="", style="Title.TLabel")
        self.mode_label.pack(side="left")

        self.stats_label = ttk.Label(top, text="", style="Muted.TLabel")
        self.stats_label.pack(side="right")

        self.time_label = ttk.Label(outer, text="25:00", style="Timer.TLabel")
        self.time_label.pack(pady=(18, 8))

        self.progress = ttk.Progressbar(
            outer,
            style="Pomodoro.Horizontal.TProgressbar",
            orient="horizontal",
            mode="determinate",
            maximum=1000,
            value=0,
        )
        self.progress.pack(fill="x", padx=2, pady=(0, 14))

        btns = ttk.Frame(outer)
        btns.pack(pady=(0, 14))

        self.start_pause_btn = ttk.Button(btns, text="开始", style="Accent.TButton", command=self.toggle_start_pause)
        self.start_pause_btn.grid(row=0, column=0, padx=6, ipadx=6)

        self.reset_btn = ttk.Button(btns, text="重置", command=self.reset_current)
        self.reset_btn.grid(row=0, column=1, padx=6, ipadx=6)

        self.skip_btn = ttk.Button(btns, text="跳过", command=self.skip_session)
        self.skip_btn.grid(row=0, column=2, padx=6, ipadx=6)

        box = ttk.Frame(outer, style="Panel.TFrame", padding=14)
        box.pack(fill="x")
        ttk.Label(box, text="设置", style="Title.TLabel").pack(anchor="w", pady=(0, 10))

        row1 = ttk.Frame(box, style="Panel.TFrame")
        row1.pack(fill="x")

        ttk.Label(row1, text="工作(分钟)", background=self._theme.panel).grid(row=0, column=0, sticky="w")
        ttk.Label(row1, text="短休(分钟)", background=self._theme.panel).grid(row=0, column=2, sticky="w", padx=(14, 0))
        ttk.Label(row1, text="长休(分钟)", background=self._theme.panel).grid(row=0, column=4, sticky="w", padx=(14, 0))

        self.work_var = tk.StringVar(value=str(self.settings.work_minutes))
        self.short_var = tk.StringVar(value=str(self.settings.short_break_minutes))
        self.long_var = tk.StringVar(value=str(self.settings.long_break_minutes))

        self.work_entry = ttk.Entry(row1, width=6, textvariable=self.work_var)
        self.short_entry = ttk.Entry(row1, width=6, textvariable=self.short_var)
        self.long_entry = ttk.Entry(row1, width=6, textvariable=self.long_var)
        self.work_entry.grid(row=0, column=1, sticky="w", padx=(8, 0))
        self.short_entry.grid(row=0, column=3, sticky="w", padx=(8, 0))
        self.long_entry.grid(row=0, column=5, sticky="w", padx=(8, 0))

        row2 = ttk.Frame(box, style="Panel.TFrame")
        row2.pack(fill="x", pady=(12, 0))

        ttk.Label(row2, text="每完成", background=self._theme.panel).grid(row=0, column=0, sticky="w")
        self.every_var = tk.StringVar(value=str(self.settings.long_break_every))
        self.every_entry = ttk.Entry(row2, width=4, textvariable=self.every_var)
        self.every_entry.grid(row=0, column=1, sticky="w", padx=(8, 8))
        ttk.Label(row2, text="个工作番茄 -> 长休", background=self._theme.panel).grid(row=0, column=2, sticky="w")

        self.auto_var = tk.BooleanVar(value=self.settings.auto_start_next)
        self.sound_var = tk.BooleanVar(value=self.settings.sound_on)
        self.auto_cb = ttk.Checkbutton(row2, text="自动开始下一段", variable=self.auto_var, command=self.apply_settings)
        self.sound_cb = ttk.Checkbutton(row2, text="提示音", variable=self.sound_var, command=self.apply_settings)
        self.auto_cb.grid(row=1, column=0, columnspan=2, sticky="w", pady=(10, 0))
        self.sound_cb.grid(row=1, column=2, sticky="w", pady=(10, 0))

        row3 = ttk.Frame(box, style="Panel.TFrame")
        row3.pack(fill="x", pady=(12, 0))
        self.apply_btn = ttk.Button(row3, text="应用设置", command=self.apply_settings)
        self.apply_btn.pack(side="left")

        ttk.Label(box, text="提示：设置会自动保存到同目录的 pomodoro_settings.json", style="Muted.TLabel").pack(
            anchor="w", pady=(10, 0)
        )

    def _mode_name(self) -> str:
        return {"work": "工作", "short_break": "短休", "long_break": "长休"}.get(self.mode, self.mode)

    def _mode_default_seconds(self, mode: str) -> int:
        if mode == "work":
            return self.settings.work_minutes * 60
        if mode == "short_break":
            return self.settings.short_break_minutes * 60
        return self.settings.long_break_minutes * 60

    def _create_tooltip(self, widget, text):
        """为widget创建鼠标悬浮提示"""
        # 检查是否已经绑定了tooltip事件
        if hasattr(widget, '_tooltip_bound') and widget._tooltip_bound:
            return
            
        def show_tooltip(event):
            # 如果已经有tooltip，先销毁
            if hasattr(widget, 'tooltip') and widget.tooltip:
                widget.tooltip.destroy()
            
            # 创建tooltip窗口
            tooltip = tk.Toplevel(self.root)
            tooltip.wm_overrideredirect(True)  # 移除窗口装饰
            tooltip.wm_geometry(f"+{event.x_root+10}+{event.y_root+10}")
            
            # 设置tooltip样式
            label = tk.Label(tooltip, text=text, justify="left",
                           background="#ffffe0", relief="solid", borderwidth=1,
                           font=("Segoe UI", 9))
            label.pack()
            
            # 保存tooltip引用以便稍后销毁
            widget.tooltip = tooltip
            
        def hide_tooltip(event):
            if hasattr(widget, 'tooltip') and widget.tooltip:
                widget.tooltip.destroy()
                widget.tooltip = None
        
        # 绑定事件
        widget.bind("<Enter>", show_tooltip)
        widget.bind("<Leave>", hide_tooltip)
        
        # 标记为已绑定
        widget._tooltip_bound = True

    def _refresh_ui(self) -> None:
        # 模式颜色 + 进度条配色
        self._accent = accent_for_mode(self.mode)
        try:
            ttk.Style(self.root).configure("Pomodoro.Horizontal.TProgressbar", background=self._accent)
        except Exception:
            pass

        self.mode_label.config(text=f"当前：{self._mode_name()}")
        self.time_label.config(text=format_mmss(self.remaining_seconds))
        
        # 更新统计标签文本
        total_work_sessions = self.completed_work_sessions + self.skipped_work_sessions
        stats_text = f"工作番茄：{self.completed_work_sessions}完成，{self.skipped_work_sessions}跳过"
        self.stats_label.config(text=stats_text)
        
        # 设置Tooltip（鼠标悬浮提示）
        tooltip_text = (
            f"番茄钟统计详情：\n"
            f"• 完成的工作番茄：{self.completed_work_sessions}\n"
            f"• 跳过的工作番茄：{self.skipped_work_sessions}\n"
            f"• 总工作番茄数：{total_work_sessions}\n"
            f"• 长休间隔：每{self.settings.long_break_every}个工作番茄\n"
            f"• 下次长休在：第{(total_work_sessions // self.settings.long_break_every + 1) * self.settings.long_break_every}个番茄钟"
        )
        self._create_tooltip(self.stats_label, tooltip_text)

        self.start_pause_btn.config(text="暂停" if self.is_running else "开始")
        state = "disabled" if self.is_running else "normal"
        for w in (self.work_entry, self.short_entry, self.long_entry, self.every_entry):
            w.config(state=state)

        total = max(1, int(self.total_seconds))
        done = max(0, min(total, total - int(self.remaining_seconds)))
        self.progress.config(value=int(done * 1000 / total))

        self.root.title(f"{format_mmss(self.remaining_seconds)} - {APP_TITLE}")
        
        # 更新托盘图标悬停文本
        self._update_tray_hover_text()

    def toggle_start_pause(self) -> None:
        if self.is_running:
            self.pause()
        else:
            self.start()

    def start(self) -> None:
        if self.is_running:
            return
        self.is_running = True
        self.last_tick_monotonic = time.monotonic()
        self._elapsed_carry = 0.0
        self._schedule_tick()
        self._refresh_ui()

    def pause(self) -> None:
        if not self.is_running:
            return
        self.is_running = False
        self.last_tick_monotonic = None
        self._elapsed_carry = 0.0
        if self.after_id is not None:
            try:
                self.root.after_cancel(self.after_id)
            except Exception:
                pass
        self.after_id = None
        self._refresh_ui()

    def reset_current(self) -> None:
        self.pause()
        self.remaining_seconds = self._mode_default_seconds(self.mode)
        self.total_seconds = self.remaining_seconds
        self._refresh_ui()

    def skip_session(self) -> None:
        self.pause()
        self._finish_session(user_skipped=True)

    # 双击触发的函数 
    def _toggle_window_by_double_click(self, systray): 
        if self.is_window_visible: 
            self._hide_to_tray() 
        else: 
            self._show_window()

    def _schedule_tick(self) -> None:
        self.after_id = self.root.after(200, self._tick)

    def _tick(self) -> None:
        if not self.is_running:
            return
        now = time.monotonic()
        last = self.last_tick_monotonic or now
        elapsed = now - last
        self.last_tick_monotonic = now

        self._elapsed_carry += elapsed
        dec = int(self._elapsed_carry)
        if dec >= 1:
            self._elapsed_carry -= dec
            self.remaining_seconds -= dec

        if self.remaining_seconds <= 0:
            self.remaining_seconds = 0
            self._refresh_ui()
            self.pause()
            self._finish_session(user_skipped=False)
            return

        self._refresh_ui()
        self._schedule_tick()

    def _next_mode(self) -> str:
        if self.mode == "work":
            # 计算总的工作番茄钟（完成 + 跳过）
            total_work_sessions = self.completed_work_sessions + self.skipped_work_sessions
            # 检查是否达到长休条件
            if total_work_sessions % self.settings.long_break_every == 0:
                return "long_break"
            return "short_break"
        return "work"

    def _finish_session(self, user_skipped: bool) -> None:
        prev_mode = self.mode
        if prev_mode == "work":
            if user_skipped:
                self.skipped_work_sessions += 1
            else:
                self.completed_work_sessions += 1

        next_mode = self._next_mode()
        self.mode = next_mode
        self.remaining_seconds = self._mode_default_seconds(next_mode)
        self.total_seconds = self.remaining_seconds

        user_confirmed = True  # 默认用户已确认
        
        if not user_skipped:
            play_done_sound(self.settings.sound_on)
            
            # 根据设置决定通知方式
            if self.settings.auto_start_next:
                # 如果需要自动开始下一段，使用交互式Toast通知进行确认
                # 这样用户可以在Toast中确认，应用页面就不需要再等待确认了
                try:
                    # 显示需要确认的Toast通知
                    user_confirmed = show_windows_toast(
                        APP_TITLE, 
                        f"{'工作' if prev_mode == 'work' else '休息'}结束，进入：{self._mode_name()}\n\n是否开始下一阶段？",
                        require_confirmation=True
                    )
                    
                    if user_confirmed:
                        print(f"✓ 用户在Toast中确认了，将开始下一阶段: {self._mode_name()}")
                    else:
                        print(f"✗ 用户在Toast中取消了，不会自动开始下一阶段")
                        
                except Exception as e:
                    print(f"⚠️ Toast通知失败，回退到MessageBox: {e}")
                    # Toast 通知失败，回退到传统 messagebox
                    result = messagebox.askyesno(
                        APP_TITLE, 
                        f"{'工作' if prev_mode == 'work' else '休息'}结束，进入：{self._mode_name()}\n\n是否开始下一阶段？"
                    )
                    user_confirmed = result
            else:
                # 如果不需要自动开始，使用Toast通知（不需要确认）
                try:
                    show_windows_toast(
                        APP_TITLE, 
                        f"{'工作' if prev_mode == 'work' else '休息'}结束，进入：{self._mode_name()}",
                        require_confirmation=False
                    )
                except Exception:
                    # Toast 通知失败，回退到传统 messagebox
                    messagebox.showinfo(APP_TITLE, f"{'工作' if prev_mode == 'work' else '休息'}结束，进入：{self._mode_name()}")

        self._refresh_ui()

        # 只有当用户确认了，并且设置了自动开始下一段时，才自动开始
        if self.settings.auto_start_next and not user_skipped and user_confirmed:
            self.start()

    def apply_settings(self) -> None:
        work = max(1, safe_int(self.work_var.get().strip(), self.settings.work_minutes))
        short = max(1, safe_int(self.short_var.get().strip(), self.settings.short_break_minutes))
        long_ = max(1, safe_int(self.long_var.get().strip(), self.settings.long_break_minutes))
        every = max(1, safe_int(self.every_var.get().strip(), self.settings.long_break_every))

        self.settings.work_minutes = work
        self.settings.short_break_minutes = short
        self.settings.long_break_minutes = long_
        self.settings.long_break_every = every
        self.settings.auto_start_next = bool(self.auto_var.get())
        self.settings.sound_on = bool(self.sound_var.get())
        save_settings(self.settings_path, self.settings)

        if not self.is_running:
            self.remaining_seconds = self._mode_default_seconds(self.mode)
            self.total_seconds = self.remaining_seconds
        self._refresh_ui()

    def _create_tray_icon(self) -> None:
        """创建系统托盘图标（使用infi.systray）"""
        try:

            # 直接引用已有的图标文件
            def resource_path(relative_path):
                import sys, os
                if hasattr(sys, "_MEIPASS"):
                    return os.path.join(sys._MEIPASS, relative_path)
                return os.path.join(os.path.dirname(__file__), relative_path)

            icon_path = resource_path("tray_icon.ico")
            print("调试：托盘图标路径：", icon_path)

            
            # 创建托盘菜单选项
            menu_options = (
                ("显示窗口", None, lambda systray: self._show_window()),
                ("隐藏窗口", None, lambda systray: self._hide_to_tray()),
                ("开始/暂停", None, lambda systray: self.toggle_start_pause()),
                ("重置当前", None, lambda systray: self.reset_current()),
                ("跳过当前", None, lambda systray: self.skip_session()),
                (None, None, self._toggle_window_by_double_click),
            )
            
            # 创建系统托盘图标
            self.tray_icon = SysTrayIcon(
                icon_path,           # 图标文件路径
                APP_TITLE,           # 悬停文本
                menu_options,        # 菜单选项
                on_quit=lambda systray: self._quit_app(),  # 退出回调
                default_menu_index=5  # 默认菜单项索引
            )
            
            print("✓ 系统托盘图标对象已创建")
            
            # 延迟启动托盘图标，确保窗口完全显示
            self.root.after(1000, self._start_tray_icon)
            
        except Exception as e:
            print(f"✗ 创建系统托盘图标失败: {e}")
            import traceback
            traceback.print_exc()
            self.tray_icon = None
    
    def _start_tray_icon(self) -> None:
        """启动系统托盘图标"""
        if self.tray_icon is not None:
            print("调试：启动托盘图标...")
            # infi.systray在单独的线程中运行
            self.tray_thread = threading.Thread(target=self.tray_icon.start, daemon=True)
            self.tray_thread.start()
            print("✓ 系统托盘图标已启动")
    
    def _update_tray_hover_text(self) -> None:
        """更新托盘图标悬停文本"""
        # 检查tray_icon是否已经初始化
        if hasattr(self, 'tray_icon') and self.tray_icon is not None:
            try:
                # 构建悬停文本：显示剩余时间和状态
                mode_name = self._mode_name()
                time_text = format_mmss(self.remaining_seconds)
                status_text = "运行中" if self.is_running else "已暂停"
                
                hover_text = f"{APP_TITLE}\n{time_text} - {mode_name} ({status_text})"
                
                # 更新托盘图标悬停文本
                self.tray_icon.update(hover_text=hover_text)
            except Exception as e:
                # 忽略更新失败的错误，避免影响主程序运行
                pass
    
    def _show_window(self, icon=None, item=None) -> None:
        """显示主窗口"""
        self.root.after(0, self._show_window_main)
        self.is_window_visible = True
    
    def _show_window_main(self) -> None:
        """在主线程中显示窗口"""
        self.root.deiconify()  # 显示窗口
        self.root.lift()       # 置顶
        self.root.focus_force() # 获取焦点
        
        # 如果窗口被最小化了，恢复它
        if self.root.state() == 'iconic':
            self.root.state('normal')
    
    def _hide_to_tray(self) -> None:
        """隐藏窗口到系统托盘"""
        self.root.withdraw()  # 隐藏窗口
        self.is_window_visible = False
        print("✓ 窗口已隐藏到系统托盘")
    
    def _setup_window_protocol(self) -> None:
        """设置窗口关闭协议 - 隐藏到系统托盘而不是退出"""
        print("设置窗口关闭协议")
        # 使用lambda包装，避免直接调用
        self.root.protocol("WM_DELETE_WINDOW", lambda: self._on_window_close())
    
    def _on_window_minimize(self, event=None) -> None:
        """窗口最小化事件处理 - 隐藏到系统托盘"""
        # 检查是否真的是最小化事件，而不是其他Unmap事件
        if event and hasattr(event, 'type') and event.type == 'Unmap':
            print("窗口最小化，隐藏到系统托盘")
            self._hide_to_tray()
    
    def _on_window_close(self) -> None:
        """窗口关闭事件处理 - 隐藏到系统托盘"""
        # 只有在窗口可见时才隐藏到托盘
        if self.root.state() != 'withdrawn':
            print("窗口关闭按钮被点击，隐藏到系统托盘")
            self._hide_to_tray()
        else:
            print("窗口已经隐藏，忽略关闭事件")
    
    def _quit_app(self, systray=None) -> None:
        """退出应用程序"""
        print("正在退出应用程序...")
        
        # 保存设置
        self.apply_settings()
        
        # 在主线程中销毁窗口
        self.root.after(0, self._destroy_app)
    
    def _destroy_app(self) -> None:
        """销毁应用程序"""
        # 停止托盘图标（在主线程中调用）
        if self.tray_icon is not None:
            try:
                # 使用after延迟调用shutdown，确保不在托盘图标线程中
                self.root.after(100, self.tray_icon.shutdown)
            except Exception as e:
                print(f"停止托盘图标时出错: {e}")
        
        # 销毁主窗口
        self.root.destroy()
