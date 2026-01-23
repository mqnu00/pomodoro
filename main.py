def main() -> None:
    import tkinter as tk

    from pomodoro.app import PomodoroApp
    from pomodoro.platform_windows import try_set_dpi_awareness
    from pomodoro.settings import default_settings_path

    try_set_dpi_awareness()
    root = tk.Tk()
    PomodoroApp(root, settings_path=default_settings_path())
    root.mainloop()


if __name__ == "__main__":
    main()

