const COLORS = {
  0: "#161917",
  I: "#59d7ff",
  I_active: "#a8f0ff",
  J: "#496aff",
  J_active: "#a7b6ff",
  L: "#ff9b4a",
  L_active: "#ffd1a2",
  O: "#ffe066",
  O_active: "#fff1ad",
  S: "#65db7d",
  S_active: "#b8efc4",
  T: "#bf6bff",
  T_active: "#e2bbff",
  Z: "#ff6464",
  Z_active: "#ffb2b2",
};

const canvases = [document.querySelector("#player1Canvas"), document.querySelector("#player2Canvas")];
const contexts = canvases.map((canvas) => canvas.getContext("2d"));

function drawBoard(context, board) {
  const cellWidth = context.canvas.width / board[0].length;
  const cellHeight = context.canvas.height / board.length;

  context.clearRect(0, 0, context.canvas.width, context.canvas.height);

  for (let y = 0; y < board.length; y += 1) {
    for (let x = 0; x < board[y].length; x += 1) {
      context.fillStyle = COLORS[board[y][x]] ?? COLORS[0];
      context.fillRect(x * cellWidth, y * cellHeight, cellWidth - 1, cellHeight - 1);
    }
  }
}

function updatePlayerCard(player, index, session) {
  const playerNumber = index + 1;
  document.querySelector(`#player${playerNumber}Score`).textContent = String(player.score);
  document.querySelector(`#player${playerNumber}Lines`).textContent = String(player.lines);
  document.querySelector(`#player${playerNumber}Next`).textContent = player.nextPieceType;
  const status = player.gameOver
    ? "Game over"
    : session.matchStarted
      ? session.paused
        ? "Paused"
        : "Running"
      : "Waiting";
  document.querySelector(`#player${playerNumber}Status`).textContent = status;
  document.querySelector(`#player${playerNumber}Connected`).textContent = player.connected ? "Yes" : "No";
  document.querySelector(`#player${playerNumber}Ready`).textContent = player.ready ? "Yes" : "No";
  drawBoard(contexts[index], player.board);
}

function formatDate(value) {
  return new Date(value).toLocaleString();
}

async function refresh() {
  const response = await fetch("/api/session");
  const session = await response.json();

  document.querySelector("#tickRate").textContent = `${session.tickMs} ms`;
  document.querySelector("#matchState").textContent = session.matchState;
  document.querySelector("#startedAt").textContent = session.startedAt ? formatDate(session.startedAt) : "Not started yet";
  document.querySelector("#lastReset").textContent = formatDate(session.lastResetAt);

  session.players.forEach((player, index) => updatePlayerCard(player, index, session));
}

async function post(pathname) {
  await fetch(pathname, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
  });
  refresh();
}

document.querySelector("#resetButton").addEventListener("click", () => post("/api/session/reset"));
document.querySelector("#pauseButton").addEventListener("click", () => post("/api/session/pause"));
document.querySelector("#resumeButton").addEventListener("click", () => post("/api/session/resume"));

refresh();
setInterval(refresh, 200);
