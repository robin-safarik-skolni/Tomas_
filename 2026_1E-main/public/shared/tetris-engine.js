export const BOARD_WIDTH = 10;
export const BOARD_HEIGHT = 20;
export const TICK_MS = 700;
export const COMMANDS = ["left", "right", "down", "rotate", "drop"];

const PIECE_TYPES = ["I", "J", "L", "O", "S", "T", "Z"];

const PIECES = {
  I: [
    [0, 0, 0, 0],
    [1, 1, 1, 1],
    [0, 0, 0, 0],
    [0, 0, 0, 0],
  ],
  J: [
    [1, 0, 0],
    [1, 1, 1],
    [0, 0, 0],
  ],
  L: [
    [0, 0, 1],
    [1, 1, 1],
    [0, 0, 0],
  ],
  O: [
    [1, 1],
    [1, 1],
  ],
  S: [
    [0, 1, 1],
    [1, 1, 0],
    [0, 0, 0],
  ],
  T: [
    [0, 1, 0],
    [1, 1, 1],
    [0, 0, 0],
  ],
  Z: [
    [1, 1, 0],
    [0, 1, 1],
    [0, 0, 0],
  ],
};

function cloneMatrix(matrix) {
  return matrix.map((row) => [...row]);
}

function createEmptyBoard() {
  return Array.from({ length: BOARD_HEIGHT }, () => Array(BOARD_WIDTH).fill(0));
}

function randomPieceType() {
  return PIECE_TYPES[Math.floor(Math.random() * PIECE_TYPES.length)];
}

function createPiece(type) {
  return {
    matrix: cloneMatrix(PIECES[type]),
    type,
  };
}

function getSpawnX(matrix) {
  return Math.floor((BOARD_WIDTH - matrix[0].length) / 2);
}

function rotateMatrix(matrix) {
  const size = matrix.length;
  const rotated = Array.from({ length: size }, () => Array(size).fill(0));

  for (let y = 0; y < size; y += 1) {
    for (let x = 0; x < size; x += 1) {
      rotated[x][size - 1 - y] = matrix[y][x];
    }
  }

  return rotated;
}

function hasCollision(board, matrix, offsetX, offsetY) {
  for (let y = 0; y < matrix.length; y += 1) {
    for (let x = 0; x < matrix[y].length; x += 1) {
      if (!matrix[y][x]) {
        continue;
      }

      const boardX = offsetX + x;
      const boardY = offsetY + y;

      if (boardX < 0 || boardX >= BOARD_WIDTH || boardY >= BOARD_HEIGHT) {
        return true;
      }

      if (boardY >= 0 && board[boardY][boardX]) {
        return true;
      }
    }
  }

  return false;
}

function mergePieceIntoBoard(state) {
  for (let y = 0; y < state.piece.matrix.length; y += 1) {
    for (let x = 0; x < state.piece.matrix[y].length; x += 1) {
      if (!state.piece.matrix[y][x]) {
        continue;
      }

      const boardX = state.pieceX + x;
      const boardY = state.pieceY + y;
      if (boardY >= 0) {
        state.board[boardY][boardX] = state.piece.type;
      }
    }
  }
}

function clearCompletedLines(board) {
  let cleared = 0;

  for (let y = board.length - 1; y >= 0; y -= 1) {
    if (board[y].every(Boolean)) {
      board.splice(y, 1);
      board.unshift(Array(BOARD_WIDTH).fill(0));
      cleared += 1;
      y += 1;
    }
  }

  return cleared;
}

function updateScore(state, clearedLines) {
  const pointsByLines = {
    1: 100,
    2: 300,
    3: 500,
    4: 800,
  };

  state.lines += clearedLines;
  state.score += pointsByLines[clearedLines] ?? 0;
}

function spawnPiece(state) {
  const piece = createPiece(state.nextPieceType ?? randomPieceType());
  state.piece = piece;
  state.pieceX = getSpawnX(piece.matrix);
  state.pieceY = 0;
  state.nextPieceType = randomPieceType();

  if (hasCollision(state.board, piece.matrix, state.pieceX, state.pieceY)) {
    state.gameOver = true;
  }
}

function lockPiece(state) {
  mergePieceIntoBoard(state);
  const clearedLines = clearCompletedLines(state.board);
  updateScore(state, clearedLines);
  spawnPiece(state);
}

function tryMove(state, nextX, nextY, nextMatrix = state.piece.matrix) {
  if (hasCollision(state.board, nextMatrix, nextX, nextY)) {
    return false;
  }

  state.pieceX = nextX;
  state.pieceY = nextY;
  state.piece.matrix = nextMatrix;
  return true;
}

export function createPlayerState(label = "Player") {
  const state = {
    board: createEmptyBoard(),
    gameOver: false,
    label,
    lines: 0,
    nextPieceType: randomPieceType(),
    piece: null,
    pieceX: 0,
    pieceY: 0,
    score: 0,
    tick: 0,
  };

  spawnPiece(state);
  return state;
}

export function resetPlayerState(state) {
  state.board = createEmptyBoard();
  state.gameOver = false;
  state.lines = 0;
  state.nextPieceType = randomPieceType();
  state.piece = null;
  state.pieceX = 0;
  state.pieceY = 0;
  state.score = 0;
  state.tick = 0;
  spawnPiece(state);
}

export function getBoardWithActivePiece(state) {
  const view = cloneMatrix(state.board);

  if (state.gameOver || !state.piece) {
    return view;
  }

  for (let y = 0; y < state.piece.matrix.length; y += 1) {
    for (let x = 0; x < state.piece.matrix[y].length; x += 1) {
      if (!state.piece.matrix[y][x]) {
        continue;
      }

      const boardX = state.pieceX + x;
      const boardY = state.pieceY + y;
      if (boardY >= 0 && boardY < BOARD_HEIGHT && boardX >= 0 && boardX < BOARD_WIDTH) {
        view[boardY][boardX] = `${state.piece.type}_active`;
      }
    }
  }

  return view;
}

export function getPlayerSnapshot(state) {
  return {
    board: getBoardWithActivePiece(state),
    currentPiece: {
      matrix: cloneMatrix(state.piece.matrix),
      type: state.piece.type,
      x: state.pieceX,
      y: state.pieceY,
    },
    gameOver: state.gameOver,
    label: state.label,
    lines: state.lines,
    nextPieceType: state.nextPieceType,
    score: state.score,
    tick: state.tick,
  };
}

export function applyCommand(state, command) {
  if (!COMMANDS.includes(command) || state.gameOver) {
    return { accepted: false };
  }

  if (command === "left") {
    return { accepted: tryMove(state, state.pieceX - 1, state.pieceY) };
  }

  if (command === "right") {
    return { accepted: tryMove(state, state.pieceX + 1, state.pieceY) };
  }

  if (command === "down") {
    if (tryMove(state, state.pieceX, state.pieceY + 1)) {
      return { accepted: true };
    }

    lockPiece(state);
    return { accepted: true };
  }

  if (command === "drop") {
    while (tryMove(state, state.pieceX, state.pieceY + 1)) {
      continue;
    }

    lockPiece(state);
    return { accepted: true };
  }

  const rotated = rotateMatrix(state.piece.matrix);
  const kickOffsets = [0, -1, 1, -2, 2];

  for (const offset of kickOffsets) {
    if (tryMove(state, state.pieceX + offset, state.pieceY, rotated)) {
      return { accepted: true };
    }
  }

  return { accepted: false };
}

export function stepState(state) {
  if (state.gameOver) {
    return;
  }

  state.tick += 1;

  if (!tryMove(state, state.pieceX, state.pieceY + 1)) {
    lockPiece(state);
  }
}
