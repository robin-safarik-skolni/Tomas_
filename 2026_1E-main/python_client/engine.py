from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

BOARD_WIDTH = 10
BOARD_HEIGHT = 20
TICK_MS = 700
COMMANDS = ["left", "right", "down", "rotate", "drop"]

PIECE_TYPES = ["I", "J", "L", "O", "S", "T", "Z"]

PIECES = {
    "I": [
        [0, 0, 0, 0],
        [1, 1, 1, 1],
        [0, 0, 0, 0],
        [0, 0, 0, 0],
    ],
    "J": [
        [1, 0, 0],
        [1, 1, 1],
        [0, 0, 0],
    ],
    "L": [
        [0, 0, 1],
        [1, 1, 1],
        [0, 0, 0],
    ],
    "O": [
        [1, 1],
        [1, 1],
    ],
    "S": [
        [0, 1, 1],
        [1, 1, 0],
        [0, 0, 0],
    ],
    "T": [
        [0, 1, 0],
        [1, 1, 1],
        [0, 0, 0],
    ],
    "Z": [
        [1, 1, 0],
        [0, 1, 1],
        [0, 0, 0],
    ],
}


def clone_matrix(matrix: list[list[Any]]) -> list[list[Any]]:
    return [row[:] for row in matrix]


def create_empty_board() -> list[list[int]]:
    return [[0 for _ in range(BOARD_WIDTH)] for _ in range(BOARD_HEIGHT)]


def random_piece_type() -> str:
    return random.choice(PIECE_TYPES)


def create_piece(piece_type: str) -> "Piece":
    return Piece(type=piece_type, matrix=clone_matrix(PIECES[piece_type]))


def get_spawn_x(matrix: list[list[int]]) -> int:
    return (BOARD_WIDTH - len(matrix[0])) // 2


def rotate_matrix(matrix: list[list[int]]) -> list[list[int]]:
    size = len(matrix)
    rotated = [[0 for _ in range(size)] for _ in range(size)]
    for y in range(size):
        for x in range(size):
            rotated[x][size - 1 - y] = matrix[y][x]
    return rotated


def has_collision(board: list[list[Any]], matrix: list[list[int]], offset_x: int, offset_y: int) -> bool:
    for y in range(len(matrix)):
        for x in range(len(matrix[y])):
            if not matrix[y][x]:
                continue

            board_x = offset_x + x
            board_y = offset_y + y

            if board_x < 0 or board_x >= BOARD_WIDTH or board_y >= BOARD_HEIGHT:
                return True

            if board_y >= 0 and board[board_y][board_x]:
                return True

    return False


@dataclass
class Piece:
    type: str
    matrix: list[list[int]]


@dataclass
class PlayerState:
    label: str = "Player"
    board: list[list[Any]] = field(default_factory=create_empty_board)
    game_over: bool = False
    lines: int = 0
    next_piece_type: str = field(default_factory=random_piece_type)
    piece: Piece | None = None
    piece_x: int = 0
    piece_y: int = 0
    score: int = 0
    tick: int = 0


def merge_piece_into_board(state: PlayerState) -> None:
    assert state.piece is not None
    for y in range(len(state.piece.matrix)):
        for x in range(len(state.piece.matrix[y])):
            if not state.piece.matrix[y][x]:
                continue

            board_x = state.piece_x + x
            board_y = state.piece_y + y
            if board_y >= 0:
                state.board[board_y][board_x] = state.piece.type


def clear_completed_lines(board: list[list[Any]]) -> int:
    cleared = 0
    y = len(board) - 1
    while y >= 0:
        if all(board[y]):
            del board[y]
            board.insert(0, [0 for _ in range(BOARD_WIDTH)])
            cleared += 1
        else:
            y -= 1
    return cleared


def update_score(state: PlayerState, cleared_lines: int) -> None:
    points_by_lines = {1: 100, 2: 300, 3: 500, 4: 800}
    state.lines += cleared_lines
    state.score += points_by_lines.get(cleared_lines, 0)


def spawn_piece(state: PlayerState) -> None:
    piece = create_piece(state.next_piece_type or random_piece_type())
    state.piece = piece
    state.piece_x = get_spawn_x(piece.matrix)
    state.piece_y = 0
    state.next_piece_type = random_piece_type()

    if has_collision(state.board, piece.matrix, state.piece_x, state.piece_y):
        state.game_over = True


def lock_piece(state: PlayerState) -> None:
    merge_piece_into_board(state)
    cleared_lines = clear_completed_lines(state.board)
    update_score(state, cleared_lines)
    spawn_piece(state)


def try_move(
    state: PlayerState,
    next_x: int,
    next_y: int,
    next_matrix: list[list[int]] | None = None,
) -> bool:
    assert state.piece is not None
    next_matrix = next_matrix or state.piece.matrix

    if has_collision(state.board, next_matrix, next_x, next_y):
        return False

    state.piece_x = next_x
    state.piece_y = next_y
    state.piece.matrix = next_matrix
    return True


def create_player_state(label: str = "Player") -> PlayerState:
    state = PlayerState(label=label)
    spawn_piece(state)
    return state


def reset_player_state(state: PlayerState) -> None:
    state.board = create_empty_board()
    state.game_over = False
    state.lines = 0
    state.next_piece_type = random_piece_type()
    state.piece = None
    state.piece_x = 0
    state.piece_y = 0
    state.score = 0
    state.tick = 0
    spawn_piece(state)


def get_board_with_active_piece(state: PlayerState) -> list[list[Any]]:
    view = clone_matrix(state.board)
    if state.game_over or state.piece is None:
        return view

    for y in range(len(state.piece.matrix)):
        for x in range(len(state.piece.matrix[y])):
            if not state.piece.matrix[y][x]:
                continue

            board_x = state.piece_x + x
            board_y = state.piece_y + y
            if 0 <= board_y < BOARD_HEIGHT and 0 <= board_x < BOARD_WIDTH:
                view[board_y][board_x] = f"{state.piece.type}_active"

    return view


def get_player_snapshot(state: PlayerState) -> dict[str, Any]:
    assert state.piece is not None
    return {
        "board": get_board_with_active_piece(state),
        "currentPiece": {
            "matrix": clone_matrix(state.piece.matrix),
            "type": state.piece.type,
            "x": state.piece_x,
            "y": state.piece_y,
        },
        "gameOver": state.game_over,
        "label": state.label,
        "lines": state.lines,
        "nextPieceType": state.next_piece_type,
        "score": state.score,
        "tick": state.tick,
        "connected": True,
        "ready": True,
        "matchStarted": True,
        "matchState": "Local sandbox",
        "paused": False,
    }


def apply_command(state: PlayerState, command: str | None) -> dict[str, bool]:
    if command not in COMMANDS or state.game_over or state.piece is None:
        return {"accepted": False}

    if command == "left":
        return {"accepted": try_move(state, state.piece_x - 1, state.piece_y)}

    if command == "right":
        return {"accepted": try_move(state, state.piece_x + 1, state.piece_y)}

    if command == "down":
        if try_move(state, state.piece_x, state.piece_y + 1):
            return {"accepted": True}
        lock_piece(state)
        return {"accepted": True}

    if command == "drop":
        while try_move(state, state.piece_x, state.piece_y + 1):
            pass
        lock_piece(state)
        return {"accepted": True}

    rotated = rotate_matrix(state.piece.matrix)
    for offset in [0, -1, 1, -2, 2]:
        if try_move(state, state.piece_x + offset, state.piece_y, rotated):
            return {"accepted": True}

    return {"accepted": False}


def step_state(state: PlayerState) -> None:
    if state.game_over or state.piece is None:
        return

    state.tick += 1
    if not try_move(state, state.piece_x, state.piece_y + 1):
        lock_piece(state)
