// ============================================================================
// auth.js — JWT verification for device and viewer tokens
// ============================================================================
'use strict';

const jwt = require('jsonwebtoken');
const JWT_SECRET = process.env.JWT_SECRET;
if (!JWT_SECRET) throw new Error('JWT_SECRET env var is required');

/**
 * Verify a device token. Device tokens have { type: 'device', device_id }.
 * @returns {Object} decoded payload
 * @throws if invalid
 */
function verifyDeviceToken(token) {
  const payload = jwt.verify(token, JWT_SECRET, { algorithms: ['HS256'] });
  if (payload.type !== 'device') throw new Error('Not a device token');
  return payload;
}

/**
 * Verify a viewer (human user) token. Has { role, sub }.
 * Roles: admin | monitor | viewer
 * @returns {Object} decoded payload
 * @throws if invalid
 */
function verifyViewerToken(token) {
  const payload = jwt.verify(token, JWT_SECRET, { algorithms: ['HS256'] });
  const ROLES = new Set(['admin', 'monitor', 'viewer']);
  if (!ROLES.has(payload.role)) throw new Error('Invalid role in token');
  return payload;
}

module.exports = { verifyDeviceToken, verifyViewerToken };
