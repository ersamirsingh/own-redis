"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { getAccessToken } from "./api";
import { TelemetryData } from "./types";

interface UseWebSocketOptions {
  topics?: string[];
  onEvent?: (event: any) => void;
  onAlert?: (alert: any) => void;
}

export function useTelemetrySocket(options: UseWebSocketOptions = {}) {
  const { topics = ["telemetry", "keys", "events", "alerts"], onEvent, onAlert } = options;
  const [connected, setConnected] = useState(false);
  const [telemetry, setTelemetry] = useState<TelemetryData | null>(null);
  const [lastMessageTime, setLastMessageTime] = useState<number | null>(null);
  const socketRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const backoffRef = useRef(1000);

  const connect = useCallback(() => {
    const token = getAccessToken();
    if (!token) return;

    const baseWsUrl = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000/ws";
    const wsUrl = `${baseWsUrl}?token=${encodeURIComponent(token)}`;

    try {
      const ws = new WebSocket(wsUrl);
      socketRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        backoffRef.current = 1000;
        // Subscribe to desired topics
        ws.send(JSON.stringify({ type: "subscribe", topics }));
      };

      ws.onmessage = (event) => {
        setLastMessageTime(Date.now());
        try {
          const payload = JSON.parse(event.data);
          if (payload.type === "telemetry" && payload.data) {
            setTelemetry(payload.data);
          } else if (payload.type === "event" && onEvent) {
            onEvent(payload);
          } else if (payload.topic === "alerts" && onAlert) {
            onAlert(payload);
          }
        } catch {
          // ignore parsing error
        }
      };

      ws.onclose = () => {
        setConnected(false);
        // Exponential backoff reconnect
        reconnectTimeoutRef.current = setTimeout(() => {
          backoffRef.current = Math.min(backoffRef.current * 1.5, 10000);
          connect();
        }, backoffRef.current);
      };

      ws.onerror = () => {
        ws.close();
      };
    } catch {
      // connection error
    }
  }, [topics, onEvent, onAlert]);

  useEffect(() => {
    connect();

    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (socketRef.current) {
        socketRef.current.close();
      }
    };
  }, [connect]);

  const sendMessage = useCallback((msg: any) => {
    if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
      socketRef.current.send(JSON.stringify(msg));
    }
  }, []);

  return {
    connected,
    telemetry,
    lastMessageTime,
    sendMessage,
  };
}
