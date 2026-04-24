/**
 * useSSE — consumes a Server-Sent Events endpoint and calls onMessage
 * for every named event received.
 *
 * @param {string|null} url        Full URL to the SSE endpoint (null = disabled)
 * @param {string}      eventName  SSE event name to listen for
 * @param {Function}    onMessage  Callback(parsedData)
 * @param {Object}      [options]
 * @param {boolean}     [options.enabled=true]
 */
import { useEffect, useRef } from 'react';
import { useAuthStore } from '../store/auth';

export function useSSE(url, eventName, onMessage, { enabled = true } = {}) {
  const token   = useAuthStore((s) => s.token);
  const cbRef   = useRef(onMessage);
  cbRef.current = onMessage;          // always call latest closure

  useEffect(() => {
    if (!enabled || !url || !token) return;

    // EventSource doesn't support custom headers natively in browsers.
    // Pass the JWT as a query param — the backend reads it via ?token=
    const fullUrl = `${url}?token=${encodeURIComponent(token)}`;
    const es = new EventSource(fullUrl);

    const handler = (ev) => {
      try {
        cbRef.current(JSON.parse(ev.data));
      } catch {
        /* ignore malformed frames */
      }
    };

    es.addEventListener(eventName, handler);
    es.addEventListener('error', () => {
      // EventSource auto-reconnects on network errors — no manual retry needed
    });

    return () => {
      es.removeEventListener(eventName, handler);
      es.close();
    };
  }, [url, eventName, token, enabled]);
}
