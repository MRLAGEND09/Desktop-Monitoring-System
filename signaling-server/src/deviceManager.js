// ============================================================================
// deviceManager.js — In-memory registry of connected devices and viewers
// ============================================================================
'use strict';

/** @type {Map<string, { ws: WebSocket, meta: Object }>} */
const devices = new Map();   // device_id → { ws, meta }

/** @type {Map<string, Set<string>>} */
const viewers = new Map();   // device_id → Set<viewer_id>

/** @type {Map<string, { ws: WebSocket, deviceId: string|null }>} */
const viewerConns = new Map(); // viewer_id → { ws, deviceId }

function registerDevice(deviceId, ws, meta = {}) {
  devices.set(deviceId, { ws, meta });
  console.log(`[dm] Device registered: ${deviceId} (${meta.hostname ?? '?'})`);
}

function unregisterDevice(deviceId) {
  devices.delete(deviceId);
  const vids = viewers.get(deviceId);
  if (vids) {
    for (const vid of vids) {
      const vc = viewerConns.get(vid);
      if (vc?.ws?.readyState === 1 /* OPEN */) {
        vc.ws.send(JSON.stringify({ type: 'device_disconnected', deviceId }));
      }
    }
    viewers.delete(deviceId);
  }
  console.log(`[dm] Device unregistered: ${deviceId}`);
}

function registerViewer(viewerId, ws) {
  viewerConns.set(viewerId, { ws, deviceId: null });
}

function unregisterViewer(viewerId) {
  const vc = viewerConns.get(viewerId);
  if (vc?.deviceId) {
    const vids = viewers.get(vc.deviceId);
    if (vids) vids.delete(viewerId);
  }
  viewerConns.delete(viewerId);
}

function attachViewerToDevice(viewerId, deviceId) {
  const vc = viewerConns.get(viewerId);
  if (vc) vc.deviceId = deviceId;

  if (!viewers.has(deviceId)) viewers.set(deviceId, new Set());
  viewers.get(deviceId).add(viewerId);
}

function getDevice(deviceId)      { return devices.get(deviceId); }
function getViewers(deviceId)     { return viewers.get(deviceId) ?? new Set(); }
function getViewerConn(viewerId)  { return viewerConns.get(viewerId); }
function deviceCount()            { return devices.size; }
function getAllDevices()           { return [...devices.entries()]; }

/**
 * Detach a viewer from whichever device it is watching, without
 * removing the viewer connection itself.
 */
function detachViewerFromDevice(viewerId) {
  const vc = viewerConns.get(viewerId);
  if (!vc || !vc.deviceId) return;
  const vids = viewers.get(vc.deviceId);
  if (vids) vids.delete(viewerId);
  vc.deviceId = null;
}

module.exports = {
  registerDevice, unregisterDevice,
  registerViewer, unregisterViewer,
  attachViewerToDevice, detachViewerFromDevice,
  getDevice, getViewers, getViewerConn,
  deviceCount, getAllDevices,
};
