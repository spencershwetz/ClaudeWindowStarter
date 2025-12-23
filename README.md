# Claude Window Starter

A macOS menu bar app that schedules Claude CLI to start at a specific time, then automatically sends a message after 30 seconds.

## Features

- Schedule Claude to start at any time (24hr format)
- Automatically sends "hi" to Claude 30 seconds after launch
- Prevents Mac from sleeping while waiting (uses caffeinate)
- Shows scheduled time in menu bar
- Works when screen is locked

## Installation

### From Source

1. Create a virtual environment and install dependencies:
```bash
python3 -m venv venv
source venv/bin/activate
pip install rumps py2app
```

2. Build the app:
```bash
python setup.py py2app
```

3. Copy to Applications:
```bash
cp -r "dist/Claude Scheduler.app" /Applications/
```

4. Launch:
```bash
open "/Applications/Claude Scheduler.app"
```

## Usage

1. Click the clock icon in your menu bar
2. Click "Schedule Claude"
3. Enter time in 24hr format (e.g., 18:05 or just 1805)
4. The app will show the scheduled time and prevent your Mac from sleeping
5. At the scheduled time, Terminal opens with Claude running in tmux
6. After 30 seconds, "hi" is automatically sent to Claude

## Requirements

- macOS
- Python 3
- tmux (`brew install tmux`)
- Claude CLI installed and accessible as `claude`

## Auto-start on Login

System Settings → General → Login Items → Add "Claude Scheduler"
