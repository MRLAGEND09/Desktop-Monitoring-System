// signaling-server/tests/turnCredentials.test.js
'use strict';

const crypto = require('crypto');

function loadTurnCredentials(secret = 'test-secret-32-chars-long-enough!') {
  jest.resetModules();
  process.env.TURN_SECRET  = secret;
  process.env.TURN_DOMAIN  = 'turn.example.com';
  process.env.TURN_PORT    = '3478';
  return require('../src/turnCredentials');
}

describe('turnCredentials', () => {
  afterEach(() => {
    delete process.env.TURN_SECRET;
    delete process.env.TURN_DOMAIN;
    delete process.env.TURN_PORT;
    jest.resetModules();
  });

  test('throws without TURN_SECRET', () => {
    jest.resetModules();
    delete process.env.TURN_SECRET;
    const tc = require('../src/turnCredentials');
    expect(() => tc.generateCredentials('user1')).toThrow('TURN_SECRET');
  });

  test('returns expected credential shape', () => {
    const tc = loadTurnCredentials();
    const creds = tc.generateCredentials('viewer-abc');
    expect(creds).toHaveProperty('username');
    expect(creds).toHaveProperty('credential');
    expect(creds).toHaveProperty('ttl');
    expect(creds).toHaveProperty('uris');
    expect(Array.isArray(creds.uris)).toBe(true);
  });

  test('username encodes expiry and userId', () => {
    const tc = loadTurnCredentials();
    const before = Math.floor(Date.now() / 1000);
    const creds = tc.generateCredentials('user-42');
    const [expiry, userId] = creds.username.split(':');
    const expiryNum = Number(expiry);
    expect(expiryNum).toBeGreaterThanOrEqual(before + 3500); // ~1 hour
    expect(userId).toBe('user-42');
  });

  test('credential is correct HMAC-SHA1 of username', () => {
    const secret = 'test-secret-32-chars-long-enough!';
    const tc = loadTurnCredentials(secret);
    const creds = tc.generateCredentials('user-test');
    const hmac = crypto.createHmac('sha1', secret);
    hmac.update(creds.username);
    const expected = hmac.digest('base64');
    expect(creds.credential).toBe(expected);
  });

  test('uris include TURN domain and port', () => {
    const tc = loadTurnCredentials();
    const creds = tc.generateCredentials('viewer-uri-test');
    expect(creds.uris.some((u) => u.includes('turn.example.com'))).toBe(true);
    expect(creds.uris.some((u) => u.includes('3478'))).toBe(true);
  });

  test('ttl is 3600', () => {
    const tc = loadTurnCredentials();
    expect(tc.generateCredentials('any').ttl).toBe(3600);
  });

  test('different users get different credentials', () => {
    const tc = loadTurnCredentials();
    const c1 = tc.generateCredentials('user-A');
    const c2 = tc.generateCredentials('user-B');
    expect(c1.username).not.toBe(c2.username);
    expect(c1.credential).not.toBe(c2.credential);
  });
});
