// ============================================================================
// index.js — HTTP health/TURN endpoints + WebSocket signaling server
// ============================================================================
'use strict';

const http      = require('http');
const express   = require('express');
const helmet    = require('helmet');
const { WebSocketServer } = require('ws');
const { handleConnection } = require('./signaling');
const { generateCredentials } = require('./turnCredentials');
const { verifyViewerToken }   = require('./auth');
const { onConnect, onDisconnect } = require('./rateLimit');

const PORT            = Number(process.env.SIGNALING_PORT) || 4000;
const PING_INTERVAL   = Number(process.env.WS_PING_INTERVAL_MS) || 30_000;

// ── Express HTTP ─────────────────────────────────────────────────────────────
const app = express();
app.use(helmet());
app.use(express.json());

// Health
app.get('/health', (_req, res) =>
  res.json({ status: 'ok', ts: Date.now() }));

// TURN credential generation (requires valid viewer JWT in Authorization header)
app.get('/turn-credentials', (req, res) => {
  const auth = req.headers['authorization'] ?? '';
  const token = auth.startsWith('Bearer ') ? auth.slice(7) : '';
  let payload;
  try {
    payload = verifyViewerToken(token);
  } catch {
    return res.status(401).json({ error: 'Unauthorized' });
  }
  try {
    const creds = generateCredentials(payload.sub ?? 'viewer');
    return res.json(creds);
  } catch (e) {
    return res.status(503).json({ error: e.message });
  }
});

// ── WebSocket server ──────────────────────────────────────────────────────────
const server = http.createServer(app);
const wss    = new WebSocketServer({ server, path: '/ws' });

wss.on('connection', (ws, req) => {
  // Per-IP rate limit
  const ip = onConnect(req);
  if (!ip) {
    ws.close(1008, 'Too Many Connections');
    return;
  }

  // Ping-pong heartbeat to detect stale connections
  ws.isAlive = true;
  ws.on('pong', () => { ws.isAlive = true; });

  ws.on('close', () => onDisconnect(ip));

  handleConnection(ws, req);
});

// Terminate connections that miss two consecutive pings
const pingTimer = setInterval(() => {
  wss.clients.forEach((ws) => {
    if (!ws.isAlive) {
      ws.terminate();
      return;
    }
    ws.isAlive = false;
    ws.ping();
  });
}, PING_INTERVAL);

server.listen(PORT, () => {
  console.log(`[signaling] Listening on port ${PORT}`);
});

// ── Graceful shutdown ─────────────────────────────────────────────────────────
const shutdown = () => {
  console.log('[signaling] Shutting down…');
  clearInterval(pingTimer);
  wss.close(() => server.close(() => process.exit(0)));
  setTimeout(() => process.exit(1), 5000);
};
process.on('SIGTERM', shutdown);
process.on('SIGINT',  shutdown);
