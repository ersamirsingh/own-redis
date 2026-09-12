"use client";

import React, { useEffect, useState } from "react";
import {
  AlertTriangle,
  Check,
  Clock,
  Copy,
  Database,
  Flame,
  History,
  Layers,
  Plus,
  RefreshCw,
  RotateCcw,
  Save,
  Snowflake,
  Sun,
  Trash2,
  X,
} from "lucide-react";
import { apiClient } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { KeyDetail, KeyRevisionItem } from "@/lib/types";

interface KeyEditorProps {
  keyName: string | null;
  isOpen: boolean;
  onClose: () => void;
  onKeyUpdated: () => void;
  onKeyDeleted: () => void;
}

export function KeyEditor({
  keyName,
  isOpen,
  onClose,
  onKeyUpdated,
  onKeyDeleted,
}: KeyEditorProps) {
  const { user } = useAuth();
  const canEdit = user?.role === "admin" || user?.role === "operator" || user?.role === "developer";

  const [activeTab, setActiveTab] = useState<"value" | "ttl" | "history">("value");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  // Key detail from API
  const [detail, setDetail] = useState<KeyDetail | null>(null);
  const [revisions, setRevisions] = useState<KeyRevisionItem[]>([]);

  // Editable states
  const [editString, setEditString] = useState("");
  const [editList, setEditList] = useState<string[]>([]);
  const [newListItem, setNewListItem] = useState("");
  const [editSet, setEditSet] = useState<string[]>([]);
  const [newSetMember, setNewSetMember] = useState("");
  const [editHash, setEditHash] = useState<Array<{ field: string; value: string }>>([]);
  const [newHashField, setNewHashField] = useState("");
  const [newHashValue, setNewHashValue] = useState("");
  const [editZSet, setEditZSet] = useState<Array<{ member: string; score: number }>>([]);
  const [newZMember, setNewZMember] = useState("");
  const [newZScore, setNewZScore] = useState<number>(0);
  const [editJson, setEditJson] = useState("");

  // TTL edit state
  const [newTtl, setNewTtl] = useState<string>("");

  useEffect(() => {
    if (isOpen && keyName) {
      loadKeyData(keyName);
      setConfirmDelete(false);
      setError(null);
      setSuccessMsg(null);
      setActiveTab("value");
    }
  }, [isOpen, keyName]);

  const loadKeyData = async (k: string) => {
    setLoading(true);
    setError(null);
    try {
      const data: KeyDetail = await apiClient(`/api/keys/${encodeURIComponent(k)}`);
      setDetail(data);

      if (data.type === "string") {
        setEditString(typeof data.value === "string" ? data.value : String(data.value ?? ""));
      } else if (data.type === "list") {
        setEditList(Array.isArray(data.value) ? data.value.map(String) : []);
      } else if (data.type === "set") {
        setEditSet(Array.isArray(data.value) ? data.value.map(String) : []);
      } else if (data.type === "hash") {
        if (typeof data.value === "object" && data.value !== null) {
          setEditHash(
            Object.entries(data.value).map(([field, value]) => ({
              field,
              value: String(value),
            }))
          );
        } else {
          setEditHash([]);
        }
      } else if (data.type === "zset") {
        setEditZSet(Array.isArray(data.value) ? data.value : []);
      } else if (data.type === "json") {
        setEditJson(
          typeof data.value === "string"
            ? data.value
            : JSON.stringify(data.value, null, 2)
        );
      }

      try {
        const hist: KeyRevisionItem[] = await apiClient(
          `/api/keys/${encodeURIComponent(k)}/history`
        );
        setRevisions(hist || []);
      } catch {
        setRevisions([]);
      }
    } catch (err: any) {
      setError(err.message || "Failed to load key details");
    } finally {
      setLoading(false);
    }
  };

  const handleCopyKey = () => {
    if (keyName) {
      navigator.clipboard.writeText(keyName);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleSaveValue = async () => {
    if (!detail || !canEdit) return;
    setSaving(true);
    setError(null);
    setSuccessMsg(null);

    let payloadValue: any;
    try {
      if (detail.type === "string") {
        payloadValue = editString;
      } else if (detail.type === "list") {
        payloadValue = editList;
      } else if (detail.type === "set") {
        payloadValue = editSet;
      } else if (detail.type === "hash") {
        const obj: Record<string, string> = {};
        for (const entry of editHash) {
          if (entry.field.trim()) {
            obj[entry.field.trim()] = entry.value;
          }
        }
        payloadValue = obj;
      } else if (detail.type === "zset") {
        payloadValue = editZSet.map((item) => ({
          member: item.member,
          score: Number(item.score),
        }));
      } else if (detail.type === "json") {
        payloadValue = JSON.parse(editJson);
      }
    } catch (err: any) {
      setError(`Value format error: ${err.message}`);
      setSaving(false);
      return;
    }

    try {
      await apiClient("/api/keys", {
        method: "POST",
        body: JSON.stringify({
          key: detail.key,
          type: detail.type,
          value: payloadValue,
          ttl_seconds: detail.ttl_seconds ? Math.max(1, Math.round(detail.ttl_seconds)) : null,
        }),
      });

      setSuccessMsg("Key value successfully updated!");
      setTimeout(() => setSuccessMsg(null), 3000);
      onKeyUpdated();
      await loadKeyData(detail.key);
    } catch (err: any) {
      setError(err.message || "Failed to update key value");
    } finally {
      setSaving(false);
    }
  };

  const handleSetTtl = async (seconds: number | null) => {
    if (!detail || !canEdit) return;
    setSaving(true);
    setError(null);

    try {
      if (seconds === null) {
        await apiClient("/api/commands", {
          method: "POST",
          body: JSON.stringify({
            command: `PERSIST "${detail.key}"`,
          }),
        });
        setSuccessMsg("Key expiration removed (Persisted).");
      } else {
        await apiClient("/api/commands", {
          method: "POST",
          body: JSON.stringify({
            command: `EXPIRE "${detail.key}" ${seconds}`,
          }),
        });
        setSuccessMsg(`Key expiration set to ${seconds} seconds.`);
      }

      setTimeout(() => setSuccessMsg(null), 3000);
      setNewTtl("");
      onKeyUpdated();
      await loadKeyData(detail.key);
    } catch (err: any) {
      setError(err.message || "Failed to update TTL");
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteKey = async () => {
    if (!detail || !canEdit) return;
    if (!confirmDelete) {
      setConfirmDelete(true);
      return;
    }

    setSaving(true);
    setError(null);
    try {
      await apiClient(`/api/keys/${encodeURIComponent(detail.key)}`, {
        method: "DELETE",
      });
      onKeyDeleted();
      onClose();
    } catch (err: any) {
      setError(err.message || "Failed to delete key");
      setSaving(false);
    }
  };

  const formatBytes = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  };

  const formatTtl = (ttl: number | null | undefined): string => {
    if (ttl === null || ttl === undefined) return "No expiration";
    if (ttl <= 0) return "Expired";
    if (ttl < 60) return `${Math.round(ttl)}s`;
    if (ttl < 3600) return `${Math.floor(ttl / 60)}m ${Math.round(ttl % 60)}s`;
    return `${(ttl / 3600).toFixed(1)}h`;
  };

  const renderTypeBadge = (t: string) => {
    const colors: Record<string, string> = {
      string: "bg-blue-500/10 text-blue-400 border-blue-500/30",
      list: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
      set: "bg-purple-500/10 text-purple-400 border-purple-500/30",
      hash: "bg-amber-500/10 text-amber-400 border-amber-500/30",
      zset: "bg-pink-500/10 text-pink-400 border-pink-500/30",
      json: "bg-cyan-500/10 text-cyan-400 border-cyan-500/30",
    };
    return (
      <span
        className={`px-2.5 py-0.5 rounded text-xs font-mono font-bold uppercase tracking-wide border ${
          colors[t] || "bg-neutral-800 text-neutral-300 border-neutral-700"
        }`}
      >
        {t}
      </span>
    );
  };

  const renderTempBadge = (temp: string) => {
    if (temp === "HOT") {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold bg-red-500/15 text-red-400 border border-red-500/30">
          <Flame className="h-3.5 w-3.5 text-red-400 animate-pulse" />
          HOT
        </span>
      );
    }
    if (temp === "WARM") {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold bg-amber-500/15 text-amber-400 border border-amber-500/30">
          <Sun className="h-3.5 w-3.5 text-amber-400" />
          WARM
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold bg-blue-500/15 text-blue-400 border border-blue-500/30">
        <Snowflake className="h-3.5 w-3.5 text-blue-400" />
        COLD
      </span>
    );
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/60 backdrop-blur-sm animate-in fade-in duration-150">
      <div className="w-full max-w-2xl bg-neutral-900 border-l border-neutral-800 h-full flex flex-col shadow-2xl overflow-hidden animate-in slide-in-from-right duration-200">
        {/* Header */}
        <div className="p-6 border-b border-neutral-800 bg-neutral-950/60">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2 mb-1">
                {detail && renderTypeBadge(detail.type)}
                {detail && renderTempBadge(detail.temperature)}
                <button
                  onClick={handleCopyKey}
                  className="p-1 text-neutral-400 hover:text-white rounded hover:bg-neutral-800 transition-colors"
                  title="Copy Key"
                >
                  {copied ? (
                    <Check className="h-3.5 w-3.5 text-emerald-400" />
                  ) : (
                    <Copy className="h-3.5 w-3.5" />
                  )}
                </button>
              </div>
              <h2 className="text-lg font-bold text-white font-mono truncate" title={keyName || ""}>
                {keyName}
              </h2>
            </div>
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg text-neutral-400 hover:text-white hover:bg-neutral-800 transition-colors"
            >
              <X className="h-5 w-5" />
            </button>
          </div>

          {/* Operational Metrics Cards */}
          {detail && (
            <div className="grid grid-cols-4 gap-2 mt-4">
              <div className="p-2.5 rounded-lg bg-neutral-900 border border-neutral-800">
                <div className="text-[11px] text-neutral-400 uppercase tracking-wider">Memory</div>
                <div className="text-sm font-semibold text-white font-mono mt-0.5">
                  {formatBytes(detail.memory_bytes)}
                </div>
              </div>
              <div className="p-2.5 rounded-lg bg-neutral-900 border border-neutral-800">
                <div className="text-[11px] text-neutral-400 uppercase tracking-wider">TTL</div>
                <div className="text-sm font-semibold text-amber-400 font-mono mt-0.5 truncate">
                  {formatTtl(detail.ttl_seconds)}
                </div>
              </div>
              <div className="p-2.5 rounded-lg bg-neutral-900 border border-neutral-800">
                <div className="text-[11px] text-neutral-400 uppercase tracking-wider">Accesses</div>
                <div className="text-sm font-semibold text-white font-mono mt-0.5">
                  {detail.access_count.toLocaleString()}
                </div>
              </div>
              <div className="p-2.5 rounded-lg bg-neutral-900 border border-neutral-800">
                <div className="text-[11px] text-neutral-400 uppercase tracking-wider">Revisions</div>
                <div className="text-sm font-semibold text-purple-400 font-mono mt-0.5">
                  {revisions.length}
                </div>
              </div>
            </div>
          )}

          {/* Navigation Tabs */}
          <div className="flex items-center gap-2 mt-5 border-b border-neutral-800">
            <button
              onClick={() => setActiveTab("value")}
              className={`pb-2.5 text-xs font-semibold uppercase tracking-wider transition-colors border-b-2 flex items-center gap-1.5 ${
                activeTab === "value"
                  ? "text-red-400 border-red-500"
                  : "text-neutral-400 border-transparent hover:text-neutral-200"
              }`}
            >
              <Database className="h-3.5 w-3.5" />
              Value Editor
            </button>
            <button
              onClick={() => setActiveTab("ttl")}
              className={`pb-2.5 text-xs font-semibold uppercase tracking-wider transition-colors border-b-2 flex items-center gap-1.5 ${
                activeTab === "ttl"
                  ? "text-red-400 border-red-500"
                  : "text-neutral-400 border-transparent hover:text-neutral-200"
              }`}
            >
              <Clock className="h-3.5 w-3.5" />
              TTL Expiration
            </button>
            <button
              onClick={() => setActiveTab("history")}
              className={`pb-2.5 text-xs font-semibold uppercase tracking-wider transition-colors border-b-2 flex items-center gap-1.5 ${
                activeTab === "history"
                  ? "text-red-400 border-red-500"
                  : "text-neutral-400 border-transparent hover:text-neutral-200"
              }`}
            >
              <History className="h-3.5 w-3.5" />
              History ({revisions.length})
            </button>
          </div>
        </div>

        {/* Content Body */}
        <div className="flex-1 p-6 overflow-y-auto space-y-4">
          {error && (
            <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-xs text-red-400 flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {successMsg && (
            <div className="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-xs text-emerald-400 flex items-center gap-2">
              <Check className="h-4 w-4 shrink-0" />
              <span>{successMsg}</span>
            </div>
          )}

          {loading ? (
            <div className="flex flex-col items-center justify-center py-20 text-neutral-400">
              <RefreshCw className="h-6 w-6 animate-spin mb-2" />
              <p className="text-xs">Loading key data...</p>
            </div>
          ) : detail ? (
            <>
              {/* TAB 1: VALUE EDITOR */}
              {activeTab === "value" && (
                <div className="space-y-4">
                  {detail.type === "string" && (
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <label className="text-xs font-semibold text-neutral-300 uppercase tracking-wider">
                          String Content ({editString.length} chars)
                        </label>
                        <button
                          type="button"
                          onClick={() => {
                            try {
                              const parsed = JSON.parse(editString);
                              setEditString(JSON.stringify(parsed, null, 2));
                            } catch {
                              setError("Value is not valid JSON to format");
                            }
                          }}
                          className="px-2 py-1 text-[11px] rounded bg-neutral-800 text-neutral-300 hover:bg-neutral-700 transition-colors"
                        >
                          Prettify JSON
                        </button>
                      </div>
                      <textarea
                        rows={12}
                        value={editString}
                        disabled={!canEdit}
                        onChange={(e) => setEditString(e.target.value)}
                        className="w-full px-3.5 py-2.5 bg-neutral-950 border border-neutral-800 rounded-lg text-sm text-neutral-100 font-mono focus:outline-none focus:border-red-500 transition-colors resize-y"
                      />
                    </div>
                  )}

                  {detail.type === "list" && (
                    <div className="space-y-3">
                      <label className="text-xs font-semibold text-neutral-300 uppercase tracking-wider">
                        List Elements ({editList.length})
                      </label>

                      {canEdit && (
                        <div className="flex items-center gap-2">
                          <input
                            type="text"
                            value={newListItem}
                            onChange={(e) => setNewListItem(e.target.value)}
                            placeholder="Add item to list..."
                            className="flex-1 px-3 py-1.5 bg-neutral-950 border border-neutral-800 rounded-lg text-xs text-white placeholder-neutral-500 font-mono"
                            onKeyDown={(e) => {
                              if (e.key === "Enter" && newListItem.trim()) {
                                setEditList([...editList, newListItem.trim()]);
                                setNewListItem("");
                              }
                            }}
                          />
                          <button
                            type="button"
                            onClick={() => {
                              if (newListItem.trim()) {
                                setEditList([...editList, newListItem.trim()]);
                                setNewListItem("");
                              }
                            }}
                            className="px-3 py-1.5 rounded-lg bg-neutral-800 text-xs font-medium text-white hover:bg-neutral-700 flex items-center gap-1"
                          >
                            <Plus className="h-3.5 w-3.5" />
                            Append
                          </button>
                        </div>
                      )}

                      <div className="space-y-2 max-h-96 overflow-y-auto pr-1">
                        {editList.length === 0 ? (
                          <div className="text-xs text-neutral-500 py-4 text-center">List is empty</div>
                        ) : (
                          editList.map((item, idx) => (
                            <div
                              key={idx}
                              className="flex items-center gap-2 p-2 rounded-lg bg-neutral-950 border border-neutral-800/80"
                            >
                              <span className="text-[11px] font-mono text-neutral-500 w-8 text-right shrink-0">
                                #{idx}
                              </span>
                              <input
                                type="text"
                                value={item}
                                disabled={!canEdit}
                                onChange={(e) => {
                                  const updated = [...editList];
                                  updated[idx] = e.target.value;
                                  setEditList(updated);
                                }}
                                className="flex-1 bg-transparent text-xs text-neutral-200 font-mono focus:outline-none"
                              />
                              {canEdit && (
                                <button
                                  type="button"
                                  onClick={() => setEditList(editList.filter((_, i) => i !== idx))}
                                  className="p-1 text-neutral-500 hover:text-red-400 transition-colors"
                                >
                                  <Trash2 className="h-3.5 w-3.5" />
                                </button>
                              )}
                            </div>
                          ))
                        )}
                      </div>
                    </div>
                  )}

                  {detail.type === "set" && (
                    <div className="space-y-3">
                      <label className="text-xs font-semibold text-neutral-300 uppercase tracking-wider">
                        Set Members ({editSet.length} unique)
                      </label>

                      {canEdit && (
                        <div className="flex items-center gap-2">
                          <input
                            type="text"
                            value={newSetMember}
                            onChange={(e) => setNewSetMember(e.target.value)}
                            placeholder="Add member to set..."
                            className="flex-1 px-3 py-1.5 bg-neutral-950 border border-neutral-800 rounded-lg text-xs text-white placeholder-neutral-500 font-mono"
                            onKeyDown={(e) => {
                              if (e.key === "Enter" && newSetMember.trim()) {
                                if (!editSet.includes(newSetMember.trim())) {
                                  setEditSet([...editSet, newSetMember.trim()]);
                                }
                                setNewSetMember("");
                              }
                            }}
                          />
                          <button
                            type="button"
                            onClick={() => {
                              if (newSetMember.trim()) {
                                if (!editSet.includes(newSetMember.trim())) {
                                  setEditSet([...editSet, newSetMember.trim()]);
                                }
                                setNewSetMember("");
                              }
                            }}
                            className="px-3 py-1.5 rounded-lg bg-neutral-800 text-xs font-medium text-white hover:bg-neutral-700 flex items-center gap-1"
                          >
                            <Plus className="h-3.5 w-3.5" />
                            Add Member
                          </button>
                        </div>
                      )}

                      <div className="flex flex-wrap gap-2 p-3 bg-neutral-950 border border-neutral-800 rounded-lg min-h-[100px] max-h-96 overflow-y-auto">
                        {editSet.length === 0 ? (
                          <div className="text-xs text-neutral-500 w-full text-center py-4">
                            Set is empty
                          </div>
                        ) : (
                          editSet.map((member, idx) => (
                            <span
                              key={idx}
                              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-neutral-900 border border-neutral-700 text-xs text-neutral-200 font-mono"
                            >
                              <span>{member}</span>
                              {canEdit && (
                                <button
                                  type="button"
                                  onClick={() => setEditSet(editSet.filter((_, i) => i !== idx))}
                                  className="text-neutral-400 hover:text-red-400 transition-colors"
                                >
                                  <X className="h-3 w-3" />
                                </button>
                              )}
                            </span>
                          ))
                        )}
                      </div>
                    </div>
                  )}

                  {detail.type === "hash" && (
                    <div className="space-y-3">
                      <label className="text-xs font-semibold text-neutral-300 uppercase tracking-wider">
                        Hash Fields & Values ({editHash.length})
                      </label>

                      {canEdit && (
                        <div className="grid grid-cols-12 gap-2">
                          <input
                            type="text"
                            value={newHashField}
                            onChange={(e) => setNewHashField(e.target.value)}
                            placeholder="Field"
                            className="col-span-5 px-3 py-1.5 bg-neutral-950 border border-neutral-800 rounded-lg text-xs text-white placeholder-neutral-500 font-mono"
                          />
                          <input
                            type="text"
                            value={newHashValue}
                            onChange={(e) => setNewHashValue(e.target.value)}
                            placeholder="Value"
                            className="col-span-5 px-3 py-1.5 bg-neutral-950 border border-neutral-800 rounded-lg text-xs text-white placeholder-neutral-500 font-mono"
                          />
                          <button
                            type="button"
                            onClick={() => {
                              if (newHashField.trim()) {
                                setEditHash([
                                  ...editHash.filter((h) => h.field !== newHashField.trim()),
                                  { field: newHashField.trim(), value: newHashValue },
                                ]);
                                setNewHashField("");
                                setNewHashValue("");
                              }
                            }}
                            className="col-span-2 px-2 py-1.5 rounded-lg bg-neutral-800 text-xs font-medium text-white hover:bg-neutral-700 flex items-center justify-center gap-1"
                          >
                            <Plus className="h-3.5 w-3.5" />
                            Add
                          </button>
                        </div>
                      )}

                      <div className="space-y-2 max-h-96 overflow-y-auto">
                        {editHash.length === 0 ? (
                          <div className="text-xs text-neutral-500 py-4 text-center">Hash is empty</div>
                        ) : (
                          editHash.map((entry, idx) => (
                            <div
                              key={idx}
                              className="grid grid-cols-12 gap-2 items-center p-2 rounded-lg bg-neutral-950 border border-neutral-800/80"
                            >
                              <input
                                type="text"
                                value={entry.field}
                                disabled={!canEdit}
                                onChange={(e) => {
                                  const updated = [...editHash];
                                  updated[idx].field = e.target.value;
                                  setEditHash(updated);
                                }}
                                className="col-span-5 bg-transparent text-xs text-amber-400 font-mono font-semibold focus:outline-none"
                              />
                              <input
                                type="text"
                                value={entry.value}
                                disabled={!canEdit}
                                onChange={(e) => {
                                  const updated = [...editHash];
                                  updated[idx].value = e.target.value;
                                  setEditHash(updated);
                                }}
                                className="col-span-6 bg-transparent text-xs text-neutral-200 font-mono focus:outline-none"
                              />
                              {canEdit && (
                                <div className="col-span-1 flex justify-end">
                                  <button
                                    type="button"
                                    onClick={() => setEditHash(editHash.filter((_, i) => i !== idx))}
                                    className="p-1 text-neutral-500 hover:text-red-400 transition-colors"
                                  >
                                    <Trash2 className="h-3.5 w-3.5" />
                                  </button>
                                </div>
                              )}
                            </div>
                          ))
                        )}
                      </div>
                    </div>
                  )}

                  {detail.type === "zset" && (
                    <div className="space-y-3">
                      <label className="text-xs font-semibold text-neutral-300 uppercase tracking-wider">
                        Sorted Set Members ({editZSet.length})
                      </label>

                      {canEdit && (
                        <div className="grid grid-cols-12 gap-2">
                          <input
                            type="text"
                            value={newZMember}
                            onChange={(e) => setNewZMember(e.target.value)}
                            placeholder="Member name"
                            className="col-span-6 px-3 py-1.5 bg-neutral-950 border border-neutral-800 rounded-lg text-xs text-white placeholder-neutral-500 font-mono"
                          />
                          <input
                            type="number"
                            step="any"
                            value={newZScore}
                            onChange={(e) => setNewZScore(parseFloat(e.target.value) || 0)}
                            placeholder="Score"
                            className="col-span-4 px-3 py-1.5 bg-neutral-950 border border-neutral-800 rounded-lg text-xs text-white placeholder-neutral-500 font-mono"
                          />
                          <button
                            type="button"
                            onClick={() => {
                              if (newZMember.trim()) {
                                setEditZSet([
                                  ...editZSet.filter((z) => z.member !== newZMember.trim()),
                                  { member: newZMember.trim(), score: newZScore },
                                ].sort((a, b) => a.score - b.score));
                                setNewZMember("");
                                setNewZScore(0);
                              }
                            }}
                            className="col-span-2 px-2 py-1.5 rounded-lg bg-neutral-800 text-xs font-medium text-white hover:bg-neutral-700 flex items-center justify-center gap-1"
                          >
                            <Plus className="h-3.5 w-3.5" />
                            Add
                          </button>
                        </div>
                      )}

                      <div className="space-y-2 max-h-96 overflow-y-auto">
                        {editZSet.length === 0 ? (
                          <div className="text-xs text-neutral-500 py-4 text-center">ZSet is empty</div>
                        ) : (
                          editZSet.map((item, idx) => (
                            <div
                              key={idx}
                              className="grid grid-cols-12 gap-2 items-center p-2 rounded-lg bg-neutral-950 border border-neutral-800/80"
                            >
                              <span className="col-span-1 text-[11px] font-mono text-neutral-500 text-center">
                                #{idx + 1}
                              </span>
                              <span className="col-span-6 text-xs text-neutral-200 font-mono truncate">
                                {item.member}
                              </span>
                              <input
                                type="number"
                                step="any"
                                value={item.score}
                                disabled={!canEdit}
                                onChange={(e) => {
                                  const updated = [...editZSet];
                                  updated[idx].score = parseFloat(e.target.value) || 0;
                                  setEditZSet(updated);
                                }}
                                className="col-span-4 bg-transparent text-xs text-pink-400 font-mono font-semibold focus:outline-none"
                              />
                              {canEdit && (
                                <div className="col-span-1 flex justify-end">
                                  <button
                                    type="button"
                                    onClick={() => setEditZSet(editZSet.filter((_, i) => i !== idx))}
                                    className="p-1 text-neutral-500 hover:text-red-400 transition-colors"
                                  >
                                    <Trash2 className="h-3.5 w-3.5" />
                                  </button>
                                </div>
                              )}
                            </div>
                          ))
                        )}
                      </div>
                    </div>
                  )}

                  {detail.type === "json" && (
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <label className="text-xs font-semibold text-neutral-300 uppercase tracking-wider">
                          JSON Document
                        </label>
                        <button
                          type="button"
                          onClick={() => {
                            try {
                              const parsed = JSON.parse(editJson);
                              setEditJson(JSON.stringify(parsed, null, 2));
                            } catch {
                              setError("Invalid JSON format");
                            }
                          }}
                          className="px-2 py-1 text-[11px] rounded bg-neutral-800 text-neutral-300 hover:bg-neutral-700 transition-colors"
                        >
                          Prettify JSON
                        </button>
                      </div>
                      <textarea
                        rows={14}
                        value={editJson}
                        disabled={!canEdit}
                        onChange={(e) => setEditJson(e.target.value)}
                        className="w-full px-3.5 py-2.5 bg-neutral-950 border border-neutral-800 rounded-lg text-xs text-cyan-300 font-mono focus:outline-none focus:border-red-500 transition-colors resize-y"
                      />
                    </div>
                  )}

                  {canEdit && (
                    <div className="pt-2">
                      <button
                        onClick={handleSaveValue}
                        disabled={saving}
                        className="w-full py-2.5 px-4 rounded-lg bg-red-600 hover:bg-red-500 text-white text-xs font-semibold uppercase tracking-wider flex items-center justify-center gap-2 transition-colors disabled:opacity-50"
                      >
                        {saving ? (
                          <RefreshCw className="h-4 w-4 animate-spin" />
                        ) : (
                          <Save className="h-4 w-4" />
                        )}
                        <span>Save Changes</span>
                      </button>
                    </div>
                  )}
                </div>
              )}

              {/* TAB 2: TTL MANAGEMENT */}
              {activeTab === "ttl" && (
                <div className="space-y-5">
                  <div className="p-4 rounded-xl bg-neutral-950 border border-neutral-800 space-y-3">
                    <div className="text-xs text-neutral-400 uppercase tracking-wider font-semibold">
                      Current Expiration Status
                    </div>
                    <div className="flex items-center justify-between">
                      <div className="text-lg font-mono font-bold text-white">
                        {formatTtl(detail.ttl_seconds)}
                      </div>
                      {detail.ttl_seconds && detail.ttl_seconds > 0 && canEdit && (
                        <button
                          onClick={() => handleSetTtl(null)}
                          disabled={saving}
                          className="px-3 py-1.5 rounded-lg bg-neutral-800 hover:bg-neutral-700 text-neutral-200 text-xs font-medium flex items-center gap-1.5 transition-colors"
                        >
                          <RotateCcw className="h-3.5 w-3.5 text-amber-400" />
                          Remove TTL (Persist)
                        </button>
                      )}
                    </div>
                  </div>

                  {canEdit && (
                    <div className="space-y-3">
                      <label className="text-xs font-semibold text-neutral-300 uppercase tracking-wider">
                        Set Expiration (Seconds)
                      </label>
                      <div className="grid grid-cols-4 gap-2">
                        {[
                          { label: "1 min", sec: 60 },
                          { label: "5 min", sec: 300 },
                          { label: "1 hour", sec: 3600 },
                          { label: "1 day", sec: 86400 },
                        ].map((preset) => (
                          <button
                            key={preset.sec}
                            type="button"
                            onClick={() => handleSetTtl(preset.sec)}
                            disabled={saving}
                            className="py-2 px-3 rounded-lg bg-neutral-950 border border-neutral-800 hover:border-neutral-700 text-xs font-medium text-neutral-300 hover:text-white transition-colors"
                          >
                            {preset.label}
                          </button>
                        ))}
                      </div>

                      <div className="flex items-center gap-2 pt-2">
                        <input
                          type="number"
                          min="1"
                          value={newTtl}
                          onChange={(e) => setNewTtl(e.target.value)}
                          placeholder="Custom TTL in seconds (e.g. 120)"
                          className="flex-1 px-3.5 py-2 bg-neutral-950 border border-neutral-800 rounded-lg text-xs text-white placeholder-neutral-500 font-mono"
                        />
                        <button
                          type="button"
                          onClick={() => {
                            const val = parseInt(newTtl, 10);
                            if (val > 0) {
                              handleSetTtl(val);
                            }
                          }}
                          disabled={saving || !newTtl}
                          className="px-4 py-2 rounded-lg bg-red-600 hover:bg-red-500 text-white text-xs font-semibold disabled:opacity-50 transition-colors"
                        >
                          Apply TTL
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* TAB 3: REVISION HISTORY */}
              {activeTab === "history" && (
                <div className="space-y-3">
                  <div className="text-xs text-neutral-400">
                    Time-travel revision history tracked by PyRedis versioning engine.
                  </div>

                  {revisions.length === 0 ? (
                    <div className="p-8 text-center border border-dashed border-neutral-800 rounded-xl text-neutral-500 text-xs">
                      No previous revisions recorded for this key yet.
                    </div>
                  ) : (
                    <div className="space-y-2 max-h-[450px] overflow-y-auto pr-1">
                      {revisions.map((rev) => (
                        <div
                          key={rev.version}
                          className="p-3.5 rounded-xl bg-neutral-950 border border-neutral-800 hover:border-neutral-700 transition-colors space-y-2"
                        >
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              <span className="px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-400 text-[11px] font-mono font-bold">
                                v{rev.version}
                              </span>
                              <span className="text-xs font-medium text-neutral-300">
                                {new Date(rev.timestamp * 1000).toLocaleString()}
                              </span>
                            </div>
                            <span className="text-[11px] font-mono text-neutral-500">
                              {formatBytes(rev.size_bytes)}
                            </span>
                          </div>

                          <div className="p-2 rounded bg-neutral-900 border border-neutral-800 text-[11px] font-mono text-neutral-300 max-h-24 overflow-y-auto whitespace-pre-wrap break-all">
                            {rev.value_repr}
                          </div>

                          {canEdit && (
                            <div className="flex justify-end pt-1">
                              <button
                                type="button"
                                onClick={() => {
                                  if (detail.type === "string") {
                                    setEditString(rev.value_repr);
                                  } else if (detail.type === "json") {
                                    try {
                                      const parsed = JSON.parse(rev.value_repr);
                                      setEditJson(JSON.stringify(parsed, null, 2));
                                    } catch {
                                      setEditJson(rev.value_repr);
                                    }
                                  }
                                  setActiveTab("value");
                                  setSuccessMsg(`Loaded revision v${rev.version} into editor.`);
                                  setTimeout(() => setSuccessMsg(null), 3000);
                                }}
                                className="px-2.5 py-1 rounded bg-neutral-800 hover:bg-neutral-700 text-neutral-200 text-[11px] font-medium flex items-center gap-1 transition-colors"
                              >
                                <RotateCcw className="h-3 w-3" />
                                Load this version
                              </button>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </>
          ) : null}
        </div>

        {/* Footer */}
        {canEdit && detail && (
          <div className="p-4 border-t border-neutral-800 bg-neutral-950/80 flex items-center justify-between">
            <button
              onClick={handleDeleteKey}
              disabled={saving}
              className={`px-4 py-2 rounded-lg text-xs font-semibold uppercase tracking-wider flex items-center gap-2 transition-colors ${
                confirmDelete
                  ? "bg-red-600 text-white animate-pulse"
                  : "bg-red-500/10 text-red-400 border border-red-500/30 hover:bg-red-500/20"
              }`}
            >
              <Trash2 className="h-3.5 w-3.5" />
              <span>{confirmDelete ? "Confirm Delete Key" : "Delete Key"}</span>
            </button>
            <button
              onClick={onClose}
              className="px-4 py-2 rounded-lg bg-neutral-800 hover:bg-neutral-700 text-neutral-300 text-xs font-semibold uppercase tracking-wider transition-colors"
            >
              Close
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
