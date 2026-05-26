# Python Client

This folder contains a standalone Python student client.

## What it does

- Runs a local Tetris sandbox in Python for offline bot iteration.
- Connects to the teacher's remote master server over HTTP.
- Lets a student claim player 1 or player 2 and mark themselves ready.
- Visualizes the board and can drive it manually or through a Python bot hook.

## Run

```bash
python3 python_client/app.py
```

If your Python installation does not include `tkinter`, the same command now falls back to a
terminal client automatically.

You can force terminal mode even on machines with Tk support:

```bash
python3 python_client/app.py --cli
```

## Files

- `python_client/app.py` is the desktop client UI.
- `python_client/engine.py` is the local Python Tetris engine.
- `python_client/student_bot.py` is the file students should edit.

## Typical workflow

1. Start in local mode.
2. Edit `python_client/student_bot.py`.
3. Run the bot against the local sandbox until it behaves as expected.
4. Switch to remote mode.
5. Set the teacher's server address such as `http://192.168.1.50:10000`.
6. Choose player 1 or player 2.
7. Click `Mark ready`.

## Dependencies

The client uses only Python standard library modules. On some systems, `tkinter` may need to
be installed separately with the system Python package manager. If it is missing, the terminal
client fallback still supports local sandboxing and remote server control.
