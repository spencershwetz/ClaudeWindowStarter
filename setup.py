from setuptools import setup

APP = ['claude_scheduler.py']
DATA_FILES = []
OPTIONS = {
    'argv_emulation': True,
    'iconfile': None,
    'plist': {
        'CFBundleName': 'Claude Scheduler',
        'CFBundleDisplayName': 'Claude Scheduler',
        'CFBundleIdentifier': 'com.spencer.claudescheduler',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'LSUIElement': True,  # Makes it a background app (no dock icon)
    },
    'packages': ['rumps'],
}

setup(
    app=APP,
    name='Claude Scheduler',
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
