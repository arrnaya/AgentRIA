"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Typed client for RIA's read-only pipeline WebSocket feed
 * (`pipeline/ws_server.py`). Four event types, matching README's Layer 3
 * dashboard panel table and the exact `*_payload()` builders in that file:
 *
 *   SIGNAL  -> Opportunities Feed  (emitted after SCOUT ranks a signal)
 *   TRACE   -> Agent Trace         (emitted after every StateGraph node)
 *   PAYMENT -> Payment Monitor     (emitted per ORACLE x402 payment)
 *   AUDIT   -> HCS Audit Trail     (emitted per AUDIT entry)
 *
 * This hook only ever reads from the socket — it never sends anything back,
 * matching the dashboard's read-only observer contract (see ws_server.py's
 * own docstring: "the dashboard never writes back, so `RiaWsServer` only
 * ever sends").
 */

export type SignalEvent = {
  signal_id: string;
  protocol: string;
  network: string;
  pair: string;
  type: string;
  type_label: string;
  confidence: number;
  observed_at: string;
};

export type TraceEvent = {
  name: string;
  status: string;
  note: string;
};

export type PaymentEvent = {
  signal_id: string | null;
  tool: string | null;
  amount_hbar: number | null;
  facilitator: string;
  tx_id: string | null;
  status: "confirmed" | "pending";
};

export type AuditEvent = {
  action: string;
  signal_id: string | null;
  hcs_topic_id: string | null;
  tx_id: string | null;
  note: string;
  logged_at: string;
};

type WsMessage =
  | { event: "SIGNAL"; data: SignalEvent; ts: string }
  | { event: "TRACE"; data: TraceEvent; ts: string }
  | { event: "PAYMENT"; data: PaymentEvent; ts: string }
  | { event: "AUDIT"; data: AuditEvent; ts: string };

export type RiaSocketStatus = "connecting" | "open" | "closed";

/**
 * `pipeline/runner.py` binds the WebSocket server to this port by default
 * (`--ws-port 3001`). There is no publicly-hosted instance of this server —
 * Vercel hosts the static frontend only, not a long-running Python process
 * — so this points at localhost by design: it "just works" against a
 * pipeline you run yourself, and fails to connect harmlessly (retrying in
 * the background, never fabricating data) everywhere else, including the
 * deployed site.
 */
const DEFAULT_WS_URL = "ws://localhost:3001";
const DEFAULT_MAX_ITEMS = 20;
const INITIAL_RECONNECT_DELAY_MS = 1000;
const MAX_RECONNECT_DELAY_MS = 10_000;

export interface UseRiaSocketOptions {
  /** Overrides `NEXT_PUBLIC_RIA_WS_URL` and the `ws://localhost:3001` default. */
  url?: string;
  /** Max number of items retained per feed (Opportunities/Payments/Audit are newest-first, capped; Trace is chronological, capped). */
  maxItems?: number;
}

export interface RiaSocketLiveFlags {
  signals: boolean;
  trace: boolean;
  payments: boolean;
  audits: boolean;
}

export interface UseRiaSocketResult {
  /** Current WebSocket connection state. */
  status: RiaSocketStatus;
  /** The URL this hook is (attempting to) connect to. */
  url: string;
  /** SIGNAL events, newest first. */
  signals: SignalEvent[];
  /** TRACE events, chronological (oldest first) — mirrors pipeline execution order. */
  trace: TraceEvent[];
  /** PAYMENT events, newest first. */
  payments: PaymentEvent[];
  /** AUDIT events, newest first. */
  audits: AuditEvent[];
  /**
   * Per-panel flags: true once at least one real event of that type has
   * been received over the current or a prior connection. This is the
   * source of truth for "is this specific panel genuinely live" — a
   * connected socket that hasn't emitted a given event type yet should
   * still show that panel as preview, not live.
   */
  live: RiaSocketLiveFlags;
}

function resolveUrl(override?: string): string {
  if (override) return override;
  const envUrl = process.env.NEXT_PUBLIC_RIA_WS_URL;
  if (envUrl) return envUrl;
  return DEFAULT_WS_URL;
}

export function useRiaSocket(options: UseRiaSocketOptions = {}): UseRiaSocketResult {
  const url = resolveUrl(options.url);
  const maxItems = options.maxItems ?? DEFAULT_MAX_ITEMS;
  const maxItemsRef = useRef(maxItems);
  useEffect(() => {
    maxItemsRef.current = maxItems;
  }, [maxItems]);

  const [status, setStatus] = useState<RiaSocketStatus>("connecting");
  const [signals, setSignals] = useState<SignalEvent[]>([]);
  const [trace, setTrace] = useState<TraceEvent[]>([]);
  const [payments, setPayments] = useState<PaymentEvent[]>([]);
  const [audits, setAudits] = useState<AuditEvent[]>([]);
  const [live, setLive] = useState<RiaSocketLiveFlags>({
    signals: false,
    trace: false,
    payments: false,
    audits: false,
  });

  useEffect(() => {
    let cancelled = false;
    let socket: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let reconnectDelay = INITIAL_RECONNECT_DELAY_MS;

    const scheduleReconnect = () => {
      if (cancelled) return;
      reconnectTimer = setTimeout(() => {
        reconnectDelay = Math.min(reconnectDelay * 1.5, MAX_RECONNECT_DELAY_MS);
        connect();
      }, reconnectDelay);
    };

    const connect = () => {
      if (cancelled) return;
      setStatus("connecting");

      let ws: WebSocket;
      try {
        ws = new WebSocket(url);
      } catch {
        // Malformed URL, WebSocket unsupported, etc. — degrade honestly and retry.
        scheduleReconnect();
        return;
      }
      socket = ws;

      ws.onopen = () => {
        if (cancelled) return;
        setStatus("open");
        reconnectDelay = INITIAL_RECONNECT_DELAY_MS;
      };

      ws.onmessage = (event) => {
        if (cancelled) return;
        let message: WsMessage;
        try {
          message = JSON.parse(event.data as string);
        } catch {
          return;
        }
        switch (message.event) {
          case "SIGNAL":
            setSignals((prev) => [message.data, ...prev].slice(0, maxItemsRef.current));
            setLive((prev) => (prev.signals ? prev : { ...prev, signals: true }));
            break;
          case "TRACE":
            setTrace((prev) => [...prev, message.data].slice(-maxItemsRef.current));
            setLive((prev) => (prev.trace ? prev : { ...prev, trace: true }));
            break;
          case "PAYMENT":
            setPayments((prev) => [message.data, ...prev].slice(0, maxItemsRef.current));
            setLive((prev) => (prev.payments ? prev : { ...prev, payments: true }));
            break;
          case "AUDIT":
            setAudits((prev) => [message.data, ...prev].slice(0, maxItemsRef.current));
            setLive((prev) => (prev.audits ? prev : { ...prev, audits: true }));
            break;
          default:
            break;
        }
      };

      ws.onclose = () => {
        if (cancelled) return;
        setStatus("closed");
        scheduleReconnect();
      };

      ws.onerror = () => {
        // onclose always follows onerror for a socket that never opened or
        // that drops — let onclose own reconnect scheduling so we don't
        // double-schedule a retry.
        ws.close();
      };
    };

    connect();

    return () => {
      cancelled = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (socket) {
        socket.onopen = null;
        socket.onmessage = null;
        socket.onclose = null;
        socket.onerror = null;
        socket.close();
      }
    };
  }, [url]);

  return { status, url, signals, trace, payments, audits, live };
}
