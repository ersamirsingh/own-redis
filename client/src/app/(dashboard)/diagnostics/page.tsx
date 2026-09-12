"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import {
  AlertCircle,
  AlertTriangle,
  Bot,
  BrainCircuit,
  Check,
  ChevronRight,
  Database,
  Flame,
  Info,
  Layers,
  MessageSquare,
  Play,
  Plus,
  RefreshCw,
  Search,
  Send,
  ShieldAlert,
  Sparkles,
  Trash2,
  Zap,
} from "lucide-react";
import { apiClient } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import {
  DiagnosticsReport,
  DiagnosticFinding,
  ProposedAction,
  SemanticMemoryItem,
} from "@/lib/types";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  context_used?: Record<string, any>;
  timestamp: number;
}

export default function DiagnosticsPage() {
  const { user } = useAuth();
  const canExecuteAction = user?.role === "admin" || user?.role === "operator";
  const canWriteMemory = user?.role === "admin" || user?.role === "operator" || user?.role === "developer";

  const [activeTab, setActiveTab] = useState<"audit" | "chat" | "memory">("audit");

  // Diagnostics State
  const [report, setReport] = useState<DiagnosticsReport | null>(null);
  const [loadingReport, setLoadingReport] = useState(false);
  const [reportError, setReportError] = useState<string | null>(null);
  const [executingActionId, setExecutingActionId] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<Record<string, string>>({});

  // Copilot Chat State
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([
    {
      role: "assistant",
      content: `Hello ${user?.name || "Engineer"}! I am your PyRedis AI Database Administrator. I continuously monitor engine telemetry, hit ratios, memory allocation, and latency percentiles to provide grounded operational advice. How can I help you today?`,
      timestamp: Date.now() / 1000,
    },
  ]);
  const [chatInput, setChatInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const chatScrollRef = useRef<HTMLDivElement>(null);

  // Semantic Memory State
  const [memoryEntries, setMemoryEntries] = useState<SemanticMemoryItem[]>([]);
  const [loadingMemory, setLoadingMemory] = useState(false);
  const [memorySearchQuery, setMemorySearchQuery] = useState("");
  const [isAddingMemory, setIsAddingMemory] = useState(false);
  const [newMemoryText, setNewMemoryText] = useState("");
  const [newMemoryTag, setNewMemoryTag] = useState("");
  const [memoryMsg, setMemoryMsg] = useState<string | null>(null);

  // Load diagnostics audit
  const fetchDiagnostics = useCallback(async () => {
    setLoadingReport(true);
    setReportError(null);
    try {
      const data: DiagnosticsReport = await apiClient("/api/ai/diagnostics");
      setReport(data);
    } catch (err: any) {
      setReportError(err.message || "Failed to generate AI diagnostic audit");
    } finally {
      setLoadingReport(false);
    }
  }, []);

  // Load semantic memory
  const fetchMemory = useCallback(async () => {
    setLoadingMemory(true);
    try {
      const res: SemanticMemoryItem[] = await apiClient("/api/ai/memory");
      setMemoryEntries(res || []);
    } catch {
      setMemoryEntries([]);
    } finally {
      setLoadingMemory(false);
    }
  }, []);

  useEffect(() => {
    fetchDiagnostics();
  }, [fetchDiagnostics]);

  useEffect(() => {
    if (activeTab === "memory") {
      fetchMemory();
    }
  }, [activeTab, fetchMemory]);

  useEffect(() => {
    if (chatScrollRef.current) {
      chatScrollRef.current.scrollTop = chatScrollRef.current.scrollHeight;
    }
  }, [chatMessages]);

  const handleExecuteAction = async (actionId: string) => {
    if (!canExecuteAction) return;
    setExecutingActionId(actionId);
    try {
      const res = await apiClient<{ status: string; result: string }>(
        "/api/ai/actions/execute",
        {
          method: "POST",
          body: JSON.stringify({ action_id: actionId }),
        }
      );
      setActionSuccess((prev) => ({
        ...prev,
        [actionId]: res.result || "Command executed successfully",
      }));
      fetchDiagnostics();
    } catch (err: any) {
      setReportError(`Action execution failed: ${err.message}`);
    } finally {
      setExecutingActionId(null);
    }
  };

  const handleSendMessage = async (msgText: string) => {
    const text = msgText.trim();
    if (!text || chatLoading) return;

    const userMsg: ChatMessage = {
      role: "user",
      content: text,
      timestamp: Date.now() / 1000,
    };

    setChatMessages((prev) => [...prev, userMsg]);
    setChatInput("");
    setChatLoading(true);

    try {
      const historyPayload = chatMessages.slice(-6).map((m) => ({
        role: m.role,
        content: m.content,
      }));

      const res = await apiClient<{ reply: string; context_used: Record<string, any> }>(
        "/api/ai/chat",
        {
          method: "POST",
          body: JSON.stringify({
            message: text,
            history: historyPayload,
          }),
        }
      );

      const aiMsg: ChatMessage = {
        role: "assistant",
        content: res.reply,
        context_used: res.context_used,
        timestamp: Date.now() / 1000,
      };
      setChatMessages((prev) => [...prev, aiMsg]);
    } catch (err: any) {
      const errorMsg: ChatMessage = {
        role: "assistant",
        content: `I encountered an issue generating a response: ${err.message}. Please verify the Google Gemini API configuration in Settings.`,
        timestamp: Date.now() / 1000,
      };
      setChatMessages((prev) => [...prev, errorMsg]);
    } finally {
      setChatLoading(false);
    }
  };

  const handleSearchMemory = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!memorySearchQuery.trim()) {
      fetchMemory();
      return;
    }

    setLoadingMemory(true);
    try {
      const results: SemanticMemoryItem[] = await apiClient("/api/ai/memory/search", {
        method: "POST",
        body: JSON.stringify({
          query: memorySearchQuery.trim(),
          top_k: 5,
        }),
      });
      setMemoryEntries(results || []);
    } catch (err: any) {
      setMemoryMsg(`Vector search failed: ${err.message}`);
    } finally {
      setLoadingMemory(false);
    }
  };

  const handleAddMemory = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newMemoryText.trim() || !canWriteMemory) return;

    setLoadingMemory(true);
    try {
      await apiClient("/api/ai/memory", {
        method: "POST",
        body: JSON.stringify({
          text: newMemoryText.trim(),
          metadata: newMemoryTag.trim() ? { tag: newMemoryTag.trim() } : {},
        }),
      });
      setNewMemoryText("");
      setNewMemoryTag("");
      setIsAddingMemory(false);
      setMemoryMsg("Document stored with dense vector embedding!");
      setTimeout(() => setMemoryMsg(null), 3000);
      fetchMemory();
    } catch (err: any) {
      setMemoryMsg(`Failed to add memory: ${err.message}`);
    } finally {
      setLoadingMemory(false);
    }
  };

  const handleDeleteMemory = async (id: string) => {
    if (!canWriteMemory) return;
    try {
      await apiClient(`/api/ai/memory/${id}`, {
        method: "DELETE",
      });
      fetchMemory();
    } catch (err: any) {
      setMemoryMsg(`Failed to delete entry: ${err.message}`);
    }
  };

  const renderHealthBadge = (score: number) => {
    if (score >= 85) {
      return (
        <span className="px-3 py-1 rounded-lg bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 text-sm font-bold font-mono">
          {score}/100 • HEALTHY
        </span>
      );
    }
    if (score >= 60) {
      return (
        <span className="px-3 py-1 rounded-lg bg-amber-500/15 text-amber-400 border border-amber-500/30 text-sm font-bold font-mono">
          {score}/100 • DEGRADED
        </span>
      );
    }
    return (
      <span className="px-3 py-1 rounded-lg bg-red-500/15 text-red-400 border border-red-500/30 text-sm font-bold font-mono">
        {score}/100 • CRITICAL
      </span>
    );
  };

  return (
    <div className="space-y-6">
      {/* Top Banner Navigation */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-6 rounded-2xl bg-gradient-to-r from-red-950/40 via-neutral-900/70 to-neutral-900/60 border border-neutral-800 backdrop-blur">
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-xl bg-red-600/20 border border-red-500/30 flex items-center justify-center text-red-400 shadow-lg shadow-red-600/10">
            <Bot className="h-6 w-6" />
          </div>
          <div>
            <h1 className="text-lg font-bold text-white flex items-center gap-2">
              Autonomous AI DBA & Copilot
              <span className="text-[10px] px-2 py-0.5 rounded bg-red-500/20 text-red-400 font-mono font-semibold">
                Gemini Grounded
              </span>
            </h1>
            <p className="text-xs text-neutral-400 mt-0.5">
              Automated telemetry diagnosis, grounded chat copilot, and semantic vector memory
            </p>
          </div>
        </div>

        {/* Tab Switcher */}
        <div className="flex items-center gap-1.5 p-1 rounded-xl bg-neutral-950/80 border border-neutral-800">
          <button
            onClick={() => setActiveTab("audit")}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all ${
              activeTab === "audit"
                ? "bg-red-600 text-white shadow-md shadow-red-600/20"
                : "text-neutral-400 hover:text-white"
            }`}
          >
            <Sparkles className="h-3.5 w-3.5" />
            DBA Health Audit
          </button>
          <button
            onClick={() => setActiveTab("chat")}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all ${
              activeTab === "chat"
                ? "bg-red-600 text-white shadow-md shadow-red-600/20"
                : "text-neutral-400 hover:text-white"
            }`}
          >
            <MessageSquare className="h-3.5 w-3.5" />
            AI Copilot Chat
          </button>
          <button
            onClick={() => setActiveTab("memory")}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all ${
              activeTab === "memory"
                ? "bg-red-600 text-white shadow-md shadow-red-600/20"
                : "text-neutral-400 hover:text-white"
            }`}
          >
            <BrainCircuit className="h-3.5 w-3.5" />
            Semantic Memory
          </button>
        </div>
      </div>

      {/* TAB 1: DBA HEALTH AUDIT */}
      {activeTab === "audit" && (
        <div className="space-y-6">
          {reportError && (
            <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/30 text-xs text-red-400 flex items-center gap-2">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{reportError}</span>
            </div>
          )}

          {/* Health Score Overview Header */}
          <div className="p-6 rounded-2xl bg-neutral-900/60 border border-neutral-800 backdrop-blur flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div className="flex items-center gap-4">
              <div className="h-16 w-16 rounded-2xl bg-neutral-950 border border-neutral-800 flex flex-col items-center justify-center font-mono">
                <span className="text-xs text-neutral-500 font-semibold uppercase">Score</span>
                <span className="text-xl font-bold text-white">
                  {report ? report.health_score : "--"}
                </span>
              </div>
              <div>
                <div className="flex items-center gap-2 mb-1">
                  {report && renderHealthBadge(report.health_score)}
                  <span className="text-xs text-neutral-500">
                    Last audit: {report ? new Date(report.timestamp * 1000).toLocaleTimeString() : "--"}
                  </span>
                </div>
                <p className="text-xs text-neutral-400 max-w-xl">
                  {report?.findings?.length === 0
                    ? "All engine metrics are optimal. No bottlenecks or contention detected."
                    : `${report?.findings?.length || 0} findings detected across latency, cache eviction, and memory allocations.`}
                </p>
              </div>
            </div>

            <button
              onClick={fetchDiagnostics}
              disabled={loadingReport}
              className="px-4 py-2.5 rounded-xl bg-neutral-950 hover:bg-neutral-800 border border-neutral-800 text-xs font-semibold text-white flex items-center gap-2 transition-colors disabled:opacity-50"
            >
              <RefreshCw className={`h-4 w-4 ${loadingReport ? "animate-spin" : ""}`} />
              <span>Re-run Audit</span>
            </button>
          </div>

          {/* AI-Proposed Actions */}
          {report?.proposed_actions && report.proposed_actions.length > 0 && (
            <div className="p-6 rounded-2xl bg-neutral-900/60 border border-neutral-800 backdrop-blur space-y-4">
              <div className="flex items-center gap-2">
                <Zap className="h-4 w-4 text-amber-400" />
                <h3 className="text-sm font-bold text-white uppercase tracking-wider">
                  AI-Recommended Prescriptions ({report.proposed_actions.length})
                </h3>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {report.proposed_actions.map((act) => {
                  const isExecuting = executingActionId === act.action_id;
                  const executionResult = actionSuccess[act.action_id];

                  return (
                    <div
                      key={act.action_id}
                      className="p-4 rounded-xl bg-neutral-950 border border-neutral-800 space-y-3 flex flex-col justify-between"
                    >
                      <div className="space-y-1.5">
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-bold text-white">{act.title}</span>
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase ${
                              act.risk_level === "LOW"
                                ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/30"
                                : "bg-amber-500/10 text-amber-400 border border-amber-500/30"
                            }`}
                          >
                            Risk: {act.risk_level}
                          </span>
                        </div>
                        <p className="text-xs text-neutral-400">{act.description}</p>
                        <div className="p-2 rounded bg-neutral-900 font-mono text-xs text-red-400 border border-neutral-850">
                          {act.command}
                        </div>
                      </div>

                      {executionResult ? (
                        <div className="p-2 rounded bg-emerald-500/10 border border-emerald-500/30 text-xs text-emerald-400 flex items-center gap-1.5">
                          <Check className="h-3.5 w-3.5" />
                          <span>Executed: {executionResult}</span>
                        </div>
                      ) : (
                        canExecuteAction && (
                          <button
                            onClick={() => handleExecuteAction(act.action_id)}
                            disabled={isExecuting}
                            className="w-full py-2 px-3 rounded-lg bg-red-600 hover:bg-red-500 text-white text-xs font-semibold flex items-center justify-center gap-1.5 transition-colors disabled:opacity-50"
                          >
                            {isExecuting ? (
                              <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                            ) : (
                              <Play className="h-3.5 w-3.5 fill-current" />
                            )}
                            <span>Approve & Execute Action</span>
                          </button>
                        )
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Diagnostic Findings */}
          <div className="p-6 rounded-2xl bg-neutral-900/60 border border-neutral-800 backdrop-blur space-y-4">
            <h3 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
              <ShieldAlert className="h-4 w-4 text-red-500" />
              Detailed Diagnostic Findings
            </h3>

            {loadingReport ? (
              <div className="py-16 text-center text-neutral-500 text-xs">
                <RefreshCw className="h-6 w-6 animate-spin mx-auto mb-2 text-neutral-400" />
                Analyzing real-time memory allocations and command latencies...
              </div>
            ) : !report?.findings || report.findings.length === 0 ? (
              <div className="py-12 text-center text-neutral-500 text-xs border border-dashed border-neutral-800 rounded-xl">
                <Check className="h-8 w-8 mx-auto mb-2 text-emerald-400" />
                <p className="font-semibold text-neutral-200">Zero Critical Anomalies</p>
                <p className="text-xs text-neutral-500 mt-0.5">
                  PyRedis engine is operating within optimal operational thresholds.
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {report.findings.map((f, i) => (
                  <div
                    key={f.id || i}
                    className="p-4 rounded-xl bg-neutral-950 border border-neutral-800 space-y-2"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        {f.severity === "CRITICAL" ? (
                          <AlertCircle className="h-4 w-4 text-red-400 shrink-0" />
                        ) : f.severity === "WARNING" ? (
                          <AlertTriangle className="h-4 w-4 text-amber-400 shrink-0" />
                        ) : (
                          <Info className="h-4 w-4 text-blue-400 shrink-0" />
                        )}
                        <span className="text-xs font-bold text-white">{f.title}</span>
                      </div>
                      <span className="px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-neutral-900 border border-neutral-800 text-neutral-400">
                        {f.category}
                      </span>
                    </div>

                    <p className="text-xs text-neutral-400 pl-6">{f.description}</p>

                    <div className="pl-6 pt-1 flex items-start gap-1.5 text-xs text-neutral-300">
                      <span className="text-red-400 font-semibold shrink-0">Recommendation:</span>
                      <span>{f.recommendation}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 2: AI COPILOT CHAT */}
      {activeTab === "chat" && (
        <div className="flex flex-col h-[650px] rounded-2xl bg-neutral-900/60 border border-neutral-800 backdrop-blur overflow-hidden shadow-2xl">
          {/* Chat Messages */}
          <div
            ref={chatScrollRef}
            className="flex-1 p-6 overflow-y-auto space-y-4 bg-neutral-950/40"
          >
            {chatMessages.map((msg, idx) => (
              <div
                key={idx}
                className={`flex gap-3 max-w-3xl ${
                  msg.role === "user" ? "ml-auto flex-row-reverse" : "mr-auto"
                }`}
              >
                <div
                  className={`h-8 w-8 rounded-lg flex items-center justify-center shrink-0 ${
                    msg.role === "user"
                      ? "bg-red-600 text-white"
                      : "bg-neutral-800 text-red-400 border border-neutral-700"
                  }`}
                >
                  {msg.role === "user" ? <span className="text-xs font-bold">You</span> : <Bot className="h-4 w-4" />}
                </div>

                <div
                  className={`p-4 rounded-2xl text-xs space-y-2 ${
                    msg.role === "user"
                      ? "bg-red-600 text-white rounded-tr-none"
                      : "bg-neutral-900 border border-neutral-800 text-neutral-200 rounded-tl-none"
                  }`}
                >
                  <div className="whitespace-pre-wrap leading-relaxed">{msg.content}</div>

                  {msg.context_used && (
                    <div className="pt-2 border-t border-neutral-800/60 text-[10px] font-mono text-neutral-400 flex items-center gap-2">
                      <Zap className="h-3 w-3 text-amber-400" />
                      <span>Telemetry grounded: {Object.keys(msg.context_used).length} metrics injected</span>
                    </div>
                  )}
                </div>
              </div>
            ))}

            {chatLoading && (
              <div className="flex gap-3 mr-auto max-w-xl">
                <div className="h-8 w-8 rounded-lg bg-neutral-800 text-red-400 border border-neutral-700 flex items-center justify-center shrink-0">
                  <Bot className="h-4 w-4" />
                </div>
                <div className="p-3.5 rounded-2xl bg-neutral-900 border border-neutral-800 text-xs text-neutral-400 flex items-center gap-2 rounded-tl-none">
                  <RefreshCw className="h-3.5 w-3.5 animate-spin text-red-500" />
                  <span>PyRedis DBA is reasoning over live engine state...</span>
                </div>
              </div>
            )}
          </div>

          {/* Quick Prompts Bar */}
          <div className="px-6 py-2.5 border-t border-neutral-800 bg-neutral-900/80 flex items-center gap-2 overflow-x-auto">
            <span className="text-[11px] font-semibold text-neutral-400 uppercase tracking-wider shrink-0">
              Suggestions:
            </span>
            {[
              "Explain current memory usage and fragmentation",
              "Which keys are consuming the most memory?",
              "How should I tune the adaptive eviction weights?",
              "Recommend best practices for distributed locks",
            ].map((promptText) => (
              <button
                key={promptText}
                onClick={() => handleSendMessage(promptText)}
                className="px-2.5 py-1 rounded-lg bg-neutral-950 hover:bg-neutral-800 border border-neutral-800 text-[11px] text-neutral-300 hover:text-white shrink-0 transition-colors"
              >
                {promptText}
              </button>
            ))}
          </div>

          {/* Chat Input Bar */}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSendMessage(chatInput);
            }}
            className="p-4 border-t border-neutral-800 bg-neutral-950 flex items-center gap-2"
          >
            <input
              type="text"
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              placeholder="Ask your PyRedis AI DBA about architecture, optimization, or queries..."
              className="flex-1 px-4 py-2.5 bg-neutral-900 border border-neutral-800 rounded-xl text-xs text-white placeholder-neutral-500 focus:outline-none focus:border-red-500 transition-colors"
            />
            <button
              type="submit"
              disabled={chatLoading || !chatInput.trim()}
              className="px-4 py-2.5 rounded-xl bg-red-600 hover:bg-red-500 text-xs font-semibold text-white flex items-center gap-1.5 transition-colors disabled:opacity-40"
            >
              <Send className="h-3.5 w-3.5" />
              <span>Ask</span>
            </button>
          </form>
        </div>
      )}

      {/* TAB 3: SEMANTIC MEMORY */}
      {activeTab === "memory" && (
        <div className="space-y-5">
          {memoryMsg && (
            <div className="p-3.5 rounded-xl bg-neutral-900 border border-neutral-800 text-xs text-neutral-300 flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-amber-400" />
              <span>{memoryMsg}</span>
            </div>
          )}

          {/* Controls Bar */}
          <div className="p-6 rounded-2xl bg-neutral-900/60 border border-neutral-800 backdrop-blur flex flex-col md:flex-row md:items-center justify-between gap-4">
            <form onSubmit={handleSearchMemory} className="flex items-center gap-2 flex-1 max-w-md">
              <div className="relative flex-1">
                <Search className="h-3.5 w-3.5 text-neutral-500 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  value={memorySearchQuery}
                  onChange={(e) => setMemorySearchQuery(e.target.value)}
                  placeholder="Semantic vector similarity query..."
                  className="w-full pl-8 pr-3 py-2 bg-neutral-950 border border-neutral-800 rounded-lg text-xs text-white placeholder-neutral-500 focus:outline-none focus:border-red-500 transition-colors"
                />
              </div>
              <button
                type="submit"
                className="px-3.5 py-2 rounded-lg bg-neutral-800 hover:bg-neutral-700 text-xs font-semibold text-neutral-200 transition-colors"
              >
                Search
              </button>
            </form>

            <div className="flex items-center gap-2">
              <button
                onClick={fetchMemory}
                disabled={loadingMemory}
                className="p-2 rounded-lg bg-neutral-950 border border-neutral-800 hover:bg-neutral-800 text-neutral-400 hover:text-white transition-colors"
                title="Refresh Memory"
              >
                <RefreshCw className={`h-4 w-4 ${loadingMemory ? "animate-spin" : ""}`} />
              </button>

              {canWriteMemory && (
                <button
                  onClick={() => setIsAddingMemory(!isAddingMemory)}
                  className="px-3.5 py-2 rounded-lg bg-red-600 hover:bg-red-500 text-xs font-semibold text-white flex items-center gap-1.5 transition-colors"
                >
                  <Plus className="h-4 w-4" />
                  <span>Add Document</span>
                </button>
              )}
            </div>
          </div>

          {/* Add Document Panel */}
          {isAddingMemory && (
            <form
              onSubmit={handleAddMemory}
              className="p-6 rounded-2xl bg-neutral-900 border border-neutral-800 space-y-4 animate-in fade-in duration-100"
            >
              <h3 className="text-xs font-bold text-white uppercase tracking-wider">
                Store Document in Vector Memory
              </h3>
              <textarea
                rows={4}
                required
                value={newMemoryText}
                onChange={(e) => setNewMemoryText(e.target.value)}
                placeholder="Enter document text or knowledge chunk to embed..."
                className="w-full px-3.5 py-2.5 bg-neutral-950 border border-neutral-800 rounded-lg text-xs text-white placeholder-neutral-500 focus:outline-none focus:border-red-500 transition-colors"
              />
              <div className="flex items-center gap-3">
                <input
                  type="text"
                  value={newMemoryTag}
                  onChange={(e) => setNewMemoryTag(e.target.value)}
                  placeholder="Optional metadata tag (e.g. runbook, schema)"
                  className="flex-1 px-3.5 py-2 bg-neutral-950 border border-neutral-800 rounded-lg text-xs text-white placeholder-neutral-500 focus:outline-none focus:border-red-500 transition-colors"
                />
                <button
                  type="submit"
                  disabled={loadingMemory}
                  className="px-4 py-2 rounded-lg bg-red-600 hover:bg-red-500 text-xs font-semibold text-white transition-colors disabled:opacity-50"
                >
                  Embed & Store
                </button>
              </div>
            </form>
          )}

          {/* Memory List */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {loadingMemory && memoryEntries.length === 0 ? (
              <div className="col-span-2 py-16 text-center text-neutral-500 text-xs">
                <RefreshCw className="h-6 w-6 animate-spin mx-auto mb-2 text-neutral-400" />
                Querying semantic vector index...
              </div>
            ) : memoryEntries.length === 0 ? (
              <div className="col-span-2 py-16 text-center text-neutral-500 text-xs border border-dashed border-neutral-800 rounded-xl">
                <BrainCircuit className="h-8 w-8 mx-auto mb-2 text-neutral-700" />
                No documents in semantic vector memory.
              </div>
            ) : (
              memoryEntries.map((entry) => (
                <div
                  key={entry.id}
                  className="p-4 rounded-xl bg-neutral-950 border border-neutral-800 space-y-2.5 flex flex-col justify-between"
                >
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between">
                      <span className="text-[11px] font-mono text-neutral-500 truncate max-w-xs">
                        id: {entry.id}
                      </span>
                      {entry.score !== undefined && (
                        <span className="px-2 py-0.5 rounded bg-purple-500/20 text-purple-400 text-[10px] font-mono font-bold">
                          similarity: {(entry.score * 100).toFixed(1)}%
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-neutral-200 whitespace-pre-wrap">{entry.text}</p>
                  </div>

                  <div className="flex items-center justify-between pt-2 border-t border-neutral-850 text-[11px] text-neutral-500">
                    <span className="font-mono">
                      {entry.metadata?.tag ? `tag: ${entry.metadata.tag}` : "no tag"}
                    </span>
                    {canWriteMemory && (
                      <button
                        onClick={() => handleDeleteMemory(entry.id)}
                        className="p-1 text-neutral-500 hover:text-red-400 transition-colors"
                        title="Delete entry"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
