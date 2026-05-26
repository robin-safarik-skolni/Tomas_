from __future__ import annotations

import argparse
import json
import queue
import threading
import time
from pathlib import Path
from typing import Any
from urllib import error, request

try:
    import tkinter as tk
    from tkinter import ttk

    TK_AVAILABLE = True
except ModuleNotFoundError:
    tk = None
    ttk = None
    TK_AVAILABLE = False

from engine import COMMANDS, TICK_MS, apply_command, create_player_state, get_player_snapshot, reset_player_state, step_state
from student_bot import choose_command

BOARD_PIXEL_WIDTH = 300
BOARD_PIXEL_HEIGHT = 600
REMOTE_POLL_MS = 200
AUTOPLAY_MS = 180
DEFAULT_API = "http://localhost:10000"

COLORS = {
    0: "#161917",
    "I": "#59d7ff",
    "I_active": "#a8f0ff",
    "J": "#496aff",
    "J_active": "#a7b6ff",
    "L": "#ff9b4a",
    "L_active": "#ffd1a2",
    "O": "#ffe066",
    "O_active": "#fff1ad",
    "S": "#65db7d",
    "S_active": "#b8efc4",
    "T": "#bf6bff",
    "T_active": "#e2bbff",
    "Z": "#ff6464",
    "Z_active": "#ffb2b2",
}


def api_get(base_url: str, path: str) -> dict[str, Any]:
    with request.urlopen(f"{base_url.rstrip('/')}{path}", timeout=2) as response:
        return json.load(response)


def api_post(base_url: str, path: str, payload: dict[str, Any]) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(
        f"{base_url.rstrip('/')}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=2) as response:
            return json.load(response)
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        if body:
            return json.loads(body)
        raise


def render_text_board(board: list[list[Any]]) -> str:
    rows = []
    for row in board:
        cells = []
        for cell in row:
            if not cell:
                cells.append(" .")
            elif isinstance(cell, str) and cell.endswith("_active"):
                cells.append("[]")
            else:
                cells.append("##")
        rows.append("".join(cells))
    return "\n".join(rows)


def snapshot_summary(snapshot: dict[str, Any]) -> str:
    if snapshot.get("gameOver"):
        status = "Game over"
    elif snapshot.get("matchStarted"):
        status = "Paused" if snapshot.get("paused") else "Running"
    else:
        status = "Waiting"

    return (
        f"Status: {status}\n"
        f"Score: {snapshot.get('score', 0)}\n"
        f"Lines: {snapshot.get('lines', 0)}\n"
        f"Next: {snapshot.get('nextPieceType', '-')}\n"
        f"Connected: {snapshot.get('connected', True)}\n"
        f"Ready: {snapshot.get('ready', True)}\n"
        f"Match state: {snapshot.get('matchState', 'Local sandbox')}\n"
        f"{render_text_board(snapshot.get('board', []))}"
    )


if TK_AVAILABLE:

    class PythonTetrisClient:
        def __init__(self, root: tk.Tk) -> None:
            self.root = root
            self.root.title("Tetris AI Lab | Python Client")
            self.root.geometry("980x760")
            self.root.minsize(900, 720)
            self.root.configure(bg="#f3efe6")

            self.local_state = create_player_state("Local Sandbox")
            self.last_snapshot = get_player_snapshot(self.local_state)
            self.autoplay = False
            self.remote_ready = False
            self.local_tick_job: str | None = None
            self.remote_poll_job: str | None = None
            self.autoplay_job: str | None = None
            self.ui_queue_job: str | None = None
            self.ui_queue: queue.SimpleQueue[Any] = queue.SimpleQueue()
            self.remote_poll_inflight = False

            self.mode_var = tk.StringVar(value="remote")
            self.player_var = tk.StringVar(value="1")
            self.api_var = tk.StringVar(value=DEFAULT_API)
            self.status_var = tk.StringVar(value="Idle")
            self.score_var = tk.StringVar(value="0")
            self.lines_var = tk.StringVar(value="0")
            self.next_var = tk.StringVar(value="-")
            self.player_indicator_var = tk.StringVar(value="1")
            self.remote_lobby_var = tk.StringVar(value="Waiting to connect to the master server.")
            self.bot_log_var = tk.StringVar(value=f"Edit {Path(__file__).with_name('student_bot.py')} to change the AI strategy.")
            self.ready_button_var = tk.StringVar(value="Mark ready")
            self.autoplay_button_var = tk.StringVar(value="Start bot")

            self.build_ui()
            self.process_ui_queue()
            self.render_snapshot(self.last_snapshot)
            self.schedule_autoplay_loop()

        def build_ui(self) -> None:
            assert ttk is not None
            style = ttk.Style()
            style.theme_use("clam")
            style.configure("Shell.TFrame", background="#f3efe6")
            style.configure("Card.TFrame", background="#fffaf1", relief="flat")
            style.configure("Title.TLabel", background="#f3efe6", foreground="#1f2a22", font=("Avenir Next", 26, "bold"))
            style.configure("Body.TLabel", background="#f3efe6", foreground="#59645b", font=("IBM Plex Sans", 11))
            style.configure("CardLabel.TLabel", background="#fffaf1", foreground="#1f2a22", font=("IBM Plex Sans", 10, "bold"))
            style.configure("Meta.TLabel", background="#fffaf1", foreground="#59645b", font=("IBM Plex Sans", 10))

            shell = ttk.Frame(self.root, style="Shell.TFrame", padding=20)
            shell.pack(fill="both", expand=True)
            shell.columnconfigure(0, weight=3)
            shell.columnconfigure(1, weight=2)
            shell.rowconfigure(1, weight=1)

            header = ttk.Frame(shell, style="Shell.TFrame")
            header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 16))
            header.columnconfigure(0, weight=1)

            ttk.Label(header, text="Python student client", style="Title.TLabel").grid(row=0, column=0, sticky="w")
            ttk.Label(
                header,
                text="Run your bot locally in Python or connect the same client to the teacher's remote master server.",
                style="Body.TLabel",
                wraplength=760,
                justify="left",
            ).grid(row=1, column=0, sticky="w", pady=(8, 0))

            board_card = ttk.Frame(shell, style="Card.TFrame", padding=16)
            board_card.grid(row=1, column=0, sticky="nsew", padx=(0, 12))
            board_card.columnconfigure(0, weight=1)

            board_header = ttk.Frame(board_card, style="Card.TFrame")
            board_header.grid(row=0, column=0, sticky="ew", pady=(0, 12))
            board_header.columnconfigure(0, weight=1)

            ttk.Label(board_header, text="Current board", style="CardLabel.TLabel").grid(row=0, column=0, sticky="w")
            ttk.Label(board_header, textvariable=self.player_indicator_var, style="CardLabel.TLabel").grid(row=0, column=1, sticky="e")

            self.canvas = tk.Canvas(
                board_card,
                width=BOARD_PIXEL_WIDTH,
                height=BOARD_PIXEL_HEIGHT,
                background="#161917",
                highlightthickness=0,
            )
            self.canvas.grid(row=1, column=0, sticky="n", pady=(0, 12))

            meta = ttk.Frame(board_card, style="Card.TFrame")
            meta.grid(row=2, column=0, sticky="ew")
            for column in range(4):
                meta.columnconfigure(column, weight=1)

            self.meta_value(meta, "Score", self.score_var, 0)
            self.meta_value(meta, "Lines", self.lines_var, 1)
            self.meta_value(meta, "Next", self.next_var, 2)
            self.meta_value(meta, "Status", self.status_var, 3)

            control_card = ttk.Frame(shell, style="Card.TFrame", padding=16)
            control_card.grid(row=1, column=1, sticky="nsew")
            control_card.columnconfigure(0, weight=1)

            row = 0
            row = self.add_select(control_card, row, "Mode", self.mode_var, ["remote", "local"], self.on_mode_changed)
            row = self.add_select(control_card, row, "Remote player slot", self.player_var, ["1", "2"], self.on_player_changed)
            row = self.add_entry(control_card, row, "API base URL", self.api_var)

            ttk.Label(control_card, text="Remote match lobby", style="CardLabel.TLabel").grid(row=row, column=0, sticky="w")
            row += 1
            ttk.Button(control_card, textvariable=self.ready_button_var, command=self.toggle_ready).grid(row=row, column=0, sticky="ew")
            row += 1
            ttk.Label(control_card, textvariable=self.remote_lobby_var, style="Meta.TLabel", wraplength=300, justify="left").grid(
                row=row, column=0, sticky="w", pady=(6, 14)
            )
            row += 1

            ttk.Label(control_card, text="Autoplay", style="CardLabel.TLabel").grid(row=row, column=0, sticky="w")
            row += 1
            ttk.Button(control_card, textvariable=self.autoplay_button_var, command=self.toggle_autoplay).grid(row=row, column=0, sticky="ew", pady=(0, 14))
            row += 1

            ttk.Label(control_card, text="Manual commands", style="CardLabel.TLabel").grid(row=row, column=0, sticky="w")
            row += 1
            command_frame = ttk.Frame(control_card, style="Card.TFrame")
            command_frame.grid(row=row, column=0, sticky="ew", pady=(0, 14))
            for index, command in enumerate(COMMANDS):
                ttk.Button(command_frame, text=command.title(), command=lambda value=command: self.send_command(value)).grid(
                    row=index // 2,
                    column=index % 2,
                    sticky="ew",
                    padx=4,
                    pady=4,
                )
            command_frame.columnconfigure(0, weight=1)
            command_frame.columnconfigure(1, weight=1)
            row += 1

            ttk.Button(control_card, text="Reset local game", command=self.reset_local_game).grid(row=row, column=0, sticky="ew", pady=(0, 14))
            row += 1

            ttk.Label(control_card, text="Student hook", style="CardLabel.TLabel").grid(row=row, column=0, sticky="w")
            row += 1
            ttk.Label(
                control_card,
                text=f"Edit {Path(__file__).with_name('student_bot.py').name}. The Python client imports your function and calls it with the latest snapshot.",
                style="Meta.TLabel",
                wraplength=300,
                justify="left",
            ).grid(row=row, column=0, sticky="w", pady=(6, 14))
            row += 1

            ttk.Label(control_card, text="Latest decision", style="CardLabel.TLabel").grid(row=row, column=0, sticky="w")
            row += 1
            log = tk.Label(
                control_card,
                textvariable=self.bot_log_var,
                bg="#1d211e",
                fg="#f0f4ef",
                anchor="nw",
                justify="left",
                padx=12,
                pady=12,
                wraplength=300,
            )
            log.grid(row=row, column=0, sticky="nsew")
            control_card.rowconfigure(row, weight=1)

        def meta_value(self, parent: Any, label: str, variable: Any, column: int) -> None:
            assert ttk is not None
            ttk.Label(parent, text=label, style="Meta.TLabel").grid(row=0, column=column, sticky="w")
            ttk.Label(parent, textvariable=variable, style="CardLabel.TLabel").grid(row=1, column=column, sticky="w")

        def add_select(self, parent: Any, row: int, label: str, variable: Any, values: list[str], callback: Any) -> int:
            assert ttk is not None
            ttk.Label(parent, text=label, style="CardLabel.TLabel").grid(row=row, column=0, sticky="w")
            row += 1
            combo = ttk.Combobox(parent, textvariable=variable, values=values, state="readonly")
            combo.grid(row=row, column=0, sticky="ew", pady=(0, 14))
            combo.bind("<<ComboboxSelected>>", callback)
            return row + 1

        def add_entry(self, parent: Any, row: int, label: str, variable: Any) -> int:
            assert ttk is not None
            ttk.Label(parent, text=label, style="CardLabel.TLabel").grid(row=row, column=0, sticky="w")
            row += 1
            ttk.Entry(parent, textvariable=variable).grid(row=row, column=0, sticky="ew", pady=(0, 14))
            return row + 1

        def set_bot_log(self, message: str) -> None:
            self.bot_log_var.set(message)

        def get_api_base(self) -> str:
            return self.api_var.get().strip().rstrip("/")

        def get_player_id(self) -> str:
            return self.player_var.get()

        def enqueue_ui(self, callback: Any) -> None:
            self.ui_queue.put(callback)

        def process_ui_queue(self) -> None:
            while True:
                try:
                    callback = self.ui_queue.get_nowait()
                except queue.Empty:
                    break

                try:
                    callback()
                except Exception as exc:  # noqa: BLE001
                    self.set_bot_log(f"UI update failed.\n{exc}")

            self.ui_queue_job = self.root.after(50, self.process_ui_queue)

        def run_remote_task(self, task: Any, on_success: Any, error_message: str) -> None:
            api_base = self.get_api_base()
            player_id = self.get_player_id()

            def worker() -> None:
                try:
                    payload = task(api_base, player_id)
                except Exception as exc:  # noqa: BLE001
                    self.enqueue_ui(lambda exc=exc: self.set_bot_log(f"{error_message}\n{exc}"))
                    return

                def finish() -> None:
                    if self.get_api_base() != api_base or self.get_player_id() != player_id:
                        return
                    on_success(payload)

                self.enqueue_ui(finish)

            threading.Thread(target=worker, daemon=True).start()

        def render_snapshot(self, snapshot: dict[str, Any]) -> None:
            self.last_snapshot = snapshot
            self.player_indicator_var.set("Local" if self.mode_var.get() == "local" else self.get_player_id())
            self.score_var.set(str(snapshot.get("score", 0)))
            self.lines_var.set(str(snapshot.get("lines", 0)))
            self.next_var.set(str(snapshot.get("nextPieceType", "-")))

            if snapshot.get("gameOver"):
                status = "Game over"
            elif snapshot.get("matchStarted"):
                status = "Paused" if snapshot.get("paused") else "Running"
            else:
                status = "Waiting"
            self.status_var.set(status)

            self.draw_board(snapshot.get("board", []))
            self.render_remote_lobby(snapshot)

        def render_remote_lobby(self, snapshot: dict[str, Any]) -> None:
            if self.mode_var.get() == "local":
                self.ready_button_var.set("Mark ready")
                self.remote_lobby_var.set("Local sandbox mode does not use the master lobby.")
                return

            self.remote_ready = bool(snapshot.get("ready"))
            self.ready_button_var.set("Cancel ready" if self.remote_ready else "Mark ready")

            if not snapshot.get("matchStarted"):
                self.remote_lobby_var.set(
                    f"Connected: {'yes' if snapshot.get('connected') else 'no'} | "
                    f"Ready: {'yes' if snapshot.get('ready') else 'no'} | "
                    f"Match state: {snapshot.get('matchState', 'Waiting')}"
                )
                return

            self.remote_lobby_var.set(
                f"Connected: {'yes' if snapshot.get('connected') else 'no'} | "
                f"Match state: {snapshot.get('matchState', 'Running')}"
            )

        def draw_board(self, board: list[list[Any]]) -> None:
            self.canvas.delete("all")
            if not board:
                return

            cell_width = BOARD_PIXEL_WIDTH / len(board[0])
            cell_height = BOARD_PIXEL_HEIGHT / len(board)
            for y, row in enumerate(board):
                for x, cell in enumerate(row):
                    color = COLORS.get(cell, COLORS[0])
                    self.canvas.create_rectangle(
                        x * cell_width,
                        y * cell_height,
                        (x + 1) * cell_width,
                        (y + 1) * cell_height,
                        fill=color,
                        outline="#202320",
                        width=1,
                    )

        def fetch_remote_snapshot_async(self, on_done: Any | None = None) -> None:
            def task(api_base: str, player_id: str) -> dict[str, Any]:
                return api_get(api_base, f"/api/players/{player_id}/state")

            def success(snapshot: dict[str, Any]) -> None:
                self.render_snapshot(snapshot)
                if on_done:
                    on_done(snapshot)

            self.run_remote_task(task, success, "Remote fetch failed.")

        def send_remote_command(self, command: str) -> None:
            def task(api_base: str, player_id: str) -> dict[str, Any]:
                return api_post(api_base, f"/api/players/{player_id}/command", {"command": command})

            def success(payload: dict[str, Any]) -> None:
                snapshot = payload.get("player")
                if snapshot:
                    self.render_snapshot(snapshot)
                self.set_bot_log(
                    f"Remote command: {command}\n"
                    f"Accepted: {payload.get('accepted')}\n"
                    f"{payload.get('error', 'No server error.')}"
                )

            self.run_remote_task(task, success, "Command failed.")

        def set_remote_ready(self, ready: bool) -> None:
            def task(api_base: str, player_id: str) -> dict[str, Any]:
                return api_post(api_base, f"/api/players/{player_id}/ready", {"ready": ready})

            def success(snapshot: dict[str, Any]) -> None:
                self.render_snapshot(snapshot)
                if ready:
                    self.set_bot_log("Ready sent to master server.\nWaiting for the other player.")
                else:
                    self.set_bot_log("Ready cancelled.\nThe match will stay in the lobby.")

            self.run_remote_task(task, success, "Ready update failed.")

        def refresh_local_snapshot(self) -> None:
            self.render_snapshot(get_player_snapshot(self.local_state))

        def send_local_command(self, command: str) -> None:
            result = apply_command(self.local_state, command)
            snapshot = get_player_snapshot(self.local_state)
            self.render_snapshot(snapshot)
            self.set_bot_log(f"Local command: {command}\nAccepted: {result.get('accepted')}\nScore: {snapshot['score']}")

        def send_command(self, command: str) -> None:
            if self.mode_var.get() == "remote":
                self.send_remote_command(command)
                return

            try:
                self.send_local_command(command)
            except Exception as exc:  # noqa: BLE001
                self.set_bot_log(f"Command failed.\n{exc}")

        def reset_local_game(self) -> None:
            reset_player_state(self.local_state)
            self.refresh_local_snapshot()
            self.set_bot_log("Local sandbox reset.")

        def stop_local_ticks(self) -> None:
            if self.local_tick_job:
                self.root.after_cancel(self.local_tick_job)
                self.local_tick_job = None

        def stop_remote_polling(self) -> None:
            if self.remote_poll_job:
                self.root.after_cancel(self.remote_poll_job)
                self.remote_poll_job = None

        def local_tick(self) -> None:
            step_state(self.local_state)
            self.refresh_local_snapshot()
            self.local_tick_job = self.root.after(TICK_MS, self.local_tick)

        def remote_poll(self) -> None:
            if self.mode_var.get() != "remote":
                self.remote_poll_inflight = False
                return

            if self.remote_poll_inflight:
                self.remote_poll_job = self.root.after(REMOTE_POLL_MS, self.remote_poll)
                return

            self.remote_poll_inflight = True

            def task(api_base: str, player_id: str) -> dict[str, Any]:
                return api_get(api_base, f"/api/players/{player_id}/state")

            def success(snapshot: dict[str, Any]) -> None:
                self.remote_poll_inflight = False
                self.render_snapshot(snapshot)
                if self.mode_var.get() == "remote":
                    self.remote_poll_job = self.root.after(REMOTE_POLL_MS, self.remote_poll)

            def failure(exc: Exception) -> None:
                self.remote_poll_inflight = False
                self.set_bot_log(f"Remote fetch failed.\n{exc}")
                if self.mode_var.get() == "remote":
                    self.remote_poll_job = self.root.after(REMOTE_POLL_MS, self.remote_poll)

            api_base = self.get_api_base()
            player_id = self.get_player_id()

            def worker() -> None:
                try:
                    snapshot = task(api_base, player_id)
                except Exception as exc:  # noqa: BLE001
                    self.enqueue_ui(lambda exc=exc: failure(exc))
                    return

                def finish() -> None:
                    if self.get_api_base() != api_base or self.get_player_id() != player_id:
                        self.remote_poll_inflight = False
                        if self.mode_var.get() == "remote":
                            self.remote_poll_job = self.root.after(REMOTE_POLL_MS, self.remote_poll)
                        return
                    success(snapshot)

                self.enqueue_ui(finish)

            threading.Thread(target=worker, daemon=True).start()

        def apply_mode(self) -> None:
            self.stop_local_ticks()
            self.stop_remote_polling()
            if self.mode_var.get() == "remote":
                self.remote_poll()
            else:
                self.refresh_local_snapshot()
                self.local_tick()

        def toggle_ready(self) -> None:
            if self.mode_var.get() != "remote":
                self.set_bot_log("Ready is only used in remote mode.")
                return
            self.set_remote_ready(not self.remote_ready)

        def autoplay_step(self) -> None:
            if self.autoplay:
                if self.mode_var.get() == "remote":
                    def continue_remote(snapshot: dict[str, Any]) -> None:
                        if not snapshot.get("matchStarted") or snapshot.get("paused") or not snapshot.get("ready"):
                            self.schedule_autoplay_loop()
                            return

                        command = choose_command(snapshot)
                        if command not in COMMANDS:
                            self.set_bot_log(f"Bot skipped turn.\nSuggested command: {command}")
                        else:
                            self.send_remote_command(command)
                        self.schedule_autoplay_loop()

                    self.fetch_remote_snapshot_async(continue_remote)
                    return

                try:
                    snapshot = get_player_snapshot(self.local_state)
                    command = choose_command(snapshot)
                    if command not in COMMANDS:
                        self.set_bot_log(f"Bot skipped turn.\nSuggested command: {command}")
                    else:
                        self.send_local_command(command)
                except Exception as exc:  # noqa: BLE001
                    self.set_bot_log(f"Bot failed.\n{exc}")

            self.schedule_autoplay_loop()

        def schedule_autoplay_loop(self) -> None:
            if self.autoplay_job:
                self.root.after_cancel(self.autoplay_job)
            self.autoplay_job = self.root.after(AUTOPLAY_MS, self.autoplay_step)

        def toggle_autoplay(self) -> None:
            self.autoplay = not self.autoplay
            self.autoplay_button_var.set("Stop bot" if self.autoplay else "Start bot")

        def on_mode_changed(self, _event: Any) -> None:
            self.apply_mode()

        def on_player_changed(self, _event: Any) -> None:
            self.remote_ready = False
            if self.mode_var.get() == "remote":
                self.fetch_remote_snapshot_async()


class TerminalTetrisClient:
    def __init__(self, mode: str, player: str, api_base: str, autoplay: bool) -> None:
        self.mode = mode
        self.player = player
        self.api_base = api_base.rstrip("/")
        self.local_state = create_player_state("Local Sandbox")
        self.last_snapshot = get_player_snapshot(self.local_state)
        self.remote_ready = False
        self.autoplay = autoplay
        self.running = True
        self.lock = threading.Lock()
        self.last_render_signature = ""
        self.worker = threading.Thread(target=self.background_loop, daemon=True)

    def start(self) -> None:
        print("Python client running in terminal mode.")
        print(f"Edit {Path(__file__).with_name('student_bot.py')} to change the AI strategy.")
        print("Type 'help' for commands.\n")
        self.worker.start()
        self.print_status()

        while self.running:
            try:
                raw = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break

            if not raw:
                continue

            try:
                self.handle_command(raw)
            except Exception as exc:  # noqa: BLE001
                print(f"Command failed: {exc}")

        self.running = False
        print("Terminal client stopped.")

    def background_loop(self) -> None:
        last_local_tick = time.monotonic()
        last_remote_poll = 0.0
        last_autoplay = 0.0

        while self.running:
            now = time.monotonic()
            should_render = False
            with self.lock:
                if self.mode == "local" and now - last_local_tick >= TICK_MS / 1000:
                    step_state(self.local_state)
                    self.last_snapshot = get_player_snapshot(self.local_state)
                    last_local_tick = now
                    should_render = True

                if self.mode == "remote" and now - last_remote_poll >= REMOTE_POLL_MS / 1000:
                    try:
                        snapshot = self.fetch_remote_snapshot()
                        if self.snapshot_signature(snapshot) != self.snapshot_signature(self.last_snapshot):
                            should_render = True
                        self.last_snapshot = snapshot
                    except Exception:
                        pass
                    last_remote_poll = now

                if self.autoplay and now - last_autoplay >= AUTOPLAY_MS / 1000:
                    self.bot_step(log=False)
                    last_autoplay = now
                    should_render = True

                if should_render:
                    self.render_live_snapshot()

            time.sleep(0.05)

    def fetch_remote_snapshot(self) -> dict[str, Any]:
        snapshot = api_get(self.api_base, f"/api/players/{self.player}/state")
        self.remote_ready = bool(snapshot.get("ready"))
        return snapshot

    def send_remote_command(self, command: str) -> dict[str, Any]:
        return api_post(self.api_base, f"/api/players/{self.player}/command", {"command": command})

    def set_remote_ready(self, ready: bool) -> dict[str, Any]:
        snapshot = api_post(self.api_base, f"/api/players/{self.player}/ready", {"ready": ready})
        self.remote_ready = bool(snapshot.get("ready"))
        self.last_snapshot = snapshot
        return snapshot

    def send_local_command(self, command: str) -> dict[str, Any]:
        result = apply_command(self.local_state, command)
        self.last_snapshot = get_player_snapshot(self.local_state)
        return {"accepted": result.get("accepted"), "player": self.last_snapshot}

    def print_status(self) -> None:
        with self.lock:
            snapshot = self.last_snapshot if self.mode == "local" else self.fetch_remote_snapshot()
            self.last_snapshot = snapshot
            self.render_live_snapshot(force=True)

    def snapshot_signature(self, snapshot: dict[str, Any]) -> str:
        return json.dumps(snapshot, sort_keys=True)

    def render_live_snapshot(self, force: bool = False) -> None:
        signature = self.snapshot_signature(self.last_snapshot)
        if not force and signature == self.last_render_signature:
            return

        self.last_render_signature = signature
        print()
        print(f"[live update] mode={self.mode} player={self.player} autoplay={self.autoplay}")
        print(snapshot_summary(self.last_snapshot))
        print()

    def run_move(self, command: str) -> None:
        with self.lock:
            if self.mode == "remote":
                payload = self.send_remote_command(command)
                player = payload.get("player", self.last_snapshot)
                self.last_snapshot = player
                print(f"Remote command: {command} | accepted={payload.get('accepted')} | error={payload.get('error', '-')}")
            else:
                payload = self.send_local_command(command)
                self.last_snapshot = payload["player"]
                print(f"Local command: {command} | accepted={payload.get('accepted')}")

    def bot_step(self, log: bool = True) -> None:
        snapshot = self.last_snapshot if self.mode == "local" else self.fetch_remote_snapshot()
        self.last_snapshot = snapshot

        if self.mode == "remote" and (
            not snapshot.get("matchStarted") or snapshot.get("paused") or not snapshot.get("ready")
        ):
            if log:
                print("Bot is waiting for the remote match to start.")
            return

        command = choose_command(snapshot)
        if command not in COMMANDS:
            if log:
                print(f"Bot skipped turn. Suggested command: {command}")
            return

        if self.mode == "remote":
            payload = self.send_remote_command(command)
            self.last_snapshot = payload.get("player", snapshot)
            if log:
                print(f"Bot command: {command} | accepted={payload.get('accepted')} | error={payload.get('error', '-')}")
        else:
            payload = self.send_local_command(command)
            self.last_snapshot = payload["player"]
            if log:
                print(f"Bot command: {command} | accepted={payload.get('accepted')}")

    def print_help(self) -> None:
        print(
            "\nCommands:\n"
            "  help                 Show this help\n"
            "  status               Print the current board and state\n"
            "  mode local|remote    Switch client mode\n"
            "  player 1|2           Change remote player slot\n"
            "  api URL              Change remote API base URL\n"
            "  ready                Toggle remote ready state\n"
            "  auto on|off          Enable or disable autoplay\n"
            "  bot                  Run one bot step\n"
            "  reset                Reset the local sandbox\n"
            "  left/right/down/rotate/drop\n"
            "  quit                 Exit the terminal client\n"
        )

    def handle_command(self, raw: str) -> None:
        parts = raw.split(maxsplit=1)
        command = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        if command == "help":
            self.print_help()
            return

        if command == "quit":
            self.running = False
            return

        if command == "status":
            self.print_status()
            return

        if command == "mode":
            if arg not in {"local", "remote"}:
                print("Use: mode local|remote")
                return
            with self.lock:
                self.mode = arg
                if self.mode == "local":
                    self.last_snapshot = get_player_snapshot(self.local_state)
                else:
                    self.last_snapshot = self.fetch_remote_snapshot()
            self.print_status()
            return

        if command == "player":
            if arg not in {"1", "2"}:
                print("Use: player 1|2")
                return
            with self.lock:
                self.player = arg
                self.remote_ready = False
                if self.mode == "remote":
                    self.last_snapshot = self.fetch_remote_snapshot()
            self.print_status()
            return

        if command == "api":
            if not arg:
                print("Use: api http://host:10000")
                return
            with self.lock:
                self.api_base = arg.rstrip("/")
                if self.mode == "remote":
                    self.last_snapshot = self.fetch_remote_snapshot()
            self.print_status()
            return

        if command == "ready":
            with self.lock:
                if self.mode != "remote":
                    print("Ready is only used in remote mode.")
                    return
                snapshot = self.set_remote_ready(not self.remote_ready)
                print(f"Ready: {snapshot.get('ready')} | Match state: {snapshot.get('matchState')}")
            return

        if command == "auto":
            if arg not in {"on", "off"}:
                print("Use: auto on|off")
                return
            with self.lock:
                self.autoplay = arg == "on"
            print(f"Autoplay: {self.autoplay}")
            return

        if command == "bot":
            with self.lock:
                self.bot_step()
            return

        if command == "reset":
            with self.lock:
                reset_player_state(self.local_state)
                self.last_snapshot = get_player_snapshot(self.local_state)
            print("Local sandbox reset.")
            return

        if command in COMMANDS:
            self.run_move(command)
            return

        print("Unknown command. Type 'help' for available commands.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Tetris AI Lab Python client")
    parser.add_argument("--cli", action="store_true", help="Run the terminal client even if tkinter is available")
    parser.add_argument("--mode", choices=["local", "remote"], default="remote", help="Initial client mode")
    parser.add_argument("--player", choices=["1", "2"], default="1", help="Remote player slot")
    parser.add_argument("--api", default=DEFAULT_API, help="Remote API base URL")
    parser.add_argument("--autoplay", action="store_true", help="Start with autoplay enabled")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.cli or not TK_AVAILABLE:
        if not TK_AVAILABLE and not args.cli:
            print("tkinter is not available in this Python build, so the client is starting in terminal mode.")
            print("You can still use local sandboxing and connect to the remote master server.\n")
        client = TerminalTetrisClient(args.mode, args.player, args.api, args.autoplay)
        client.start()
        return

    root = tk.Tk()
    client = PythonTetrisClient(root)
    client.mode_var.set(args.mode)
    client.player_var.set(args.player)
    client.api_var.set(args.api)
    if args.autoplay:
        client.toggle_autoplay()
    client.apply_mode()
    root.mainloop()


if __name__ == "__main__":
    main()
