# Tetris AI Lab

This project is a small teaching environment for students who want to build an AI that can
play Tetris without first needing to build a backend stack from scratch.

## What is included

- A master server that owns the Tetris rules and the score for two players.
- A master dashboard at `/` that shows both boards in real time.
- A student client at `/client.html?player=1` or `/client.html?player=2`.
- A standalone Python student client in `python_client/` for students who want to stay in
  Python instead of editing JavaScript.
- A local sandbox mode inside the client page for testing the bot without touching the
  shared server state.
- A ready-up lobby so the classroom match starts only after both students connect and click
  `Mark ready`.
- A simple `student-bot.js` file where students can replace the default move logic.

## API

The API is intentionally small and polling-friendly:

- `GET /api/session`
- `POST /api/session/reset`
- `POST /api/session/pause`
- `POST /api/session/resume`
- `GET /api/players/1/state`
- `GET /api/players/2/state`
- `POST /api/players/1/ready`
- `POST /api/players/2/ready`
- `POST /api/players/1/command`
- `POST /api/players/2/command`

Example command body:

```json
{
  "command": "rotate"
}
```

Example ready body:

```json
{
  "ready": true
}
```

Supported commands:

- `left`
- `right`
- `down`
- `rotate`
- `drop`

## Run

```bash
npm start
```

In case of permission issues, run the following command to temporarily bypass security.
```bash
powershell -ExecutionPolicy Bypass
```

Then open:

- `http://localhost:10000/` for the master application
- `http://localhost:10000/client.html?player=1` for player 1 client
- `http://localhost:10000/client.html?player=2` for player 2 client

Run the Python student client with:

```bash
python3 python_client/app.py
```

If `tkinter` is not available in the Python installation, the app automatically falls back to
an interactive terminal client. You can also force terminal mode with:

```bash
python3 python_client/app.py --cli
```

## Suggested student workflow

1. Open the client page in `local` mode.
2. Edit `/public/student-bot.js`.
3. Keep the visualization open while the bot runs locally.
4. Switch to `remote` mode when the strategy is ready to control the master server.
5. Set the teacher's server address, choose player 1 or player 2, and click `Mark ready`.
6. The shared match starts automatically when both students are connected and ready.

## Suggested Python workflow

1. Run `python3 python_client/app.py`.
2. Start in `local` mode.
3. Edit `python_client/student_bot.py`.
4. Use the local sandbox until the behavior looks right.
5. Switch to `remote` mode.
6. Set the teacher's server address, choose player 1 or player 2, and click `Mark ready`.

## Notes

- The app is intentionally dependency-light and uses only Node built-ins.
- The same Tetris engine powers both the server and the local sandbox client.
- The Python desktop client is also dependency-light and uses the Python standard library.
- If `tkinter` is missing, the Python client still works in terminal mode.
- If you want students to run their bot from a separate process later, they can call the
  same HTTP API from Python, JavaScript, Java, or another language.
- `Reset match` puts the server back into the waiting-room state and clears both ready flags.
