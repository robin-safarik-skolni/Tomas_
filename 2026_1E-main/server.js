import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import {
  TICK_MS,
  applyCommand,
  createPlayerState,
  getPlayerSnapshot,
  resetPlayerState,
  stepState,
} from "./public/shared/tetris-engine.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const publicDir = path.join(__dirname, "public");

const players = [createPlayerState("Player 1"), createPlayerState("Player 2")];
const playerSlots = [
  { ready: false, lastSeenAt: null },
  { ready: false, lastSeenAt: null },
];
const CONNECTION_TIMEOUT_MS = 2500;

const session = {
  matchStarted: false,
  paused: false,
  lastResetAt: new Date().toISOString(),
  startedAt: null,
};

const mimeTypes = {
  ".css": "text/css; charset=utf-8",
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
};

function writeJson(response, statusCode, payload) {
  response.writeHead(statusCode, {
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
    "Access-Control-Allow-Origin": "*",
    "Content-Type": "application/json; charset=utf-8",
  });
  response.end(JSON.stringify(payload));
}

function writeText(response, statusCode, text) {
  response.writeHead(statusCode, {
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
    "Access-Control-Allow-Origin": "*",
    "Content-Type": "text/plain; charset=utf-8",
  });
  response.end(text);
}

async function readJsonBody(request) {
  const chunks = [];

  for await (const chunk of request) {
    chunks.push(chunk);
  }

  if (chunks.length === 0) {
    return {};
  }

  return JSON.parse(Buffer.concat(chunks).toString("utf8"));
}

function getSessionSnapshot() {
  return {
    matchStarted: session.matchStarted,
    matchState: getMatchState(),
    paused: session.paused,
    lastResetAt: session.lastResetAt,
    startedAt: session.startedAt,
    tickMs: TICK_MS,
    players: players.map((player, index) => ({
      ...getPlayerSnapshot(player),
      connected: isPlayerConnected(index),
      ready: playerSlots[index].ready,
    })),
  };
}

function parsePlayerId(urlPath) {
  const match = urlPath.match(/^\/api\/players\/(\d+)\/(command|ready|state)$/);
  if (!match) {
    return null;
  }

  const playerIndex = Number(match[1]) - 1;
  if (!players[playerIndex]) {
    return null;
  }

  return {
    action: match[2],
    playerIndex,
  };
}

function isPlayerConnected(playerIndex) {
  const lastSeenAt = playerSlots[playerIndex].lastSeenAt;
  if (!lastSeenAt) {
    return false;
  }

  return Date.now() - lastSeenAt < CONNECTION_TIMEOUT_MS;
}

function getMatchState() {
  if (!session.matchStarted) {
    return "Waiting for both players";
  }

  if (session.paused) {
    return "Paused";
  }

  return "Running";
}

function markPlayerSeen(playerIndex) {
  playerSlots[playerIndex].lastSeenAt = Date.now();
}

function clearReadyFlags() {
  playerSlots.forEach((slot) => {
    slot.ready = false;
  });
}

function enterWaitingRoom() {
  players.forEach(resetPlayerState);
  clearReadyFlags();
  session.matchStarted = false;
  session.paused = false;
  session.startedAt = null;
  session.lastResetAt = new Date().toISOString();
}

function tryStartMatch() {
  const everyoneConnected = playerSlots.every((slot, index) => slot.ready && isPlayerConnected(index));
  if (!everyoneConnected || session.matchStarted) {
    return false;
  }

  players.forEach(resetPlayerState);
  session.matchStarted = true;
  session.paused = false;
  session.startedAt = new Date().toISOString();
  session.lastResetAt = session.startedAt;
  return true;
}

function resetSession() {
  enterWaitingRoom();
}

function getPlayerStateResponse(playerIndex) {
  return {
    ...getPlayerSnapshot(players[playerIndex]),
    connected: isPlayerConnected(playerIndex),
    ready: playerSlots[playerIndex].ready,
    matchStarted: session.matchStarted,
    matchState: getMatchState(),
    paused: session.paused,
  };
}

async function serveStatic(requestPath, response) {
  const normalizedPath = requestPath === "/" ? "/index.html" : requestPath;
  const safePath = path.normalize(normalizedPath).replace(/^(\.\.[/\\])+/, "").replace(/^[/\\]+/, "");
  const filePath = path.join(publicDir, safePath);

  if (!filePath.startsWith(publicDir)) {
    writeText(response, 403, "Forbidden");
    return;
  }

  try {
    const file = await readFile(filePath);
    const extension = path.extname(filePath);
    response.writeHead(200, {
      "Content-Type": mimeTypes[extension] ?? "application/octet-stream",
    });
    response.end(file);
  } catch {
    writeText(response, 404, "Not found");
  }
}

const server = createServer(async (request, response) => {
  if (!request.url || !request.method) {
    writeText(response, 400, "Bad request");
    return;
  }

  const url = new URL(request.url, "http://localhost");

  if (request.method === "OPTIONS") {
    response.writeHead(204, {
      "Access-Control-Allow-Headers": "Content-Type",
      "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
      "Access-Control-Allow-Origin": "*",
    });
    response.end();
    return;
  }

  if (url.pathname === "/api/session" && request.method === "GET") {
    writeJson(response, 200, getSessionSnapshot());
    return;
  }

  if (url.pathname === "/api/session/reset" && request.method === "POST") {
    resetSession();
    writeJson(response, 200, getSessionSnapshot());
    return;
  }

  if (url.pathname === "/api/session/pause" && request.method === "POST") {
    if (!session.matchStarted) {
      writeJson(response, 409, {
        error: "Match has not started yet",
        session: getSessionSnapshot(),
      });
      return;
    }

    session.paused = true;
    writeJson(response, 200, getSessionSnapshot());
    return;
  }

  if (url.pathname === "/api/session/resume" && request.method === "POST") {
    if (!session.matchStarted) {
      writeJson(response, 409, {
        error: "Match has not started yet",
        session: getSessionSnapshot(),
      });
      return;
    }

    session.paused = false;
    writeJson(response, 200, getSessionSnapshot());
    return;
  }

  const playerRoute = parsePlayerId(url.pathname);
  if (playerRoute && request.method === "GET" && playerRoute.action === "state") {
    markPlayerSeen(playerRoute.playerIndex);
    writeJson(response, 200, getPlayerStateResponse(playerRoute.playerIndex));
    return;
  }

  if (playerRoute && request.method === "POST" && playerRoute.action === "ready") {
    try {
      const body = await readJsonBody(request);
      markPlayerSeen(playerRoute.playerIndex);
      playerSlots[playerRoute.playerIndex].ready = Boolean(body.ready);
      tryStartMatch();
      writeJson(response, 200, getPlayerStateResponse(playerRoute.playerIndex));
    } catch (error) {
      writeJson(response, 400, {
        error: error instanceof Error ? error.message : "Invalid request",
      });
    }
    return;
  }

  if (playerRoute && request.method === "POST" && playerRoute.action === "command") {
    try {
      markPlayerSeen(playerRoute.playerIndex);

      if (!session.matchStarted || session.paused) {
        writeJson(response, 409, {
          accepted: false,
          command: null,
          error: !session.matchStarted ? "Match is waiting for players" : "Match is paused",
          player: getPlayerStateResponse(playerRoute.playerIndex),
        });
        return;
      }

      const body = await readJsonBody(request);
      const result = applyCommand(players[playerRoute.playerIndex], body.command);
      writeJson(response, 200, {
        accepted: result.accepted,
        command: body.command ?? null,
        player: getPlayerStateResponse(playerRoute.playerIndex),
      });
    } catch (error) {
      writeJson(response, 400, {
        error: error instanceof Error ? error.message : "Invalid request",
      });
    }
    return;
  }

  serveStatic(url.pathname, response);
});

setInterval(() => {
  if (!session.matchStarted || session.paused) {
    return;
  }

  players.forEach(stepState);
}, TICK_MS);

const port = Number(process.env.PORT ?? 10000);

server.listen(port, () => {
  console.log(`Tetris AI lab running on http://localhost:${port}`);
});
