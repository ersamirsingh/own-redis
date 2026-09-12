"use client";

import React, { useState, useRef, useEffect } from "react";
import {
  AlertCircle,
  Check,
  ChevronRight,
  Clock,
  Copy,
  Layers,
  Play,
  RotateCcw,
  Sparkles,
  Terminal as TerminalIcon,
  Trash2,
} from "lucide-react";
import { apiClient } from "@/lib/api";
import { useAuth } from "@/lib/auth";

interface ConsoleHistoryEntry {
  id: string;
  command: string;
  result: any;
  duration_ms?: number;
  timestamp: number;
  error?: string;
  trace_id?: string;
}

const COMMAND_SUGGESTIONS = [
  { name: "PING", desc: "Test server responsiveness" },
  { name: "INFO", desc: "Engine telemetry & metrics summary" },
  { name: "DBSIZE", desc: "Count total keys in store" },
  { name: "KEYS *", desc: "List all keys matching pattern" },
  { name: "SET key value", desc: "Set string key value" },
  { name: "GET key", desc: "Get string key value" },
  { name: "EXPIRE key 60", desc: "Set active expiration in seconds" },
  { name: "TTL key", desc: "Get remaining TTL in seconds" },
  { name: "PERSIST key", desc: "Remove key expiration" },
  { name: "DEL key", desc: "Remove key from memory" },
  { name: "LPUSH list item", desc: "Prepend element to list" },
  { name: "RPUSH list item", desc: "Append element to list" },
  { name: "LRANGE list 0 -1", desc: "Retrieve all elements from list" },
  { name: "SADD set member", desc: "Add member to unique set" },
  { name: "SMEMBERS set", desc: "Retrieve all set members" },
  { name: "HSET hash field val", desc: "Set field value in hash" },
  { name: "HGETALL hash", desc: "Retrieve all fields and values in hash" },
  { name: "ZADD zset 10 member", desc: "Add member with score to sorted set" },
  { name: "ZRANGE zset 0 -1", desc: "Retrieve sorted set members by score" },
  { name: "JSON.SET doc $ '{\"a\":1}'", desc: "Set JSON document" },
  { name: "JSON.GET doc $", desc: "Query JSON path" },
  { name: "LOCK.ACQUIRE lock 10", desc: "Acquire distributed lock" },
  { name: "LOCK.RELEASE lock", desc: "Release distributed lock" },
  { name: "RATE.CHECK user 100 60", desc: "Token bucket rate limit check" },
];

export default function CommandsPage() {
  const { user } = useAuth();
  const [command, setCommand] = useState("");
  const [history, setHistory] = useState<ConsoleHistoryEntry[]>([]);
  const [commandBuffer, setCommandBuffer] = useState<string[]>([]);
  const [bufferIndex, setBufferIndex] = useState<number>(-1);
  const [loading, setLoading] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const inputRef = useRef<HTMLInputElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Initial banner entry
    setHistory([
      {
        id: "init",
        command: "# System initialized",
        result: `PyRedis Command Console ready. Authenticated as ${user?.email || "anonymous"} (${user?.role || "user"}). Type a command or click a quick snippet below.`,
        timestamp: Date.now() / 1000,
      },
    ]);
  }, [user]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [history]);

  const executeCommandString = async (cmdStr: string) => {
    const trimmed = cmdStr.trim();
    if (!trimmed || loading) return;

    // Save to cycling buffer
    setCommandBuffer((prev) => [trimmed, ...prev.filter((c) => c !== trimmed)]);
    setBufferIndex(-1);
    setLoading(true);

    const entryId = Math.random().toString(36).substring(2, 9);
    const start = performance.now();

    try {
      const res = await apiClient<{
        command: string;
        result: any;
        duration_ms: number;
        trace_id: string;
      }>("/api/commands", {
        method: "POST",
        body: JSON.stringify({ command: trimmed }),
      });

      const entry: ConsoleHistoryEntry = {
        id: entryId,
        command: trimmed,
        result: res.result,
        duration_ms: res.duration_ms,
        timestamp: Date.now() / 1000,
        trace_id: res.trace_id,
      };

      setHistory((prev) => [...prev, entry]);
      setCommand("");
    } catch (err: any) {
      const duration = Math.round(performance.now() - start);
      const entry: ConsoleHistoryEntry = {
        id: entryId,
        command: trimmed,
        result: null,
        error: err.message || "Execution error",
        duration_ms: duration,
        timestamp: Date.now() / 1000,
      };
      setHistory((prev) => [...prev, entry]);
    } finally {
      setLoading(false);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      executeCommandString(command);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      if (commandBuffer.length > 0) {
        const nextIndex = Math.min(bufferIndex + 1, commandBuffer.length - 1);
        setBufferIndex(nextIndex);
        setCommand(commandBuffer[nextIndex]);
      }
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      if (bufferIndex > 0) {
        const prevIndex = bufferIndex - 1;
        setBufferIndex(prevIndex);
        setCommand(commandBuffer[prevIndex]);
      } else if (bufferIndex === 0) {
        setBufferIndex(-1);
        setCommand("");
      }
    }
  };

  const handleCopyResult = (id: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const renderResult = (val: any) => {
    if (val === null || val === undefined) {
      return <span className="text-neutral-500 italic">(nil)</span>;
    }
    if (typeof val === "boolean") {
      return <span className="text-purple-400 font-bold">{val ? "true" : "false"}</span>;
    }
    if (typeof val === "number") {
      return <span className="text-amber-400 font-bold">(integer) {val}</span>;
    }
    if (typeof val === "string") {
      if (val === "OK" || val === "PONG") {
        return <span className="text-emerald-400 font-semibold">{val}</span>;
      }
      return <span className="text-emerald-300 font-mono whitespace-pre-wrap">{val}</span>;
    }
    if (Array.isArray(val)) {
      if (val.length === 0) {
        return <span className="text-neutral-500 italic">(empty list or set)</span>;
      }
      return (
        <div className="space-y-1 pl-2 border-l border-neutral-800">
          {val.map((item, idx) => (
            <div key={idx} className="flex items-start gap-2">
              <span className="text-neutral-500 font-mono w-6 text-right select-none">
                {idx + 1})
              </span>
              <div className="flex-1">{renderResult(item)}</div>
            </div>
          ))}
        </div>
      );
    }
    if (typeof val === "object") {
      return (
        <pre className="text-cyan-300 font-mono text-xs overflow-x-auto whitespace-pre-wrap p-2 bg-neutral-950/80 rounded border border-neutral-800">
          {JSON.stringify(val, null, 2)}
        </pre>
      );
    }
    return <span className="text-neutral-200">{String(val)}</span>;
  };

  return (
    <div className="flex flex-col h-[calc(100vh-6.5rem)] space-y-4">
      {/* Console Card */}
      <div className="flex-1 flex flex-col rounded-2xl bg-neutral-900/90 border border-neutral-800 backdrop-blur shadow-2xl overflow-hidden">
        {/* Terminal Header Bar */}
        <div className="px-5 py-3 border-b border-neutral-800 bg-neutral-950/80 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5">
              <span className="h-3 w-3 rounded-full bg-red-500/80" />
              <span className="h-3 w-3 rounded-full bg-yellow-500/80" />
              <span className="h-3 w-3 rounded-full bg-green-500/80" />
            </div>
            <div className="h-4 w-[1px] bg-neutral-800" />
            <div className="flex items-center gap-2">
              <TerminalIcon className="h-4 w-4 text-red-400" />
              <span className="text-xs font-bold text-white tracking-wide">
                PyRedis Interactive REPL
              </span>
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-neutral-800 text-neutral-400 font-mono">
                port 6379 / HTTP 8000
              </span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setHistory([])}
              className="p-1.5 rounded-lg text-neutral-400 hover:text-white hover:bg-neutral-800 transition-colors text-xs flex items-center gap-1.5"
              title="Clear Terminal Output"
            >
              <Trash2 className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">Clear</span>
            </button>
          </div>
        </div>

        {/* Terminal Log Area */}
        <div
          ref={scrollRef}
          className="flex-1 p-5 overflow-y-auto font-mono text-xs space-y-4 bg-neutral-950/60"
        >
          {history.map((entry) => (
            <div key={entry.id} className="space-y-1.5 group">
              {/* Command Line */}
              <div className="flex items-center justify-between text-neutral-400">
                <div className="flex items-center gap-2">
                  <span className="text-red-500 font-bold select-none">&gt;</span>
                  <span className="text-white font-semibold">{entry.command}</span>
                </div>
                <div className="flex items-center gap-2.5 opacity-0 group-hover:opacity-100 transition-opacity">
                  {entry.duration_ms !== undefined && (
                    <span className="text-[10px] text-neutral-500 font-mono flex items-center gap-1">
                      <Clock className="h-3 w-3" />
                      {entry.duration_ms.toFixed(2)}ms
                    </span>
                  )}
                  {entry.trace_id && (
                    <span className="text-[10px] px-1.5 py-0.2 rounded bg-neutral-800 text-neutral-400 font-mono flex items-center gap-1">
                      <Layers className="h-2.5 w-2.5 text-red-400" />
                      {entry.trace_id.substring(0, 8)}
                    </span>
                  )}
                  <button
                    onClick={() =>
                      handleCopyResult(
                        entry.id,
                        entry.error ||
                          (typeof entry.result === "object"
                            ? JSON.stringify(entry.result, null, 2)
                            : String(entry.result))
                      )
                    }
                    className="p-1 text-neutral-500 hover:text-white transition-colors"
                    title="Copy result"
                  >
                    {copiedId === entry.id ? (
                      <Check className="h-3 w-3 text-emerald-400" />
                    ) : (
                      <Copy className="h-3 w-3" />
                    )}
                  </button>
                </div>
              </div>

              {/* Output / Result */}
              <div className="pl-4">
                {entry.error ? (
                  <div className="flex items-center gap-2 text-red-400 p-2 rounded bg-red-500/10 border border-red-500/20">
                    <AlertCircle className="h-3.5 w-3.5 shrink-0" />
                    <span>(error) {entry.error}</span>
                  </div>
                ) : (
                  renderResult(entry.result)
                )}
              </div>
            </div>
          ))}

          {loading && (
            <div className="flex items-center gap-2 text-neutral-400 pl-4 py-2">
              <span className="h-2 w-2 rounded-full bg-red-500 animate-ping" />
              <span>Executing in memory engine...</span>
            </div>
          )}
        </div>

        {/* Quick Command Snippets Bar */}
        <div className="px-5 py-2.5 border-t border-neutral-800 bg-neutral-900/60 flex items-center gap-2 overflow-x-auto">
          <span className="text-[11px] font-semibold text-neutral-400 uppercase tracking-wider shrink-0">
            Quick Snippets:
          </span>
          {[
            "PING",
            "INFO",
            "DBSIZE",
            "KEYS *",
            'SET pyredis:status "online"',
            "GET pyredis:status",
            'HSET user:demo name "Alice" role "Engineer"',
            "HGETALL user:demo",
          ].map((cmd) => (
            <button
              key={cmd}
              onClick={() => {
                setCommand(cmd);
                executeCommandString(cmd);
              }}
              className="px-2.5 py-1 rounded bg-neutral-800 hover:bg-neutral-700 text-[11px] font-mono text-neutral-300 hover:text-white shrink-0 transition-colors border border-neutral-700/60"
            >
              {cmd}
            </button>
          ))}
        </div>

        {/* Input Bar */}
        <div className="p-4 border-t border-neutral-800 bg-neutral-950/90">
          <div className="flex items-center gap-2">
            <span className="text-red-500 font-mono font-bold text-base pl-2 select-none">&gt;</span>
            <input
              ref={inputRef}
              type="text"
              value={command}
              onChange={(e) => setCommand(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder='Type a PyRedis command (e.g. SET mykey "hello" or KEYS *)...'
              className="flex-1 bg-transparent text-sm font-mono text-white placeholder-neutral-500 focus:outline-none"
              autoFocus
            />
            <button
              onClick={() => executeCommandString(command)}
              disabled={loading || !command.trim()}
              className="px-4 py-2 rounded-lg bg-red-600 hover:bg-red-500 text-xs font-semibold text-white flex items-center gap-1.5 transition-colors disabled:opacity-40"
            >
              <Play className="h-3.5 w-3.5 fill-current" />
              <span>Run</span>
            </button>
          </div>
        </div>
      </div>

      {/* Suggested Commands Guide Drawer / Panel */}
      <div className="p-4 rounded-xl bg-neutral-900/40 border border-neutral-800 flex flex-wrap items-center gap-3">
        <span className="text-xs font-semibold text-neutral-400 uppercase tracking-wider flex items-center gap-1.5">
          <Sparkles className="h-3.5 w-3.5 text-amber-400" />
          Supported RESP2 Commands:
        </span>
        <div className="flex flex-wrap gap-2 text-[11px] font-mono text-neutral-400">
          {[
            "GET",
            "SET",
            "DEL",
            "EXISTS",
            "EXPIRE",
            "TTL",
            "PERSIST",
            "LPUSH",
            "RPUSH",
            "LPOP",
            "RPOP",
            "LRANGE",
            "SADD",
            "SMEMBERS",
            "HSET",
            "HGET",
            "HGETALL",
            "ZADD",
            "ZRANGE",
            "JSON.SET",
            "JSON.GET",
            "LOCK.ACQUIRE",
            "RATE.CHECK",
          ].map((tag) => (
            <button
              key={tag}
              onClick={() => setCommand((prev) => (prev ? `${prev} ${tag}` : tag))}
              className="px-2 py-0.5 rounded bg-neutral-950 border border-neutral-800 hover:border-neutral-700 text-neutral-300 hover:text-white transition-colors"
            >
              {tag}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
