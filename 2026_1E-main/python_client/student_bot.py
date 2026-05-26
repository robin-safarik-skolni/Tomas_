from __future__ import annotations

from typing import Any

BOARD_WIDTH = 10
BOARD_HEIGHT = 20

# Weight coefficients for the heuristic evaluation
HEIGHT_WEIGHT = -0.51
HOLES_WEIGHT = -0.76
BUMPINESS_WEIGHT = -0.18
COMPLETE_LINES_WEIGHT = 0.76

# Additional weights for strategic placement
EDGE_BONUS = 0.7  # Bonus for placing pieces near the edges (columns 0-1 and 8-9)
VERTICAL_BONUS = 0.5  # Bonus for vertical orientation of long pieces (I, L, J)


def choose_command(snapshot: dict[str, Any]) -> str | None:
    """
    Main entry point called by the game client.
    Returns the next command to execute: 'left', 'right', 'down', 'rotate', or 'drop'.
    
    Strategy: Each call, we re-evaluate the best final position for the current piece
    and return the next step needed to get there. This avoids the queue problem where
    the piece moves while we're executing pre-planned commands.
    """
    if snapshot.get("gameOver"):
        return None

    current_piece = snapshot.get("currentPiece", {})
    piece_type = current_piece.get("type")
    piece_x = current_piece.get("x", 0)
    piece_y = current_piece.get("y", 0)
    piece_matrix = current_piece.get("matrix", [])
    
    if not piece_type or not piece_matrix:
        return "drop"

    # Get the board without the active piece for simulation
    board = snapshot.get("board", [])
    # Create a clean board (remove active piece markers)
    clean_board = []
    for row in board:
        clean_row = []
        for cell in row:
            if cell == 0:
                clean_row.append(0)
            elif isinstance(cell, str) and cell.endswith("_active"):
                clean_row.append(0)
            else:
                clean_row.append(cell)
        clean_board.append(clean_row)

    # Find the best final position for this piece
    best_target_x, best_rotation = find_best_position(clean_board, piece_type, piece_matrix)
    
    # Get the matrix for the best rotation
    rotations = get_all_rotations(piece_type, piece_matrix)
    if best_rotation >= len(rotations):
        best_rotation = 0
    
    target_matrix = rotations[best_rotation]
    
    # Now figure out what command to issue RIGHT NOW
    # 1. If we need to rotate, do it
    # 2. If we need to move left/right, do it
    # 3. Otherwise, drop
    
    # Check current rotation state by comparing matrices
    current_rotation = get_current_rotation(piece_matrix, rotations)
    
    # If not at target rotation, rotate
    if current_rotation != best_rotation:
        return "rotate"
    
    # If not at target x, move horizontally
    if piece_x < best_target_x:
        # Check if moving right is valid
        if can_move(clean_board, target_matrix, piece_x + 1, piece_y):
            return "right"
        else:
            # Can't move right, maybe we should drop?
            return "drop"
    elif piece_x > best_target_x:
        # Check if moving left is valid
        if can_move(clean_board, target_matrix, piece_x - 1, piece_y):
            return "left"
        else:
            return "drop"
    
    # We're at the target position, drop!
    return "drop"


def get_current_rotation(current_matrix: list[list[int]], rotations: list[list[list[int]]]) -> int:
    """Find which rotation index matches the current matrix."""
    for i, rot in enumerate(rotations):
        if matrices_equal(current_matrix, rot):
            return i
    return 0


def matrices_equal(a: list[list[int]], b: list[list[int]]) -> bool:
    """Check if two matrices are equal."""
    if len(a) != len(b) or len(a[0]) != len(b[0]):
        return False
    for i in range(len(a)):
        for j in range(len(a[i])):
            if a[i][j] != b[i][j]:
                return False
    return True


def can_move(board: list[list[Any]], matrix: list[list[int]], new_x: int, new_y: int) -> bool:
    """Check if the piece can move to the new position."""
    return not has_collision(board, matrix, new_x, new_y)


def is_vertical_orientation(base_matrix: list[list[int]], current_matrix: list[list[int]]) -> bool:
    """Check if the current matrix is a vertical orientation compared to base."""
    base_height = len(base_matrix)
    base_width = len(base_matrix[0]) if base_matrix else 0
    current_height = len(current_matrix)
    current_width = len(current_matrix[0]) if current_matrix else 0
    
    # If current is taller than wide (compared to base), it's vertical
    # For pieces like I: base is 1x4 (horizontal), vertical is 4x1
    return current_height > current_width and base_width > base_height


def find_best_position(board: list[list[Any]], piece_type: str, base_matrix: list[list[int]]) -> tuple[int, int]:
    """Find the best x position and rotation for the piece.
    Returns (target_x, rotation_index).
    
    Strategy: Prefer vertical orientation for long pieces (I, L, J) and
    placement near the edges (columns 0-1 and 8-9).
    """
    rotations = get_all_rotations(piece_type, base_matrix)
    
    best_score = float('-inf')
    best_target_x = 4  # Default center position
    best_rotation = 0
    
    # Check if this is a long piece that benefits from vertical placement
    is_long_piece = piece_type in ["I", "L", "J"]
    
    for rot_idx, matrix in enumerate(rotations):
        piece_width = len(matrix[0])
        piece_height = len(matrix)
        
        # Check if this rotation is vertical (taller than wide)
        is_vertical = piece_height > piece_width
        
        # Try each possible x position where the piece can fit
        for target_x in range(BOARD_WIDTH - piece_width + 1):
            # Check if the piece fits at this x position at the top
            if has_collision(board, matrix, target_x, 0):
                continue
            
            # Get the drop position
            drop_y = get_drop_y(board, matrix, target_x)
            
            # Merge the piece and clear lines
            new_board = merge_piece(board, matrix, target_x, drop_y, piece_type)
            new_board, _ = clear_lines(new_board)
            
            # Evaluate the resulting board
            score = evaluate_board(new_board)
            
            # Add bonus for vertical orientation of long pieces
            if is_long_piece and is_vertical:
                score += VERTICAL_BONUS
            
            # Add bonus for edge placement (columns 0-1 and 8-9)
            # Calculate the rightmost column the piece will occupy
            rightmost_col = target_x + piece_width - 1
            if target_x <= 1 or rightmost_col >= 8:
                score += EDGE_BONUS
            
            if score > best_score:
                best_score = score
                best_target_x = target_x
                best_rotation = rot_idx
    
    return best_target_x, best_rotation


def rotate_matrix(matrix: list[list[int]]) -> list[list[int]]:
    """Rotate a matrix 90 degrees clockwise."""
    rows = len(matrix)
    cols = len(matrix[0])
    rotated = [[0 for _ in range(rows)] for _ in range(cols)]
    for r in range(rows):
        for c in range(cols):
            rotated[c][rows - 1 - r] = matrix[r][c]
    return rotated


def get_all_rotations(piece_type: str, base_matrix: list[list[int]]) -> list[list[list[int]]]:
    """Get all unique rotations of a piece."""
    rotations = []
    matrix = [row[:] for row in base_matrix]
    
    for _ in range(4):
        # Check if this rotation is unique
        is_unique = True
        for existing in rotations:
            if len(existing) == len(matrix) and len(existing[0]) == len(matrix[0]):
                if existing == matrix:
                    is_unique = False
                    break
        
        if is_unique:
            rotations.append([row[:] for row in matrix])
        
        matrix = rotate_matrix(matrix)
    
    return rotations


def has_collision(board: list[list[Any]], matrix: list[list[int]], offset_x: int, offset_y: int) -> bool:
    """Check if the piece at the given position collides with the board."""
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


def get_drop_y(board: list[list[Any]], matrix: list[list[int]], pos_x: int) -> int:
    """Get the y position where the piece will land when dropped."""
    y = 0
    while not has_collision(board, matrix, pos_x, y + 1):
        y += 1
    return y


def merge_piece(board: list[list[Any]], matrix: list[list[int]], pos_x: int, pos_y: int, piece_type: str) -> list[list[Any]]:
    """Merge the piece into the board and return a new board."""
    new_board = [row[:] for row in board]
    for y in range(len(matrix)):
        for x in range(len(matrix[y])):
            if not matrix[y][x]:
                continue
            
            board_x = pos_x + x
            board_y = pos_y + y
            if 0 <= board_y < BOARD_HEIGHT and 0 <= board_x < BOARD_WIDTH:
                new_board[board_y][board_x] = piece_type
    return new_board


def clear_lines(board: list[list[Any]]) -> tuple[list[list[Any]], int]:
    """Clear completed lines and return the new board and number of cleared lines."""
    new_board = [row[:] for row in board]
    cleared = 0
    y = BOARD_HEIGHT - 1
    while y >= 0:
        if all(new_board[y]):
            del new_board[y]
            new_board.insert(0, [0 for _ in range(BOARD_WIDTH)])
            cleared += 1
        else:
            y -= 1
    return new_board, cleared


def calculate_heights(board: list[list[Any]]) -> list[int]:
    """Calculate the height of each column."""
    heights = [0] * BOARD_WIDTH
    for x in range(BOARD_WIDTH):
        for y in range(BOARD_HEIGHT):
            if board[y][x]:
                heights[x] = BOARD_HEIGHT - y
                break
    return heights


def calculate_holes(board: list[list[Any]]) -> int:
    """Count the number of holes (empty cells with filled cells above)."""
    holes = 0
    for x in range(BOARD_WIDTH):
        found_block = False
        for y in range(BOARD_HEIGHT):
            if board[y][x]:
                found_block = True
            elif found_block:
                holes += 1
    return holes


def calculate_bumpiness(heights: list[int]) -> int:
    """Calculate bumpiness (sum of height differences between adjacent columns)."""
    bumpiness = 0
    for i in range(len(heights) - 1):
        bumpiness += abs(heights[i] - heights[i + 1])
    return bumpiness


def evaluate_board(board: list[list[Any]]) -> float:
    """Evaluate the board state using a heuristic function."""
    heights = calculate_heights(board)
    holes = calculate_holes(board)
    bumpiness = calculate_bumpiness(heights)
    
    # Count complete lines
    complete_lines = 0
    for y in range(BOARD_HEIGHT):
        if all(board[y]):
            complete_lines += 1
    
    max_height = max(heights) if heights else 0
    
    score = (
        HEIGHT_WEIGHT * max_height +
        HOLES_WEIGHT * holes +
        BUMPINESS_WEIGHT * bumpiness +
        COMPLETE_LINES_WEIGHT * complete_lines
    )
    
    return score