"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  Activity,
  ArrowUpRight,
  Bot,
  Database,
  Flame,
  HardDrive,
  Layers,
  Sparkles,
  Terminal,
  TrendingUp,
  Zap,
} from "lucide-react";
import { useAuth } from "@/lib/auth";
import { apiClient } from "@/lib/api";
import { useTelemetrySocket } from "@/lib/websocket";
import { TelemetryData } from "@/lib/types";

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`;
}

export default function DashboardOverviewPage() {
  const { user } = useAuth();
  const { telemetry: liveTelemetry, connected } = useTelemetrySocket();
  const [staticTelemetry, setStaticTelemetry] = useState<TelemetryData | null>(null);

  useEffect(() => {
    // Initial fetch of telemetry via REST API
    apiClient<TelemetryData>("/api/stats")
      .then((data) => setStaticTelemetry(data))
      .catch(() => {});
  }, []);

  const data = liveTelemetry || staticTelemetry;
  const memoryBytes = data?.memory_used_bytes || 0;
  const maxMemory = 256 * 1024 * 1024; // 256MB default
  const memoryPct = Math.min(100, Math.round((memoryBytes / maxMemory) * 100));

  return (
    <div className="space-y-8">
      {/* Top Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-neutral-800/80 pb-6">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-white flex items-center gap-3">
            <span>Cluster Overview</span>
            <span
              className={`text-xs px-2.5 py-0.5 rounded-full font-mono font-medium border ${
                connected
                  ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                  : "bg-amber-500/10 text-amber-400 border-amber-500/30"
              }`}
            >
              {connected ? "LIVE TELEMETRY STREAMING" : "CONNECTING REST POOL"}
            </span>
          </h1>
          <p className="text-sm text-neutral-400 mt-1">
            Welcome back, <span className="text-neutral-200 font-semibold">{user?.name}</span>. Operational telemetry is streaming in real-time.
          </p>
        </div>

        {/* Quick actions */}
        <div className="flex items-center gap-3">
          <Link
            href="/data"
            className="px-3.5 py-2 rounded-lg bg-neutral-800 hover:bg-neutral-700/80 text-xs font-semibold text-neutral-200 border border-neutral-700/80 flex items-center gap-1.5 transition-colors"
          >
            <Database className="h-3.5 w-3.5 text-neutral-400" />
            <span>Data Console</span>
          </Link>
          <Link
            href="/commands"
            className="px-3.5 py-2 rounded-lg bg-neutral-800 hover:bg-neutral-700/80 text-xs font-semibold text-neutral-200 border border-neutral-700/80 flex items-center gap-1.5 transition-colors"
          >
            <Terminal className="h-3.5 w-3.5 text-neutral-400" />
            <span>Monaco CLI</span>
          </Link>
          <Link
            href="/diagnostics"
            className="px-3.5 py-2 rounded-lg bg-red-600 hover:bg-red-500 text-xs font-semibold text-white shadow-md shadow-red-600/20 flex items-center gap-1.5 transition-colors"
          >
            <Sparkles className="h-3.5 w-3.5" />
            <span>AI Copilot</span>
          </Link>
        </div>
      </div>

      {/* Primary Metrics Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Memory Card */}
        <div className="p-5 rounded-2xl bg-neutral-900 border border-neutral-800/80 space-y-3 relative overflow-hidden">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-neutral-400 uppercase tracking-wider">Used Memory</span>
            <div className="h-8 w-8 rounded-lg bg-red-500/10 border border-red-500/20 flex items-center justify-center">
              <HardDrive className="h-4 w-4 text-red-400" />
            </div>
          </div>
          <div>
            <div className="text-2xl font-bold text-white font-mono">{formatBytes(memoryBytes)}</div>
            <div className="flex items-center justify-between text-xs text-neutral-400 mt-1">
              <span>Cap: {formatBytes(maxMemory)}</span>
              <span className="font-mono text-red-400">{memoryPct}%</span>
            </div>
          </div>
          {/* Progress bar */}
          <div className="w-full h-1.5 bg-neutral-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-red-600 to-red-400 transition-all duration-500"
              style={{ width: `${memoryPct}%` }}
            />
          </div>
        </div>

        {/* Total Keys Card */}
        <div className="p-5 rounded-2xl bg-neutral-900 border border-neutral-800/80 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-neutral-400 uppercase tracking-wider">Total Active Keys</span>
            <div className="h-8 w-8 rounded-lg bg-blue-500/10 border border-blue-500/20 flex items-center justify-center">
              <Database className="h-4 w-4 text-blue-400" />
            </div>
          </div>
          <div>
            <div className="text-2xl font-bold text-white font-mono">
              {(data?.total_keys || 0).toLocaleString()}
            </div>
            <p className="text-xs text-neutral-500 mt-1">Across all 6 native data types</p>
          </div>
        </div>

        {/* Throughput Card */}
        <div className="p-5 rounded-2xl bg-neutral-900 border border-neutral-800/80 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-neutral-400 uppercase tracking-wider">Throughput</span>
            <div className="h-8 w-8 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center">
              <Zap className="h-4 w-4 text-emerald-400" />
            </div>
          </div>
          <div>
            <div className="text-2xl font-bold text-white font-mono">
              {(data?.ops_per_second || 0).toLocaleString()}{" "}
              <span className="text-xs font-normal text-neutral-400">ops/s</span>
            </div>
            <p className="text-xs text-neutral-500 mt-1">
              {(data?.total_commands || 0).toLocaleString()} total commands
            </p>
          </div>
        </div>

        {/* Latency P99 Card */}
        <div className="p-5 rounded-2xl bg-neutral-900 border border-neutral-800/80 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-neutral-400 uppercase tracking-wider">Latency (P99)</span>
            <div className="h-8 w-8 rounded-lg bg-purple-500/10 border border-purple-500/20 flex items-center justify-center">
              <Activity className="h-4 w-4 text-purple-400" />
            </div>
          </div>
          <div>
            <div className="text-2xl font-bold text-white font-mono">
              {data?.latency_p99_ms ? `${data.latency_p99_ms.toFixed(2)} ms` : "0.05 ms"}
            </div>
            <div className="flex items-center gap-1.5 text-xs text-neutral-500 mt-1">
              <span>Hit ratio:</span>
              <span className="text-emerald-400 font-mono">
                {Math.round((data?.cache_hit_ratio || 1) * 100)}%
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Secondary Row: Temperature Breakdown & Quick Launch */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Temperature Classification */}
        <div className="lg:col-span-2 p-6 rounded-2xl bg-neutral-900 border border-neutral-800 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-base font-semibold text-white flex items-center gap-2">
                <Flame className="h-4 w-4 text-orange-400" />
                Adaptive Memory Temperature Classification
              </h2>
              <p className="text-xs text-neutral-400 mt-0.5">
                Dynamic classification tracking recency and frequency for proactive cache eviction.
              </p>
            </div>
            <Link
              href="/data"
              className="text-xs text-red-400 hover:text-red-300 font-semibold flex items-center gap-1"
            >
              Explore <ArrowUpRight className="h-3.5 w-3.5" />
            </Link>
          </div>

          <div className="grid grid-cols-3 gap-3 pt-2">
            <div className="p-4 rounded-xl bg-neutral-950/70 border border-red-500/20 space-y-1">
              <span className="text-xs font-semibold text-red-400 flex items-center gap-1">
                <span className="h-2 w-2 rounded-full bg-red-500 animate-pulse" />
                HOT
              </span>
              <div className="text-xl font-bold text-white font-mono">
                {data?.temperature?.hot || 0}
              </div>
              <p className="text-[11px] text-neutral-500">Frequently accessed keys</p>
            </div>

            <div className="p-4 rounded-xl bg-neutral-950/70 border border-amber-500/20 space-y-1">
              <span className="text-xs font-semibold text-amber-400 flex items-center gap-1">
                <span className="h-2 w-2 rounded-full bg-amber-500" />
                WARM
              </span>
              <div className="text-xl font-bold text-white font-mono">
                {data?.temperature?.warm || 0}
              </div>
              <p className="text-[11px] text-neutral-500">Moderate recent usage</p>
            </div>

            <div className="p-4 rounded-xl bg-neutral-950/70 border border-blue-500/20 space-y-1">
              <span className="text-xs font-semibold text-blue-400 flex items-center gap-1">
                <span className="h-2 w-2 rounded-full bg-blue-500" />
                COLD
              </span>
              <div className="text-xl font-bold text-white font-mono">
                {data?.temperature?.cold || 0}
              </div>
              <p className="text-[11px] text-neutral-500">Eviction candidates</p>
            </div>
          </div>
        </div>

        {/* AI Copilot Status Card */}
        <div className="p-6 rounded-2xl bg-gradient-to-b from-neutral-900 to-neutral-950 border border-neutral-800 space-y-4 flex flex-col justify-between">
          <div className="space-y-3">
            <div className="h-10 w-10 rounded-xl bg-gradient-to-tr from-red-600 to-red-400 flex items-center justify-center shadow-lg shadow-red-500/20">
              <Bot className="h-5 w-5 text-white" />
            </div>
            <div>
              <h3 className="text-base font-semibold text-white">Google Gemini DBA Copilot</h3>
              <p className="text-xs text-neutral-400 mt-1 leading-relaxed">
                Autonomous system diagnostics grounded on real-time cache fragmentation, query latencies, and access patterns.
              </p>
            </div>
          </div>

          <Link
            href="/diagnostics"
            className="w-full py-2.5 px-4 rounded-xl bg-neutral-800 hover:bg-neutral-700 text-white text-xs font-semibold text-center border border-neutral-700/80 transition-colors flex items-center justify-center gap-2"
          >
            <span>Launch Health Audit</span>
            <ArrowUpRight className="h-3.5 w-3.5" />
          </Link>
        </div>
      </div>
    </div>
  );
}
