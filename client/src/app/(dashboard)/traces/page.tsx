"use client";

import React, { useState, useEffect, useMemo, useCallback } from "react";
import {
  AlertCircle,
  ArrowUpDown,
  Check,
  Clock,
  Copy,
  ExternalLink,
  Filter,
  Layers,
  RefreshCw,
  Search,
  ShieldAlert,
  Sliders,
  Zap,
} from "lucide-react";
import { apiClient } from "@/lib/api";
import { TraceItem, SpanItem } from "@/lib/types";

export default function TracesPage() {
  const [traces, setTraces] = useState<TraceItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [commandFilter, setCommandFilter] = useState("ALL");
  const [statusFilter, setStatusFilter] = useState<"ALL" | "OK" | "ERROR">("ALL");
  const [minDuration, setMinDuration] = useState<number>(0);
  const [searchQuery, setSearchQuery] = useState("");
  const [autoRefresh, setAutoRefresh] = useState(true);

  // Selected Trace for Waterfall Inspector
  const [selectedTrace, setSelectedTrace] = useState<TraceItem | null>(null);
  const [copiedTraceId, setCopiedTraceId] = useState(false);

  const fetchTraces = useCallback(async () => {
    try {
      let url = "/api/traces?limit=100";
      if (commandFilter !== "ALL") {
        url += `&command=${encodeURIComponent(commandFilter)}`;
      }
      if (statusFilter !== "ALL") {
        url += `&status=${encodeURIComponent(statusFilter)}`;
      }
      if (minDuration > 0) {
        url += `&min_duration_ms=${minDuration}`;
      }

      const res: TraceItem[] = await apiClient(url);
      setTraces(res || []);
      setError(null);

      // Preserve selection or auto-select first
      if (res && res.length > 0) {
        setSelectedTrace((prev) => {
          if (!prev) return res[0];
          const matched = res.find((t) => t.trace_id === prev.trace_id);
          return matched || res[0];
        });
      }
    } catch (err: any) {
      setError(err.message || "Failed to load distributed traces");
    } finally {
      setLoading(false);
    }
  }, [commandFilter, statusFilter, minDuration]);

  useEffect(() => {
    fetchTraces();
  }, [fetchTraces]);

  // Polling for live distributed tracing
  useEffect(() => {
    if (!autoRefresh) return;
    const interval = setInterval(() => {
      fetchTraces();
    }, 3000);
    return () => clearInterval(interval);
  }, [autoRefresh, fetchTraces]);

  // Filtered traces in memory by search query
  const filteredTraces = useMemo(() => {
    return traces.filter((t) => {
      if (!searchQuery) return true;
      const q = searchQuery.toLowerCase();
      return (
        t.trace_id.toLowerCase().includes(q) ||
        t.command.toLowerCase().includes(q) ||
        t.sanitized_args.some((arg) => arg.toLowerCase().includes(q)) ||
        (t.client_ip && t.client_ip.toLowerCase().includes(q))
      );
    });
  }, [traces, searchQuery]);

  // Metrics summary
  const stats = useMemo(() => {
    if (traces.length === 0) {
      return { total: 0, p50: 0, p99: 0, errorRate: 0 };
    }
    const durations = [...traces.map((t) => t.duration_ms)].sort((a, b) => a - b);
    const p50 = durations[Math.floor(durations.length * 0.5)] || 0;
    const p99 = durations[Math.floor(durations.length * 0.99)] || 0;
    const errorCount = traces.filter((t) => t.status === "ERROR").length;
    const errorRate = ((errorCount / traces.length) * 100).toFixed(1);

    return {
      total: traces.length,
      p50: p50.toFixed(2),
      p99: p99.toFixed(2),
      errorRate,
    };
  }, [traces]);

  const handleCopyTraceId = () => {
    if (selectedTrace) {
      navigator.clipboard.writeText(selectedTrace.trace_id);
      setCopiedTraceId(true);
      setTimeout(() => setCopiedTraceId(false), 2000);
    }
  };

  const formatDuration = (ms: number) => {
    if (ms < 1) {
      return `${(ms * 1000).toFixed(0)} µs`;
    }
    return `${ms.toFixed(2)} ms`;
  };

  const getDurationColor = (ms: number) => {
    if (ms > 5) return "text-red-400 bg-red-500/10 border-red-500/30";
    if (ms > 1) return "text-amber-400 bg-amber-500/10 border-amber-500/30";
    return "text-emerald-400 bg-emerald-500/10 border-emerald-500/30";
  };

  return (
    <div className="space-y-6">
      {/* Overview Stat Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="p-4 rounded-xl bg-neutral-900/60 border border-neutral-800 backdrop-blur">
          <div className="text-xs font-semibold text-neutral-400 uppercase tracking-wider">
            Trace Buffer
          </div>
          <div className="text-2xl font-bold font-mono text-white mt-1">
            {stats.total.toLocaleString()}
          </div>
          <div className="text-[11px] text-neutral-500 mt-1">Ring buffer capacity: 1,000</div>
        </div>

        <div className="p-4 rounded-xl bg-neutral-900/60 border border-neutral-800 backdrop-blur">
          <div className="text-xs font-semibold text-neutral-400 uppercase tracking-wider">
            P50 Latency
          </div>
          <div className="text-2xl font-bold font-mono text-emerald-400 mt-1">
            {stats.p50} ms
          </div>
          <div className="text-[11px] text-neutral-500 mt-1">Median execution duration</div>
        </div>

        <div className="p-4 rounded-xl bg-neutral-900/60 border border-neutral-800 backdrop-blur">
          <div className="text-xs font-semibold text-neutral-400 uppercase tracking-wider">
            P99 Latency
          </div>
          <div className="text-2xl font-bold font-mono text-amber-400 mt-1">
            {stats.p99} ms
          </div>
          <div className="text-[11px] text-neutral-500 mt-1">99th percentile tail latency</div>
        </div>

        <div className="p-4 rounded-xl bg-neutral-900/60 border border-neutral-800 backdrop-blur">
          <div className="text-xs font-semibold text-neutral-400 uppercase tracking-wider">
            Error Rate
          </div>
          <div className="text-2xl font-bold font-mono text-white mt-1">
            {stats.errorRate}%
          </div>
          <div className="text-[11px] text-neutral-500 mt-1">Failed command percentage</div>
        </div>
      </div>

      {/* Main Split Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 min-h-[600px]">
        {/* Left Column: Trace List (5 cols) */}
        <div className="lg:col-span-5 flex flex-col rounded-2xl bg-neutral-900/60 border border-neutral-800 backdrop-blur p-4 space-y-4">
          {/* Controls Bar */}
          <div className="space-y-3">
            <div className="flex items-center justify-between gap-2">
              <div className="relative flex-1">
                <Search className="h-3.5 w-3.5 text-neutral-500 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Filter by command or ID..."
                  className="w-full pl-8 pr-3 py-1.5 bg-neutral-950 border border-neutral-800 rounded-lg text-xs text-white placeholder-neutral-500 font-mono focus:outline-none focus:border-red-500 transition-colors"
                />
              </div>
              <button
                onClick={fetchTraces}
                disabled={loading}
                className="p-1.5 rounded-lg bg-neutral-950 border border-neutral-800 hover:bg-neutral-800 text-neutral-400 hover:text-white transition-colors"
                title="Refresh Traces"
              >
                <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
              </button>
            </div>

            {/* Filter Pills */}
            <div className="flex items-center justify-between text-xs gap-2">
              <div className="flex items-center gap-1">
                {(["ALL", "OK", "ERROR"] as const).map((s) => (
                  <button
                    key={s}
                    onClick={() => setStatusFilter(s)}
                    className={`px-2.5 py-1 rounded-md text-[11px] font-semibold transition-colors ${
                      statusFilter === s
                        ? s === "ERROR"
                          ? "bg-red-500/20 text-red-400 border border-red-500/30"
                          : "bg-red-600/20 text-red-400 border border-red-500/30"
                        : "bg-neutral-950 text-neutral-400 hover:text-neutral-200 border border-neutral-800"
                    }`}
                  >
                    {s}
                  </button>
                ))}
              </div>

              <div className="flex items-center gap-1.5 text-[11px] text-neutral-400">
                <label className="flex items-center gap-1 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={autoRefresh}
                    onChange={(e) => setAutoRefresh(e.target.checked)}
                    className="rounded border-neutral-800 text-red-600 focus:ring-0 bg-neutral-950"
                  />
                  <span>Auto-refresh</span>
                </label>
              </div>
            </div>

            {/* Slow Query Filter Presets */}
            <div className="flex items-center gap-1 text-[11px] overflow-x-auto pb-1">
              <span className="text-neutral-500 shrink-0">Duration:</span>
              {[
                { label: "All", val: 0 },
                { label: ">0.5ms", val: 0.5 },
                { label: ">1ms", val: 1.0 },
                { label: ">5ms", val: 5.0 },
              ].map((opt) => (
                <button
                  key={opt.label}
                  onClick={() => setMinDuration(opt.val)}
                  className={`px-2 py-0.5 rounded text-[10px] font-medium font-mono shrink-0 transition-colors ${
                    minDuration === opt.val
                      ? "bg-neutral-800 text-amber-400 border border-amber-500/30"
                      : "bg-neutral-950 text-neutral-400 hover:text-neutral-200 border border-neutral-800"
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          {/* Traces List */}
          <div className="flex-1 overflow-y-auto space-y-2 max-h-[600px] pr-1">
            {loading && traces.length === 0 ? (
              <div className="py-16 text-center text-neutral-500 text-xs">
                <RefreshCw className="h-5 w-5 animate-spin mx-auto mb-2 text-neutral-400" />
                Loading distributed trace telemetry...
              </div>
            ) : filteredTraces.length === 0 ? (
              <div className="py-16 text-center text-neutral-500 text-xs border border-dashed border-neutral-800 rounded-xl">
                <Layers className="h-6 w-6 mx-auto mb-2 text-neutral-600" />
                No distributed traces match criteria.
              </div>
            ) : (
              filteredTraces.map((trace) => {
                const isSelected = selectedTrace?.trace_id === trace.trace_id;
                return (
                  <div
                    key={trace.trace_id}
                    onClick={() => setSelectedTrace(trace)}
                    className={`p-3 rounded-xl border transition-all cursor-pointer ${
                      isSelected
                        ? "bg-neutral-800/90 border-red-500/50 shadow-md shadow-red-500/5"
                        : "bg-neutral-950/70 border-neutral-800/80 hover:bg-neutral-900 hover:border-neutral-700"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2 min-w-0">
                        <span className="px-2 py-0.5 rounded bg-neutral-900 border border-neutral-700 text-white font-mono text-xs font-bold">
                          {trace.command}
                        </span>
                        <span className="text-[11px] font-mono text-neutral-400 truncate">
                          {trace.sanitized_args.join(" ") || "#no-args"}
                        </span>
                      </div>
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold border ${getDurationColor(
                          trace.duration_ms
                        )}`}
                      >
                        {formatDuration(trace.duration_ms)}
                      </span>
                    </div>

                    <div className="flex items-center justify-between mt-2 pt-2 border-t border-neutral-800/50 text-[10px] font-mono text-neutral-500">
                      <span>{new Date(trace.start_time * 1000).toLocaleTimeString()}</span>
                      <div className="flex items-center gap-2">
                        {trace.status === "ERROR" ? (
                          <span className="text-red-400 font-semibold flex items-center gap-0.5">
                            <AlertCircle className="h-3 w-3" /> ERROR
                          </span>
                        ) : (
                          <span className="text-emerald-400 font-semibold">OK</span>
                        )}
                        <span>•</span>
                        <span>{trace.spans?.length || 1} spans</span>
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Right Column: Waterfall Span Timeline (7 cols) */}
        <div className="lg:col-span-7 flex flex-col rounded-2xl bg-neutral-900/60 border border-neutral-800 backdrop-blur p-6">
          {selectedTrace ? (
            <div className="space-y-6 flex-1 flex flex-col">
              {/* Trace Header */}
              <div className="p-4 rounded-xl bg-neutral-950 border border-neutral-800 space-y-3">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <span className="px-2.5 py-0.5 rounded bg-red-600 text-white font-mono text-xs font-bold">
                        {selectedTrace.command}
                      </span>
                      {selectedTrace.status === "ERROR" ? (
                        <span className="px-2 py-0.5 rounded bg-red-500/10 text-red-400 border border-red-500/30 text-[11px] font-semibold">
                          FAILED
                        </span>
                      ) : (
                        <span className="px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 text-[11px] font-semibold">
                          SUCCESS
                        </span>
                      )}
                      <span className="text-xs text-neutral-400 font-mono">
                        {selectedTrace.client_ip || "local"}
                      </span>
                    </div>
                    <div className="text-xs font-mono text-neutral-300 break-all">
                      {selectedTrace.command} {selectedTrace.sanitized_args.join(" ")}
                    </div>
                  </div>

                  <div className="text-right">
                    <div className="text-lg font-bold font-mono text-white">
                      {formatDuration(selectedTrace.duration_ms)}
                    </div>
                    <div className="text-[10px] text-neutral-500 font-mono">
                      Total Latency
                    </div>
                  </div>
                </div>

                <div className="flex items-center justify-between pt-2 border-t border-neutral-800 text-[11px] text-neutral-500">
                  <div className="flex items-center gap-1.5 font-mono">
                    <span>Trace ID:</span>
                    <span className="text-neutral-300 truncate max-w-xs">
                      {selectedTrace.trace_id}
                    </span>
                    <button
                      onClick={handleCopyTraceId}
                      className="p-1 hover:text-white transition-colors"
                      title="Copy Trace ID"
                    >
                      {copiedTraceId ? (
                        <Check className="h-3.5 w-3.5 text-emerald-400" />
                      ) : (
                        <Copy className="h-3.5 w-3.5" />
                      )}
                    </button>
                  </div>
                  <span>{new Date(selectedTrace.start_time * 1000).toLocaleString()}</span>
                </div>
              </div>

              {/* Error Callout if applicable */}
              {selectedTrace.error_message && (
                <div className="p-3.5 rounded-xl bg-red-500/10 border border-red-500/30 text-xs text-red-400 flex items-start gap-2.5">
                  <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
                  <div>
                    <div className="font-semibold">Execution Failure:</div>
                    <div className="font-mono mt-0.5">{selectedTrace.error_message}</div>
                  </div>
                </div>
              )}

              {/* Waterfall Spans Timeline View */}
              <div className="flex-1 space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-xs font-bold text-neutral-300 uppercase tracking-wider flex items-center gap-1.5">
                    <Zap className="h-4 w-4 text-amber-400" />
                    Waterfall Execution Breakdown ({selectedTrace.spans?.length || 1} spans)
                  </h3>
                  <span className="text-[11px] font-mono text-neutral-500">
                    Duration: {formatDuration(selectedTrace.duration_ms)}
                  </span>
                </div>

                <div className="p-4 rounded-xl bg-neutral-950 border border-neutral-800 space-y-3 overflow-y-auto max-h-[360px]">
                  {/* Total Command Span Bar */}
                  <div className="space-y-1">
                    <div className="flex items-center justify-between text-xs font-mono">
                      <span className="font-semibold text-white">
                        [Root] {selectedTrace.command}
                      </span>
                      <span className="text-neutral-400">
                        {formatDuration(selectedTrace.duration_ms)}
                      </span>
                    </div>
                    <div className="h-3 w-full bg-neutral-900 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-gradient-to-r from-red-600 to-red-400 rounded-full"
                        style={{ width: "100%" }}
                      />
                    </div>
                  </div>

                  {/* Child Spans (e.g. storage, auth, parse, persistence) */}
                  {selectedTrace.spans && selectedTrace.spans.length > 0 ? (
                    selectedTrace.spans.map((span, idx) => {
                      const totalDur = Math.max(0.001, selectedTrace.duration_ms);
                      const spanDur = span.duration_ms || 0.01;
                      const widthPct = Math.max(4, Math.min(100, (spanDur / totalDur) * 100));

                      // Calculate offset relative to start_time
                      const offsetMs = Math.max(
                        0,
                        (span.start_time - selectedTrace.start_time) * 1000
                      );
                      const leftPct = Math.min(95, (offsetMs / totalDur) * 100);

                      const spanColors: Record<string, string> = {
                        storage: "from-blue-500 to-cyan-400",
                        auth: "from-purple-500 to-pink-400",
                        parse: "from-amber-500 to-yellow-400",
                        eviction: "from-red-500 to-orange-400",
                        persistence: "from-emerald-500 to-green-400",
                      };
                      const gradient = spanColors[span.name] || "from-neutral-500 to-neutral-400";

                      return (
                        <div key={idx} className="space-y-1 pt-2 border-t border-neutral-850">
                          <div className="flex items-center justify-between text-xs font-mono">
                            <span className="text-neutral-300 pl-3 border-l-2 border-neutral-700">
                              ↳ span: {span.name}
                            </span>
                            <span className="text-neutral-400">
                              {formatDuration(span.duration_ms)}
                            </span>
                          </div>
                          <div className="h-2.5 w-full bg-neutral-900 rounded-full overflow-hidden relative">
                            <div
                              className={`h-full bg-gradient-to-r ${gradient} rounded-full absolute`}
                              style={{
                                left: `${leftPct}%`,
                                width: `${widthPct}%`,
                              }}
                            />
                          </div>
                        </div>
                      );
                    })
                  ) : (
                    <div className="pt-2 text-[11px] text-neutral-500 italic pl-3">
                      ↳ Inlined single-stage execution (fast-path)
                    </div>
                  )}
                </div>
              </div>

              {/* Sanitized Arguments Pill List */}
              <div className="p-3.5 rounded-xl bg-neutral-950 border border-neutral-800 space-y-1.5">
                <span className="text-[11px] font-semibold text-neutral-400 uppercase tracking-wider">
                  Sanitized Command Arguments (PII-Masked)
                </span>
                <div className="flex flex-wrap gap-1.5 font-mono text-xs text-neutral-300">
                  {selectedTrace.sanitized_args.length === 0 ? (
                    <span className="text-neutral-600 italic">None</span>
                  ) : (
                    selectedTrace.sanitized_args.map((arg, i) => (
                      <span
                        key={i}
                        className="px-2 py-0.5 rounded bg-neutral-900 border border-neutral-800"
                      >
                        {arg}
                      </span>
                    ))
                  )}
                </div>
              </div>
            </div>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center text-neutral-500 text-xs">
              <Layers className="h-8 w-8 mb-2 text-neutral-700" />
              Select a trace from the left panel to inspect the waterfall execution breakdown.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
