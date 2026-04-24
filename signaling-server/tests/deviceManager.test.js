// signaling-server/tests/deviceManager.test.js
'use strict';

const dm = require('../src/deviceManager');

// Minimal WebSocket stub
function makeFakeWs(state = 1 /* OPEN */) {
  const messages = [];
  return {
    readyState: state,
    send: (msg) => messages.push(msg),
    _messages: messages,
  };
}

// Reset state between tests (module-level maps)
beforeEach(() => {
  // Re-register clears old entries naturally via the public API
  // We just make sure we use unique IDs per test
});

describe('deviceManager — devices', () => {
  test('registers a device and retrieves it', () => {
    const ws = makeFakeWs();
    dm.registerDevice('dev-unit-1', ws, { hostname: 'PC-01' });

    const d = dm.getDevice('dev-unit-1');
    expect(d).toBeTruthy();
    expect(d.meta.hostname).toBe('PC-01');
  });

  test('deviceCount reflects registered devices', () => {
    const before = dm.deviceCount();
    const ws = makeFakeWs();
    dm.registerDevice('dev-unit-2', ws);
    expect(dm.deviceCount()).toBe(before + 1);
  });

  test('getAllDevices includes registered device', () => {
    const ws = makeFakeWs();
    dm.registerDevice('dev-unit-3', ws);
    const ids = dm.getAllDevices().map(([id]) => id);
    expect(ids).toContain('dev-unit-3');
  });

  test('unregisterDevice removes device', () => {
    const ws = makeFakeWs();
    dm.registerDevice('dev-unit-4', ws);
    dm.unregisterDevice('dev-unit-4');
    expect(dm.getDevice('dev-unit-4')).toBeUndefined();
  });

  test('unregistering device notifies attached viewers', () => {
    const devWs  = makeFakeWs();
    const viewWs = makeFakeWs();
    dm.registerDevice('dev-unit-5', devWs);
    dm.registerViewer('viewer-unit-1', viewWs);
    dm.attachViewerToDevice('viewer-unit-1', 'dev-unit-5');

    dm.unregisterDevice('dev-unit-5');

    expect(viewWs._messages.length).toBeGreaterThan(0);
    const msg = JSON.parse(viewWs._messages[0]);
    expect(msg.type).toBe('device_disconnected');
    expect(msg.deviceId).toBe('dev-unit-5');
  });
});

describe('deviceManager — viewers', () => {
  test('attaches viewer to device', () => {
    const devWs  = makeFakeWs();
    const viewWs = makeFakeWs();
    dm.registerDevice('dev-unit-6', devWs);
    dm.registerViewer('viewer-unit-2', viewWs);
    dm.attachViewerToDevice('viewer-unit-2', 'dev-unit-6');

    const vids = dm.getViewers('dev-unit-6');
    expect(vids.has('viewer-unit-2')).toBe(true);
  });

  test('getViewerConn returns connection', () => {
    const ws = makeFakeWs();
    dm.registerViewer('viewer-unit-3', ws);
    const conn = dm.getViewerConn('viewer-unit-3');
    expect(conn).toBeTruthy();
    expect(conn.ws).toBe(ws);
  });

  test('unregisterViewer removes entry', () => {
    const ws = makeFakeWs();
    dm.registerViewer('viewer-unit-4', ws);
    dm.unregisterViewer('viewer-unit-4');
    expect(dm.getViewerConn('viewer-unit-4')).toBeUndefined();
  });

  test('getViewers returns empty set for unknown device', () => {
    const vids = dm.getViewers('no-such-device');
    expect(vids.size).toBe(0);
  });
});
