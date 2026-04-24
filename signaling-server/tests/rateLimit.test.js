// signaling-server/tests/rateLimit.test.js
'use strict';

// Reload module fresh for each describe block to get clean Map state
function loadRateLimit(maxConns = 3) {
  // Remove from cache so the env var is picked up fresh
  delete require.cache[require.resolve('../src/rateLimit')];
  process.env.WS_MAX_CONNS_PER_IP = String(maxConns);
  return require('../src/rateLimit');
}

function makeReq(ip, xff = null) {
  return {
    headers: xff ? { 'x-forwarded-for': xff } : {},
    socket: { remoteAddress: ip },
  };
}

describe('rateLimit — connection tracking', () => {
  let rl;
  beforeEach(() => { rl = loadRateLimit(3); });

  test('allows connections up to limit', () => {
    const req1 = makeReq('10.0.0.1');
    const req2 = makeReq('10.0.0.1');
    const req3 = makeReq('10.0.0.1');

    expect(rl.onConnect(req1)).toBe('10.0.0.1');
    expect(rl.onConnect(req2)).toBe('10.0.0.1');
    expect(rl.onConnect(req3)).toBe('10.0.0.1');
  });

  test('rejects connection beyond limit', () => {
    const ip = '10.0.0.2';
    for (let i = 0; i < 3; i++) rl.onConnect(makeReq(ip));
    expect(rl.onConnect(makeReq(ip))).toBeNull();
  });

  test('onDisconnect decrements count and allows reconnect', () => {
    const ip = '10.0.0.3';
    for (let i = 0; i < 3; i++) rl.onConnect(makeReq(ip));
    // All full; disconnect one
    rl.onDisconnect(ip);
    // Should be allowed now
    expect(rl.onConnect(makeReq(ip))).toBe(ip);
  });

  test('different IPs tracked independently', () => {
    for (let i = 0; i < 3; i++) rl.onConnect(makeReq('10.0.1.1'));
    // IP 10.0.1.1 is full, but 10.0.1.2 should still connect
    expect(rl.onConnect(makeReq('10.0.1.2'))).toBe('10.0.1.2');
    expect(rl.onConnect(makeReq('10.0.1.1'))).toBeNull();
  });
});

describe('rateLimit — X-Forwarded-For', () => {
  let rl;
  beforeEach(() => { rl = loadRateLimit(2); });

  test('uses first XFF address', () => {
    const req = makeReq('127.0.0.1', '203.0.113.1, 10.0.0.1');
    expect(rl.onConnect(req)).toBe('203.0.113.1');
  });

  test('limits by real IP from XFF', () => {
    const ip = '203.0.113.5';
    rl.onConnect(makeReq('127.0.0.1', `${ip}, 10.0.0.1`));
    rl.onConnect(makeReq('127.0.0.1', `${ip}, 10.0.0.1`));
    expect(rl.onConnect(makeReq('127.0.0.1', `${ip}, 10.0.0.1`))).toBeNull();
  });
});
