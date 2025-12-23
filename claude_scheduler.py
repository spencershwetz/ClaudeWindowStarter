import rumps
import subprocess
import threading
from datetime import datetime

class ClaudeScheduler(rumps.App):
    def __init__(self):
        super().__init__("⏰ Claude", icon=None, quit_button="Quit")
        self.scheduled_time = None
        self.timer_thread = None
        self.cancel_event = threading.Event()
        self.caffeinate_process = None

        # Create menu items
        self.schedule_button = rumps.MenuItem("Schedule Claude", callback=self.set_time)
        self.cancel_button = rumps.MenuItem("Cancel Schedule", callback=self.cancel)

        # Only show schedule button initially (no cancel until something is scheduled)
        self.menu = [self.schedule_button]

    def start_caffeinate(self):
        # Prevent Mac from sleeping while schedule is active
        if self.caffeinate_process is None:
            self.caffeinate_process = subprocess.Popen(["caffeinate", "-i"])

    def stop_caffeinate(self):
        if self.caffeinate_process:
            self.caffeinate_process.terminate()
            self.caffeinate_process = None

    def set_time(self, _):
        # Default to next hour + 1 minute
        now = datetime.now()
        next_hour = (now.hour + 1) % 24
        default_time = f"{next_hour:02d}:01"

        window = rumps.Window(
            message='Enter time (HH:MM in 24hr format):',
            title='Schedule Claude',
            default_text=default_time,
            dimensions=(200, 24)
        )
        response = window.run()
        if response.clicked:
            time_input = response.text.strip()

            # Auto-insert colon if user just typed 4 digits (e.g., "1701" -> "17:01")
            if len(time_input) == 4 and time_input.isdigit():
                time_input = f"{time_input[:2]}:{time_input[2:]}"

            self.scheduled_time = time_input
            try:
                # Validate time format
                datetime.strptime(self.scheduled_time, "%H:%M")
                self.title = f"⏰ {self.scheduled_time}"
                self.cancel_event.clear()
                self.start_caffeinate()
                self.start_scheduler()

                # Show cancel button
                if "Cancel Schedule" not in self.menu:
                    self.menu.insert_after("Schedule Claude", self.cancel_button)

            except ValueError:
                rumps.notification("Claude Scheduler", "Error", "Invalid time format. Use HH:MM")

    def start_scheduler(self):
        def run_at_time():
            target = datetime.strptime(self.scheduled_time, "%H:%M").replace(
                year=datetime.now().year,
                month=datetime.now().month,
                day=datetime.now().day
            )
            wait_seconds = (target - datetime.now()).total_seconds()

            if wait_seconds <= 0:
                rumps.notification("Claude Scheduler", "Error", "Time has already passed today")
                self.title = "⏰ Claude"
                self.hide_cancel()
                self.stop_caffeinate()
                return

            # Wait in small increments so we can cancel
            while wait_seconds > 0:
                if self.cancel_event.is_set():
                    return
                sleep_time = min(1, wait_seconds)
                threading.Event().wait(sleep_time)
                wait_seconds -= sleep_time

            if self.cancel_event.is_set():
                return

            # Open Terminal and start claude in tmux
            cmd = 'tmux kill-session -t claude_session 2>/dev/null; tmux new-session -d -s claude_session \\"claude\\" && tmux attach -t claude_session'

            script = f'''
            tell application "Terminal"
                activate
                do script "{cmd}"
            end tell
            '''
            subprocess.run(["osascript", "-e", script])

            rumps.notification("Claude Scheduler", "Running!", "Claude started")
            self.title = "⏰ Claude"
            self.scheduled_time = None
            self.hide_cancel()
            self.stop_caffeinate()

            # Wait 30 seconds then send "hi" (in a separate thread so we don't block)
            def send_hi():
                threading.Event().wait(30)
                subprocess.run(["tmux", "send-keys", "-t", "claude_session", "hi"])
                threading.Event().wait(1)
                subprocess.run(["tmux", "send-keys", "-t", "claude_session", "Enter"])

            threading.Thread(target=send_hi, daemon=True).start()

        if self.timer_thread and self.timer_thread.is_alive():
            self.cancel_event.set()
            self.timer_thread.join(timeout=2)

        self.timer_thread = threading.Thread(target=run_at_time, daemon=True)
        self.timer_thread.start()
        rumps.notification("Claude Scheduler", "Scheduled!", f"Will run at {self.scheduled_time}")

    def hide_cancel(self):
        if "Cancel Schedule" in self.menu:
            del self.menu["Cancel Schedule"]

    def cancel(self, _):
        self.cancel_event.set()
        self.title = "⏰ Claude"
        self.scheduled_time = None
        self.hide_cancel()
        self.stop_caffeinate()
        rumps.notification("Claude Scheduler", "Cancelled", "Schedule cleared")

if __name__ == "__main__":
    ClaudeScheduler().run()
