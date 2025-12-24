import rumps
import subprocess
import threading
import os
import json
from datetime import datetime, timedelta
from collections import deque

# Daily schedule times (24hr format)
SCHEDULE_TIMES = ["04:00", "09:00", "14:00", "19:00"]

# Preferences file
PREFS_FILE = os.path.expanduser("~/.claude_scheduler_prefs.json")

# Global log storage (last 50 entries)
app_logs = deque(maxlen=50)


def log(message):
    """Add a timestamped log entry."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    entry = f"[{timestamp}] {message}"
    app_logs.append(entry)
    print(entry)  # Also print to console for debugging


def get_tmux_path():
    """Get the full path to tmux, or None if not installed."""
    result = subprocess.run(["which", "tmux"], capture_output=True, text=True)
    path = result.stdout.strip()
    if not path:
        # Try common locations
        for p in ["/opt/homebrew/bin/tmux", "/usr/local/bin/tmux", "/usr/bin/tmux"]:
            if os.path.exists(p):
                return p
    return path if path else None


def is_tmux_installed():
    """Check if tmux is installed."""
    return get_tmux_path() is not None


def is_homebrew_installed():
    """Check if Homebrew is installed."""
    result = subprocess.run(["which", "brew"], capture_output=True, text=True)
    return bool(result.stdout.strip())


def install_tmux():
    """Install tmux via Homebrew. Returns True if successful."""
    if not is_homebrew_installed():
        return False, "Homebrew not installed"

    result = subprocess.run(
        ["brew", "install", "tmux"],
        capture_output=True,
        text=True
    )
    return result.returncode == 0, result.stderr if result.returncode != 0 else ""


class ClaudeScheduler(rumps.App):
    def __init__(self):
        super().__init__("⏰ Claude", icon=None, quit_button="Quit")

        # Check for tmux on startup
        if not is_tmux_installed():
            self.handle_missing_tmux()

        self.auto_mode = False
        self.check_thread = None
        self.stop_event = threading.Event()
        self.caffeinate_process = None
        self.last_triggered = None
        self.custom_time = None
        self.custom_thread = None
        self.custom_cancel_event = threading.Event()

        # Create menu items
        self.auto_button = rumps.MenuItem("Enable Auto Schedule", callback=self.toggle_auto)
        self.custom_button = rumps.MenuItem("Schedule Custom Time", callback=self.set_custom_time)
        self.cancel_button = rumps.MenuItem("Cancel Custom", callback=self.cancel_custom)
        self.next_label = rumps.MenuItem("Next: --:--", callback=None)
        self.next_label.set_callback(None)
        self.login_button = rumps.MenuItem("Start at Login", callback=self.toggle_login_item)
        self.logs_button = rumps.MenuItem("View Logs", callback=self.show_logs)
        self.test_hi_button = rumps.MenuItem("Test Send Hi Now", callback=self.test_send_hi)

        # Check if already in login items
        if self.is_login_item():
            self.login_button.state = 1

        self.menu = [self.auto_button, self.custom_button, self.next_label, None, self.login_button, self.logs_button, self.test_hi_button]

        log("App started")
        log(f"tmux path: {get_tmux_path()}")

        # Auto-start schedule if preference is set
        if self.load_prefs().get("auto_schedule_enabled", False):
            self.toggle_auto(self.auto_button)

    def handle_missing_tmux(self):
        """Handle the case when tmux is not installed."""
        if is_homebrew_installed():
            # Offer to install tmux
            response = rumps.alert(
                title="tmux Required",
                message="Claude Scheduler requires tmux to run. Would you like to install it now via Homebrew?",
                ok="Install tmux",
                cancel="Quit"
            )
            if response == 1:  # User clicked "Install tmux"
                rumps.notification("Claude Scheduler", "Installing...", "Installing tmux via Homebrew")
                success, error = install_tmux()
                if success:
                    rumps.notification("Claude Scheduler", "Success!", "tmux installed successfully")
                else:
                    rumps.alert(
                        title="Installation Failed",
                        message=f"Failed to install tmux: {error}\n\nPlease run 'brew install tmux' manually.",
                        ok="Quit"
                    )
                    rumps.quit_application()
            else:
                rumps.quit_application()
        else:
            # Homebrew not installed
            rumps.alert(
                title="tmux Required",
                message="Claude Scheduler requires tmux.\n\nPlease install Homebrew first, then run:\nbrew install tmux\n\nVisit https://brew.sh for Homebrew installation.",
                ok="Quit"
            )
            rumps.quit_application()

    def show_logs(self, _):
        """Display recent logs in a dialog."""
        if app_logs:
            log_text = "\n".join(app_logs)
        else:
            log_text = "No logs yet."
        rumps.alert(title="Recent Logs", message=log_text, ok="Close")

    def test_send_hi(self, _):
        """Test sending 'hi' to tmux session immediately."""
        log("test_send_hi: called")
        tmux = get_tmux_path()
        if not tmux:
            log("test_send_hi: tmux not found!")
            rumps.notification("Test", "Error", "tmux not found")
            return

        # First check if session exists
        check = subprocess.run([tmux, "has-session", "-t", "claude_session"], capture_output=True, text=True)
        log(f"test_send_hi: session check returncode={check.returncode}, stderr={check.stderr.strip()}")

        if check.returncode != 0:
            log("test_send_hi: session 'claude_session' does not exist!")
            rumps.notification("Test", "Error", "No tmux session 'claude_session' found. Start Claude first.")
            return

        log("test_send_hi: sending 'hi'")
        result1 = subprocess.run([tmux, "send-keys", "-t", "claude_session", "hi"], capture_output=True, text=True)
        log(f"test_send_hi: send 'hi' returncode={result1.returncode}, stderr={result1.stderr.strip()}")

        threading.Event().wait(0.5)

        log("test_send_hi: sending Enter")
        result2 = subprocess.run([tmux, "send-keys", "-t", "claude_session", "Enter"], capture_output=True, text=True)
        log(f"test_send_hi: send Enter returncode={result2.returncode}, stderr={result2.stderr.strip()}")

        rumps.notification("Test", "Done", "Check logs for results")

    def load_prefs(self):
        try:
            with open(PREFS_FILE, "r") as f:
                return json.load(f)
        except:
            return {}

    def save_prefs(self, prefs):
        try:
            with open(PREFS_FILE, "w") as f:
                json.dump(prefs, f)
        except:
            pass

    def is_login_item(self):
        script = '''
        tell application "System Events"
            get the name of every login item
        end tell
        '''
        result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
        return "Claude Scheduler" in result.stdout

    def toggle_login_item(self, sender):
        app_path = "/Applications/Claude Scheduler.app"
        if sender.state == 0:
            # Add to login items
            script = f'''
            tell application "System Events"
                make login item at end with properties {{path:"{app_path}", hidden:false}}
            end tell
            '''
            subprocess.run(["osascript", "-e", script])
            sender.state = 1
            rumps.notification("Claude Scheduler", "Enabled", "Will start at login")
        else:
            # Remove from login items
            script = '''
            tell application "System Events"
                delete login item "Claude Scheduler"
            end tell
            '''
            subprocess.run(["osascript", "-e", script])
            sender.state = 0
            rumps.notification("Claude Scheduler", "Disabled", "Removed from login items")

    def start_caffeinate(self):
        if self.caffeinate_process is None:
            self.caffeinate_process = subprocess.Popen(["caffeinate", "-i"])

    def stop_caffeinate(self):
        if self.caffeinate_process:
            self.caffeinate_process.terminate()
            self.caffeinate_process = None

    def get_next_scheduled_time(self):
        now = datetime.now()
        today = now.date()

        for time_str in SCHEDULE_TIMES:
            hour, minute = map(int, time_str.split(":"))
            scheduled = datetime.combine(today, datetime.strptime(time_str, "%H:%M").time())
            if scheduled > now:
                return scheduled

        # If all times passed today, return first time tomorrow
        hour, minute = map(int, SCHEDULE_TIMES[0].split(":"))
        return datetime.combine(today + timedelta(days=1), datetime.strptime(SCHEDULE_TIMES[0], "%H:%M").time())

    def toggle_auto(self, sender):
        if self.auto_mode:
            # Disable auto mode
            self.auto_mode = False
            self.stop_event.set()
            self.stop_caffeinate()
            sender.title = "Enable Auto Schedule"
            self.title = "⏰ Claude"
            self.next_label.title = "Next: --:--"
            self.save_prefs({"auto_schedule_enabled": False})
            rumps.notification("Claude Scheduler", "Disabled", "Auto schedule stopped")
        else:
            # Enable auto mode - cancel any custom schedule first
            if self.custom_time:
                self.custom_cancel_event.set()
                self.clear_custom()

            self.auto_mode = True
            self.stop_event.clear()
            self.start_caffeinate()
            sender.title = "Disable Auto Schedule"
            self.start_schedule_checker()
            self.save_prefs({"auto_schedule_enabled": True})
            rumps.notification("Claude Scheduler", "Enabled", f"Auto schedule active: {', '.join(SCHEDULE_TIMES)}")

    def set_custom_time(self, _):
        # Default to next hour + 1 minute
        now = datetime.now()
        next_hour = (now.hour + 1) % 24
        default_time = f"{next_hour:02d}:01"

        window = rumps.Window(
            message='Enter time (HH:MM in 24hr format):',
            title='Schedule Custom Time',
            default_text=default_time,
            dimensions=(200, 24)
        )
        response = window.run()
        if response.clicked:
            time_input = response.text.strip()

            # Auto-insert colon if user just typed 4 digits
            if len(time_input) == 4 and time_input.isdigit():
                time_input = f"{time_input[:2]}:{time_input[2:]}"

            try:
                datetime.strptime(time_input, "%H:%M")

                # Cancel auto mode if active
                if self.auto_mode:
                    self.auto_mode = False
                    self.stop_event.set()
                    self.auto_button.title = "Enable Auto Schedule"

                self.custom_time = time_input
                self.custom_cancel_event.clear()
                self.start_caffeinate()
                self.start_custom_scheduler()

                # Show cancel button
                if "Cancel Custom" not in self.menu:
                    self.menu.insert_after("Schedule Custom Time", self.cancel_button)

                if not self.auto_mode:
                    self.title = f"⏰ {self.custom_time}"
                    self.next_label.title = f"Next: {self.custom_time}"

                rumps.notification("Claude Scheduler", "Scheduled!", f"Custom time set for {self.custom_time}")
            except ValueError:
                rumps.notification("Claude Scheduler", "Error", "Invalid time format. Use HH:MM")

    def start_custom_scheduler(self):
        def run_at_time():
            target = datetime.strptime(self.custom_time, "%H:%M").replace(
                year=datetime.now().year,
                month=datetime.now().month,
                day=datetime.now().day
            )
            wait_seconds = (target - datetime.now()).total_seconds()

            if wait_seconds <= 0:
                rumps.notification("Claude Scheduler", "Error", "Time has already passed today")
                self.clear_custom()
                return

            # Wait in small increments so we can cancel
            while wait_seconds > 0:
                if self.custom_cancel_event.is_set():
                    return
                sleep_time = min(1, wait_seconds)
                threading.Event().wait(sleep_time)
                wait_seconds -= sleep_time

            if self.custom_cancel_event.is_set():
                return

            self.trigger_claude()
            self.clear_custom()

        if self.custom_thread and self.custom_thread.is_alive():
            self.custom_cancel_event.set()
            self.custom_thread.join(timeout=2)
            self.custom_cancel_event.clear()

        self.custom_thread = threading.Thread(target=run_at_time, daemon=True)
        self.custom_thread.start()

    def cancel_custom(self, _):
        self.custom_cancel_event.set()
        self.clear_custom()
        rumps.notification("Claude Scheduler", "Cancelled", "Custom schedule cleared")

    def clear_custom(self):
        self.custom_time = None
        if "Cancel Custom" in self.menu:
            del self.menu["Cancel Custom"]
        if not self.auto_mode:
            self.title = "⏰ Claude"
            self.next_label.title = "Next: --:--"
            self.stop_caffeinate()

    def start_schedule_checker(self):
        def check_loop():
            while not self.stop_event.is_set():
                now = datetime.now()
                current_time = now.strftime("%H:%M")

                # Update next scheduled time display
                next_time = self.get_next_scheduled_time()
                self.next_label.title = f"Next: {next_time.strftime('%H:%M')}"
                self.title = f"⏰ {next_time.strftime('%H:%M')}"

                # Check if current time matches any schedule
                if current_time in SCHEDULE_TIMES:
                    # Avoid triggering twice in the same minute
                    if self.last_triggered != current_time:
                        self.last_triggered = current_time
                        self.trigger_claude()

                # Check every 30 seconds
                self.stop_event.wait(30)

        self.check_thread = threading.Thread(target=check_loop, daemon=True)
        self.check_thread.start()

    def trigger_claude(self):
        log("trigger_claude called")

        # Get full path to tmux
        tmux = get_tmux_path()
        if not tmux:
            log("ERROR: tmux not found!")
            rumps.notification("Claude Scheduler", "Error", "tmux not found!")
            return

        log(f"Using tmux at: {tmux}")

        # Open Terminal and start claude in tmux (use full path)
        cmd = f'{tmux} kill-session -t claude_session 2>/dev/null; {tmux} new-session -d -s claude_session \\"claude\\" && {tmux} attach -t claude_session'

        log(f"Running Terminal command")
        script = f'''
        tell application "Terminal"
            activate
            do script "{cmd}"
        end tell
        '''
        result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
        log(f"Terminal script result: returncode={result.returncode}")
        if result.stderr:
            log(f"Terminal script stderr: {result.stderr}")

        rumps.notification("Claude Scheduler", "Running!", f"Claude started at {datetime.now().strftime('%H:%M')}")

        # Wait 15 seconds then send "hi" (in a separate thread)
        def send_hi():
            log("send_hi: waiting 15 seconds...")
            threading.Event().wait(15)

            log("send_hi: sending 'hi' to tmux")
            result1 = subprocess.run([tmux, "send-keys", "-t", "claude_session", "hi"], capture_output=True, text=True)
            log(f"send_hi: send 'hi' result: returncode={result1.returncode}, stderr={result1.stderr}")

            threading.Event().wait(1)

            log("send_hi: sending Enter")
            result2 = subprocess.run([tmux, "send-keys", "-t", "claude_session", "Enter"], capture_output=True, text=True)
            log(f"send_hi: send Enter result: returncode={result2.returncode}, stderr={result2.stderr}")

            log("send_hi: complete")

        log("Starting send_hi thread")
        threading.Thread(target=send_hi, daemon=True).start()

if __name__ == "__main__":
    ClaudeScheduler().run()
