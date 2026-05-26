from __future__ import annotations

from typing import Any

TARGET_COLUMNS = {
    "I": 4,
    "J": 1,
    "L": 8,
    "O": 5,
    "S": 3,
    "T": 6,
    "Z": 7,
}


def choose_command(snapshot: dict[str, Any]) -> str | None:
    if snapshot.get("gameOver"):
        return None

    current_piece = snapshot.get("currentPiece", {})
    piece_type = current_piece.get("type")
    piece_x = current_piece.get("x", 0)
    target_x = TARGET_COLUMNS.get(piece_type, 4)

    if piece_x < target_x:
        return "right"

    if piece_x > target_x:
        return "left"

    return "drop"
