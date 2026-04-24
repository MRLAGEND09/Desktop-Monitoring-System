// ============================================================================
// rateLimit.js — Per-IP WebSocket connection rate limiter
//
// Allows MAX_CONNS_PER_IP simultaneous connections per IP.
// New connections beyond the limit are rejected with HTTP 429.
// ============================================================================
'use strict';

const MAX_CONNS_PER_IP = Number(process.env.WS_MAX_CONNS_PER_IP) || 10;

/** @type {Map<string, number>} ip → active connection count */
const ipConns = new Map();

/**
 * Extract real client IP, respecting X-Forwarded-For from trusted proxies.
 * @param {import('http').IncomingMessage} req
 */
function clientIp(req) {
  const xff = req.headers['x-forwarded-for'];
  if (xff) return xff.split(',')[0].trim();
  return req.socket.remoteAddress ?? 'unknown';
}

/**
 * Called when a new WebSocket connection arrives.
 * @returns {string|null} ip if allowed, null if rejected
 */
function onConnect(req) {
  const ip = clientIp(req);
  const count = (ipConns.get(ip) ?? 0) + 1;
  if (count > MAX_CONNS_PER_IP) {
    console.warn(`[rate] Rejected connection from ${ip} (${count} > ${MAX_CONNS_PER_IP})`);
    return null;
  }
  ipConns.set(ip, count);
  return ip;
}

/**
 * Called when a WebSocket connection closes.
 */
function onDisconnect(ip) {
  if (!ip) return;
  const count = ipConns.get(ip) ?? 1;
  if (count <= 1) ipConns.delete(ip);
  else ipConns.set(ip, count - 1);
}

module.exports = { onConnect, onDisconnect };
