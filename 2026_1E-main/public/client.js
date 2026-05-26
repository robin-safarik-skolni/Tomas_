import {
  COMMANDS,
  TICK_MS,
  applyCommand,
  createPlayerState,
  getPlayerSnapshot,
  resetPlayerState,
  stepState,
} from "./shared/tetris-engine.js";
import { chooseCommand } from "./student-bot.js";

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

const params = new URLSearchParams(window.location.search);

const elements = {
  apiBaseInput: document.querySelector("#apiBaseInput"),
  autoplayToggle: document.querySelector("#autoplayToggle"),
  botLog: document.querySelector("#botLog"),
  canvas: document.querySelector("#clientCanvas"),
  clientLines: document.querySelector("#clientLines"),
  clientNext: document.querySelector("#clientNext"),
  clientScore: document.querySelector("#clientScore"),
  clientStatus: document.querySelector("#clientStatus"),
  localResetButton: document.querySelector("#localResetButton"),
  modeSelect: document.querySelector("#modeSelect"),
  playerIndicator: document.querySelector("#playerIndicator"),
  playerSelect: document.querySelector("#playerSelect"),
  readyToggle: document.querySelector("#readyToggle"),
  remoteLobbyStatus: document.querySelector("#remoteLobbyStatus"),
};

elements.playerSelect.value = params.get("player") === "2" ? "2" : "1";

const context = elements.canvas.getContext("2d");
const localState = createPlayerState("Local Sandbox");

const appState = {
  autoplay: false,
  lastRenderedSnapshot: getPlayerSnapshot(localState),
  localTickHandle: null,
  mode: "remote",
  remoteReady: false,
  remotePollHandle: null,
};

function getApiBase() {
  return elements.apiBaseInput.value.trim().replace(/\/$/, "");
}

function getPlayerId() {
  return Number(elements.playerSelect.value);
}

function setBotLog(message) {
  elements.botLog.textContent = message;
}

function drawBoard(board) {
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

function renderSnapshot(snapshot) {
  appState.lastRenderedSnapshot = snapshot;
  elements.playerIndicator.textContent = appState.mode === "local" ? "Local" : String(getPlayerId());
  elements.clientScore.textContent = String(snapshot.score);
  elements.clientLines.textContent = String(snapshot.lines);
  elements.clientNext.textContent = snapshot.nextPieceType;
  elements.clientStatus.textContent = snapshot.gameOver
    ? "Game over"
    : snapshot.matchStarted
      ? snapshot.paused
        ? "Paused"
        : "Running"
      : "Waiting";
  drawBoard(snapshot.board);
  renderRemoteLobby(snapshot);
}

function renderRemoteLobby(snapshot) {
  if (appState.mode === "local") {
    elements.remoteLobbyStatus.textContent = "Local sandbox mode does not use the master lobby.";
    elements.readyToggle.textContent = "Mark ready";
    elements.readyToggle.disabled = true;
    return;
  }

  appState.remoteReady = Boolean(snapshot.ready);
  elements.readyToggle.disabled = false;
  elements.readyToggle.textContent = snapshot.ready ? "Cancel ready" : "Mark ready";

  if (!snapshot.matchStarted) {
    elements.remoteLobbyStatus.textContent = `Connected: ${snapshot.connected ? "yes" : "no"} | Ready: ${snapshot.ready ? "yes" : "no"} | Match state: ${snapshot.matchState}`;
    return;
  }

  elements.remoteLobbyStatus.textContent = `Connected: ${snapshot.connected ? "yes" : "no"} | Match state: ${snapshot.matchState}`;
}

async function fetchRemoteSnapshot() {
  const base = getApiBase();
  const response = await fetch(`${base}/api/players/${getPlayerId()}/state`);
  const snapshot = await response.json();
  renderSnapshot(snapshot);
  return snapshot;
}

function refreshLocalSnapshot() {
  renderSnapshot(getPlayerSnapshot(localState));
}

async function sendRemoteCommand(command) {
  const base = getApiBase();
  const response = await fetch(`${base}/api/players/${getPlayerId()}/command`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ command }),
  });
  const payload = await response.json();
  const snapshot = payload.player ?? (await fetchRemoteSnapshot());
  setBotLog(`Remote command: ${command}\nScore: ${snapshot.score}\nLines: ${snapshot.lines}`);
  renderSnapshot(snapshot);
}

async function setRemoteReady(ready) {
  const base = getApiBase();
  const response = await fetch(`${base}/api/players/${getPlayerId()}/ready`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ ready }),
  });
  const snapshot = await response.json();
  renderSnapshot(snapshot);
  setBotLog(
    ready
      ? "Ready sent to master server.\nWaiting for the other player."
      : "Ready cancelled.\nThe match will stay in the lobby."
  );
}

function sendLocalCommand(command) {
  applyCommand(localState, command);
  const snapshot = getPlayerSnapshot(localState);
  renderSnapshot(snapshot);
  setBotLog(`Local command: ${command}\nScore: ${snapshot.score}\nLines: ${snapshot.lines}`);
}

function stopRemotePolling() {
  if (appState.remotePollHandle) {
    clearInterval(appState.remotePollHandle);
    appState.remotePollHandle = null;
  }
}

function stopLocalTicks() {
  if (appState.localTickHandle) {
    clearInterval(appState.localTickHandle);
    appState.localTickHandle = null;
  }
}

function startRemotePolling() {
  stopRemotePolling();
  fetchRemoteSnapshot().catch((error) => {
    setBotLog(`Remote fetch failed.\n${error.message}`);
  });

  appState.remotePollHandle = setInterval(() => {
    fetchRemoteSnapshot().catch((error) => {
      setBotLog(`Remote fetch failed.\n${error.message}`);
    });
  }, 200);
}

function startLocalTicks() {
  stopLocalTicks();
  refreshLocalSnapshot();

  appState.localTickHandle = setInterval(() => {
    stepState(localState);
    refreshLocalSnapshot();
  }, TICK_MS);
}

function applyMode(mode) {
  appState.mode = mode;

  if (mode === "remote") {
    stopLocalTicks();
    startRemotePolling();
  } else {
    stopRemotePolling();
    startLocalTicks();
    renderRemoteLobby({});
  }
}

async function runBotStep() {
  const snapshot = appState.mode === "remote" ? await fetchRemoteSnapshot() : getPlayerSnapshot(localState);
  if (appState.mode === "remote" && (!snapshot.matchStarted || snapshot.paused || !snapshot.ready)) {
    return;
  }

  const command = chooseCommand(snapshot);

  if (!command || !COMMANDS.includes(command)) {
    setBotLog(`Bot skipped turn.\nSuggested command: ${String(command)}`);
    return;
  }

  if (appState.mode === "remote") {
    await sendRemoteCommand(command);
  } else {
    sendLocalCommand(command);
  }
}

function toggleAutoplay() {
  appState.autoplay = !appState.autoplay;
  elements.autoplayToggle.textContent = appState.autoplay ? "Stop bot" : "Start bot";
}

setInterval(() => {
  if (!appState.autoplay) {
    return;
  }

  runBotStep().catch((error) => {
    setBotLog(`Bot failed.\n${error.message}`);
  });
}, 180);

elements.modeSelect.addEventListener("change", (event) => {
  applyMode(event.target.value);
});

elements.playerSelect.addEventListener("change", () => {
  appState.remoteReady = false;
  if (appState.mode === "remote") {
    fetchRemoteSnapshot().catch((error) => {
      setBotLog(`Remote fetch failed.\n${error.message}`);
    });
  }
});

elements.autoplayToggle.addEventListener("click", toggleAutoplay);
elements.readyToggle.addEventListener("click", () => {
  if (appState.mode !== "remote") {
    return;
  }

  setRemoteReady(!appState.remoteReady).catch((error) => {
    setBotLog(`Ready update failed.\n${error.message}`);
  });
});

elements.localResetButton.addEventListener("click", () => {
  resetPlayerState(localState);
  refreshLocalSnapshot();
  setBotLog("Local sandbox reset.");
});

document.querySelectorAll("[data-command]").forEach((button) => {
  button.addEventListener("click", () => {
    const command = button.getAttribute("data-command");
    if (!COMMANDS.includes(command)) {
      return;
    }

    if (appState.mode === "remote") {
      sendRemoteCommand(command).catch((error) => {
        setBotLog(`Remote command failed.\n${error.message}`);
      });
    } else {
      sendLocalCommand(command);
    }
  });
});

setBotLog("Edit /public/student-bot.js to change the AI strategy.");
applyMode(elements.modeSelect.value);
