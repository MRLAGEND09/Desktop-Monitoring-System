/**
 * useWebRTC — viewer-side WebRTC + JPEG frame fallback
 *
 * Phase 1: Agent sends binary frames over signaling WebSocket → displayed as JPEG.
 * Phase 2: Full WebRTC SDP/ICE → MediaStream on <video>.
 *
 * TURN credentials are fetched dynamically from /api/signaling/turn-credentials
 * so ephemeral HMAC tokens are always fresh (1-hour TTL from coturn).
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { useAuthStore } from '../store/auth';
import api from '../lib/api';

const SIGNAL_URL = import.meta.env.VITE_SIGNALING_URL || 'ws://localhost:4000/ws';
// Fallback static ICE config used if the credential fetch fails
const FALLBACK_ICE = [
  { urls: import.meta.env.VITE_STUN_URL || 'stun:localhost:3478' },
];

/**
 * Fetch ephemeral TURN credentials from the signaling server.
 * Returns an array of RTCIceServer objects.
 */
async function fetchIceServers(token) {
  try {
    const { data } = await api.get('/signaling/turn-credentials', {
      headers: { Authorization: `Bearer ${token}` },
    });
    return [
      ...data.uris
        .filter((u) => u.startsWith('stun:'))
        .map((u) => ({ urls: u })),
      {
        urls:       data.uris.filter((u) => u.startsWith('turn') || u.startsWith('turns:')),
        username:   data.username,
        credential: data.credential,
      },
    ];
  } catch {
    console.warn('[useWebRTC] TURN credential fetch failed — using STUN only');
    return FALLBACK_ICE;
  }
}

export function useWebRTC(deviceId, videoRef) {
  const token  = useAuthStore((s) => s.token);
  const wsRef  = useRef(null);
  const pcRef  = useRef(null);
  const objUrl = useRef(null);
  const iceRef = useRef(FALLBACK_ICE);
  const [status, setStatus] = useState('idle');

  const cleanup = useCallback(() => {
    pcRef.current?.close();   pcRef.current = null;
    wsRef.current?.close();   wsRef.current = null;
    if (objUrl.current) { URL.revokeObjectURL(objUrl.current); objUrl.current = null; }
  }, []);

  useEffect(() => {
    if (!deviceId || !token) return;
    setStatus('connecting');

    let cancelled = false;

    (async () => {
      // Pre-fetch fresh TURN credentials before opening the WebSocket
      iceRef.current = await fetchIceServers(token);
      if (cancelled) return;

      const ws = new WebSocket(SIGNAL_URL);
      ws.binaryType = 'blob';
      wsRef.current = ws;

      ws.onopen = () => {
        ws.send(JSON.stringify({ type: 'viewer_join', token }));
        ws.send(JSON.stringify({ type: 'viewer_watch', deviceId }));
      };

      ws.onmessage = async (event) => {
        // ── Binary JPEG frame ──────────────────────────────────────────────
        if (event.data instanceof Blob) {
          // Frame format: [4-byte header len][JSON header][JPEG bytes]
          const buf = await event.data.arrayBuffer();
          const view = new DataView(buf);
          const hdrLen = view.getUint32(0, false); // big-endian
          const jpegStart = 4 + hdrLen;
          const jpeg = buf.slice(jpegStart);
          if (videoRef?.current?.tagName === 'IMG') {
            if (objUrl.current) URL.revokeObjectURL(objUrl.current);
            objUrl.current = URL.createObjectURL(new Blob([jpeg], { type: 'image/jpeg' }));
            videoRef.current.src = objUrl.current;
          }
          setStatus('live');
          return;
        }

        // ── JSON signaling ─────────────────────────────────────────────────
        let msg;
        try { msg = JSON.parse(event.data); } catch { return; }

        if (msg.type === 'offer') {
          const pc = new RTCPeerConnection({ iceServers: iceRef.current });
          pcRef.current = pc;

          pc.ontrack = (e) => {
            if (videoRef?.current && e.streams[0]) {
              videoRef.current.srcObject = e.streams[0];
              setStatus('live');
            }
          };
          pc.onicecandidate = (e) => {
            if (e.candidate)
              ws.send(JSON.stringify({ type: 'ice_candidate', deviceId, candidate: e.candidate }));
          };
          pc.onconnectionstatechange = () => {
            if (['failed', 'disconnected', 'closed'].includes(pc.connectionState))
              setStatus('error');
          };

          await pc.setRemoteDescription(new RTCSessionDescription(msg.sdp));
          const answer = await pc.createAnswer();
          await pc.setLocalDescription(answer);
          ws.send(JSON.stringify({ type: 'answer', deviceId, sdp: answer }));
          setStatus('live');
        }

        if (msg.type === 'ice_candidate' && pcRef.current) {
          try { await pcRef.current.addIceCandidate(msg.candidate); } catch { /* ignore */ }
        }

        if (msg.type === 'error')              setStatus('error');
        if (msg.type === 'device_disconnected') setStatus('idle');
      };

      ws.onerror = () => setStatus('error');
      ws.onclose = () => { if (!cancelled) setStatus('idle'); };
    })();

    return () => {
      cancelled = true;
      cleanup();
    };
  }, [deviceId, token, cleanup]); // eslint-disable-line react-hooks/exhaustive-deps

  return { status };
}
