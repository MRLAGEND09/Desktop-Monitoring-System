// ============================================================================
// turnCredentials.js — Ephemeral HMAC-SHA1 TURN credentials
//
// Compatible with coturn's `use-auth-secret` mode.
// Spec: https://www.ietf.org/rfc/rfc5766.txt §10.2
//
// username = "<expiry_unix_ts>:<user_id>"
// password = base64(HMAC-SHA1(TURN_SECRET, username))
// ============================================================================
'use strict';

const crypto = require('crypto');

const TURN_SECRET = process.env.TURN_SECRET;
const TURN_DOMAIN = process.env.TURN_DOMAIN || 'localhost';
const TURN_PORT   = Number(process.env.TURN_PORT) || 3478;
const TTL_SECS    = 3600; // 1 hour

if (!TURN_SECRET) {
  console.warn('[turn] TURN_SECRET not set — /turn-credentials will return 503');
}

/**
 * Generate an ephemeral TURN credential pair.
 * @param {string} userId  Arbitrary label (e.g. viewer UUID). Not secret.
 * @returns {{ username: string, credential: string, ttl: number, uris: string[] }}
 */
function generateCredentials(userId) {
  if (!TURN_SECRET) throw new Error('TURN_SECRET not configured');

  const expiry   = Math.floor(Date.now() / 1000) + TTL_SECS;
  const username = `${expiry}:${userId}`;
  const hmac     = crypto.createHmac('sha1', TURN_SECRET);
  hmac.update(username);
  const credential = hmac.digest('base64');

  return {
    username,
    credential,
    ttl: TTL_SECS,
    uris: [
      `stun:${TURN_DOMAIN}:${TURN_PORT}`,
      `turn:${TURN_DOMAIN}:${TURN_PORT}?transport=udp`,
      `turn:${TURN_DOMAIN}:${TURN_PORT}?transport=tcp`,
      `turns:${TURN_DOMAIN}:5349?transport=tcp`,
    ],
  };
}

module.exports = { generateCredentials };
