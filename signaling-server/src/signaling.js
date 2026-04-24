// ============================================================================
// signaling.js — WebRTC signaling message router
//
// Message types (client → server):
//   device_register  { token, device_id, hostname }
//   viewer_join      { token }
//   viewer_watch     { deviceId }
//   offer            { deviceId, sdp }         (viewer → device)
//   answer           { deviceId, sdp }         (device → viewer)
//   ice_candidate    { deviceId, candidate }   (both directions)
//   activity_log     { device_id, ... }        (device → server → DB)
//
// Message types (server → client):
//   viewer_request   { viewerId }              (forwarded to device)
//   offer/answer/ice relayed transparently
//   device_disconnected { deviceId }
//   error            { code, message }
// ============================================================================
'use strict';

const { v4: uuidv4 }   = require('uuid');
const { verifyDeviceToken, verifyViewerToken } = require('./auth');
const dm = require('./deviceManager');

function send(ws, obj) {
  if (ws.readyState === 1 /* OPEN */) ws.send(JSON.stringify(obj));
}

function handleConnection(ws, req) {
  let role     = null;  // 'device' | 'viewer'
  let entityId = null;  // device_id or viewer_id

  ws.on('message', (raw) => {
    // Binary frames: device is streaming JPEG — forward to all viewers
    if (Buffer.isBuffer(raw) && role === 'device' && entityId) {
      const vids = dm.getViewers(entityId);
      for (const vid of vids) {
        const vc = dm.getViewerConn(vid);
        if (vc?.ws?.readyState === 1) vc.ws.send(raw);
      }
      return;
    }

    let msg;
    try { msg = JSON.parse(raw.toString()); }
    catch { return send(ws, { type: 'error', code: 'PARSE_ERROR', message: 'Invalid JSON' }); }

    switch (msg.type) {

      // ── Device registers itself ────────────────────────────────────────────
      case 'device_register': {
        try {
          const payload = verifyDeviceToken(msg.token);
          entityId = payload.device_id || msg.device_id;
          role     = 'device';
          dm.registerDevice(entityId, ws, { hostname: msg.hostname });
          send(ws, { type: 'registered', device_id: entityId });
        } catch (e) {
          send(ws, { type: 'error', code: 'AUTH_FAILED', message: e.message });
          ws.close(4001, 'Unauthorized');
        }
        break;
      }

      // ── Viewer (human) joins ───────────────────────────────────────────────
      case 'viewer_join': {
        try {
          verifyViewerToken(msg.token);
          entityId = uuidv4();
          role     = 'viewer';
          dm.registerViewer(entityId, ws);
          send(ws, { type: 'viewer_joined', viewer_id: entityId,
                     device_count: dm.deviceCount() });
        } catch (e) {
          send(ws, { type: 'error', code: 'AUTH_FAILED', message: e.message });
          ws.close(4001, 'Unauthorized');
        }
        break;
      }

      // ── Viewer requests to watch a device ──────────────────────────────────
      case 'viewer_watch': {
        if (role !== 'viewer') break;
        const dev = dm.getDevice(msg.deviceId);
        if (!dev) {
          send(ws, { type: 'error', code: 'DEVICE_NOT_FOUND', message: `Unknown device: ${msg.deviceId}` });
          break;
        }
        dm.attachViewerToDevice(entityId, msg.deviceId);
        // Notify device that a viewer wants to watch
        send(dev.ws, { type: 'viewer_request', viewerId: entityId });
        break;
      }

      // ── WebRTC offer (viewer → device) ─────────────────────────────────────
      case 'offer': {
        if (role !== 'viewer') break;
        const dev = dm.getDevice(msg.deviceId);
        if (dev) send(dev.ws, { type: 'offer', viewerId: entityId, sdp: msg.sdp });
        break;
      }

      // ── WebRTC answer (device → viewer) ────────────────────────────────────
      case 'answer': {
        if (role !== 'device') break;
        const vc = dm.getViewerConn(msg.viewerId);
        if (vc) send(vc.ws, { type: 'answer', deviceId: entityId, sdp: msg.sdp });
        break;
      }

      // ── ICE candidates (both directions) ──────────────────────────────────
      case 'ice_candidate': {
        if (role === 'viewer') {
          const dev = dm.getDevice(msg.deviceId);
          if (dev) send(dev.ws, { type: 'ice_candidate', viewerId: entityId, candidate: msg.candidate });
        } else if (role === 'device') {
          const vc = dm.getViewerConn(msg.viewerId);
          if (vc) send(vc.ws, { type: 'ice_candidate', deviceId: entityId, candidate: msg.candidate });
        }
        break;
      }

      // ── Viewer stops watching a device ───────────────────────────────────────────
      case 'viewer_unwatch': {
        if (role !== 'viewer' || !entityId) break;
        dm.detachViewerFromDevice(entityId);
        send(ws, { type: 'viewer_unwatched' });
        break;
      }

      // ── Viewer requests list of connected devices ─────────────────────────
      case 'device_list': {
        if (role !== 'viewer') break;
        const list = dm.getAllDevices().map(([id, d]) => ({
          device_id: id,
          hostname:  d.meta.hostname ?? null,
          viewer_count: dm.getViewers(id).size,
        }));
        send(ws, { type: 'device_list', devices: list });
        break;
      }

      // ── Application-level ping (keepalive for restrictive proxies) ─────────
      case 'ping':
        send(ws, { type: 'pong', ts: Date.now() });
        break;

      default:
        send(ws, { type: 'error', code: 'UNKNOWN_TYPE', message: `Unknown message type: ${msg.type}` });
    }
  });

  ws.on('close', () => {
    if (role === 'device' && entityId) dm.unregisterDevice(entityId);
    if (role === 'viewer' && entityId) dm.unregisterViewer(entityId);
  });

  ws.on('error', (err) => {
    console.error(`[signaling] WS error (${role}/${entityId}): ${err.message}`);
  });
}

module.exports = { handleConnection };
