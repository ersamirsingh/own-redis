"use client";

import React, { useEffect, useState, useMemo, useCallback } from "react";
import {
  AlertTriangle,
  ArrowUpDown,
  Clock,
  Database,
  Eye,
  Filter,
  Flame,
  Plus,
  RefreshCw,
  Search,
  Snowflake,
  Sun,
  Trash2,
} from "lucide-react";
import { apiClient } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { KeyItem, TelemetryData } from "@/lib/types";
import { useTelemetrySocket } from "@/lib/websocket";
import { CreateKeyModal } from "@/components/data/CreateKeyModal";
import { KeyEditor } from "@/components/data/KeyEditor";

type FilterType = "ALL" | "STRING" | "LIST" | "SET" | "HASH" | "ZSET" | "JSON";
type SortField = "key" | "memory" | "ttl" | "temp" | "access";
type SortOrder = "asc" | "desc";

export default function DataConsolePage() {
  const { user } = useAuth();
  const canWrite = user?.role === "admin" || user?.role === "developer";

  // Search & Filter States
  const [pattern, setPattern] = useState("*");
  const [searchInput, setSearchInput] = useState("*");
  const [selectedType, setSelectedType] = useState<FilterType>("ALL");
  const [sortField, setSortField] = useState<SortField>("access");
  const [sortOrder, setSortOrder] = useState<SortOrder>("desc");

  // Pagination
  const [page, setPage] = useState(1);
  const pageSize = 25;

  // Data States
  const [keys, setKeys] = useState<KeyItem[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Modals & Drawers
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [isEditorOpen, setIsEditorOpen] = useState(false);

  // Live Telemetry
  const { telemetry } = useTelemetrySocket();

  const fetchKeys = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const typeParam = selectedType === "ALL" ? "" : `&data_type=${selectedType.toLowerCase()}`;
      const url = `/api/keys?pattern=${encodeURIComponent(
        pattern.trim() || "*"
      )}${typeParam}&limit=500&offset=0`;
      const res = await apiClient<{ total: number; keys: KeyItem[] }>(url);
      setKeys(res.keys || []);
      setTotalCount(res.total || 0);
    } catch (err: any) {
      setError(err.message || "Failed to retrieve keys from PyRedis engine");
    } finally {
      setLoading(false);
    }
  }, [pattern, selectedType]);

  useEffect(() => {
    fetchKeys();
  }, [fetchKeys]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPattern(searchInput.trim() || "*");
    setPage(1);
  };

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortOrder(sortOrder === "asc" ? "desc" : "asc");
    } else {
      setSortField(field);
      setSortOrder("desc");
    }
  };

  // Sorted and Paginated keys
  const sortedKeys = useMemo(() => {
    return [...keys].sort((a, b) => {
      let comparison = 0;
      if (sortField === "key") {
        comparison = a.key.localeCompare(b.key);
      } else if (sortField === "memory") {
        comparison = a.memory_bytes - b.memory_bytes;
      } else if (sortField === "ttl") {
        const ttlA = a.ttl_seconds ?? Infinity;
        const ttlB = b.ttl_seconds ?? Infinity;
        comparison = ttlA - ttlB;
      } else if (sortField === "temp") {
        const order = { HOT: 3, WARM: 2, COLD: 1, UNKNOWN: 0 };
        comparison = (order[a.temperature] || 0) - (order[b.temperature] || 0);
      } else if (sortField === "access") {
        comparison = a.access_count - b.access_count;
      }
      return sortOrder === "asc" ? comparison : -comparison;
    });
  }, [keys, sortField, sortOrder]);

  const totalPages = Math.max(1, Math.ceil(sortedKeys.length / pageSize));
  const displayedKeys = useMemo(() => {
    const start = (page - 1) * pageSize;
    return sortedKeys.slice(start, start + pageSize);
  }, [sortedKeys, page, pageSize]);

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
        className={`px-2 py-0.5 rounded text-[11px] font-mono font-bold uppercase tracking-wider border ${
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
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-red-500/15 text-red-400 border border-red-500/30">
          <Flame className="h-3 w-3 text-red-400" />
          HOT
        </span>
      );
    }
    if (temp === "WARM") {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-amber-500/15 text-amber-400 border border-amber-500/30">
          <Sun className="h-3 w-3 text-amber-400" />
          WARM
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-blue-500/15 text-blue-400 border border-blue-500/30">
        <Snowflake className="h-3 w-3 text-blue-400" />
        COLD
      </span>
    );
  };

  const openEditor = (key: string) => {
    setSelectedKey(key);
    setIsEditorOpen(true);
  };

  return (
    <div className="space-y-6">
      {/* Top Banner Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="p-4 rounded-xl bg-neutral-900/60 border border-neutral-800 backdrop-blur">
          <div className="text-xs font-semibold text-neutral-400 uppercase tracking-wider">
            Total Keys
          </div>
          <div className="text-2xl font-bold font-mono text-white mt-1">
            {telemetry?.total_keys?.toLocaleString() ?? totalCount.toLocaleString()}
          </div>
          <div className="text-[11px] text-neutral-500 mt-1">Active in DataStore</div>
        </div>

        <div className="p-4 rounded-xl bg-neutral-900/60 border border-neutral-800 backdrop-blur">
          <div className="text-xs font-semibold text-neutral-400 uppercase tracking-wider">
            Matched Keys
          </div>
          <div className="text-2xl font-bold font-mono text-red-400 mt-1">
            {keys.length.toLocaleString()}
          </div>
          <div className="text-[11px] text-neutral-500 mt-1">Matching current filter</div>
        </div>

        <div className="p-4 rounded-xl bg-neutral-900/60 border border-neutral-800 backdrop-blur">
          <div className="text-xs font-semibold text-neutral-400 uppercase tracking-wider">
            RAM Used
          </div>
          <div className="text-2xl font-bold font-mono text-white mt-1">
            {telemetry?.memory_used_bytes ? formatBytes(telemetry.memory_used_bytes) : "0 B"}
          </div>
          <div className="text-[11px] text-neutral-500 mt-1">Resident heap allocation</div>
        </div>

        <div className="p-4 rounded-xl bg-neutral-900/60 border border-neutral-800 backdrop-blur">
          <div className="text-xs font-semibold text-neutral-400 uppercase tracking-wider">
            Hot Keys
          </div>
          <div className="text-2xl font-bold font-mono text-amber-400 mt-1">
            {telemetry?.temperature?.hot ?? keys.filter((k) => k.temperature === "HOT").length}
          </div>
          <div className="text-[11px] text-neutral-500 mt-1">High access frequency</div>
        </div>
      </div>

      {/* Main Container */}
      <div className="p-6 rounded-2xl bg-neutral-900/60 border border-neutral-800 backdrop-blur space-y-5">
        {/* Controls Bar */}
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          {/* Pattern Search Form */}
          <form onSubmit={handleSearchSubmit} className="flex items-center gap-2 flex-1 max-w-md">
            <div className="relative flex-1">
              <Search className="h-4 w-4 text-neutral-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                placeholder="Glob search (e.g. user:* or *)"
                className="w-full pl-9 pr-3.5 py-2 bg-neutral-950 border border-neutral-800 rounded-lg text-xs text-white placeholder-neutral-500 font-mono focus:outline-none focus:border-red-500 transition-colors"
              />
            </div>
            <button
              type="submit"
              className="px-3.5 py-2 rounded-lg bg-neutral-800 hover:bg-neutral-700 text-xs font-semibold text-neutral-200 transition-colors"
            >
              Search
            </button>
          </form>

          {/* Actions */}
          <div className="flex items-center gap-2.5">
            <button
              onClick={fetchKeys}
              disabled={loading}
              className="p-2 rounded-lg bg-neutral-950 border border-neutral-800 hover:bg-neutral-800 text-neutral-400 hover:text-white transition-colors"
              title="Refresh Keys"
            >
              <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            </button>

            {canWrite && (
              <button
                onClick={() => setIsCreateOpen(true)}
                className="px-3.5 py-2 rounded-lg bg-red-600 hover:bg-red-500 text-xs font-semibold text-white flex items-center gap-1.5 shadow-lg shadow-red-600/20 transition-all"
              >
                <Plus className="h-4 w-4" />
                <span>New Key</span>
              </button>
            )}
          </div>
        </div>

        {/* Type Filter Tabs */}
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 border-b border-neutral-800">
          {(["ALL", "STRING", "LIST", "SET", "HASH", "ZSET", "JSON"] as FilterType[]).map(
            (t) => (
              <button
                key={t}
                onClick={() => {
                  setSelectedType(t);
                  setPage(1);
                }}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                  selectedType === t
                    ? "bg-red-600/20 text-red-400 border border-red-500/30"
                    : "text-neutral-400 hover:text-neutral-200 hover:bg-neutral-800/60"
                }`}
              >
                {t}
              </button>
            )
          )}
        </div>

        {/* Error Alert */}
        {error && (
          <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/30 text-xs text-red-400 flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Table View */}
        <div className="overflow-x-auto rounded-xl border border-neutral-800 bg-neutral-950">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-neutral-800 bg-neutral-900/80 text-neutral-400 text-[11px] font-semibold uppercase tracking-wider">
                <th
                  onClick={() => handleSort("key")}
                  className="py-3 px-4 cursor-pointer hover:text-white transition-colors"
                >
                  <div className="flex items-center gap-1.5">
                    <span>Key Identifier</span>
                    <ArrowUpDown className="h-3 w-3" />
                  </div>
                </th>
                <th className="py-3 px-4">Type</th>
                <th
                  onClick={() => handleSort("memory")}
                  className="py-3 px-4 cursor-pointer hover:text-white transition-colors"
                >
                  <div className="flex items-center gap-1.5">
                    <span>Memory</span>
                    <ArrowUpDown className="h-3 w-3" />
                  </div>
                </th>
                <th
                  onClick={() => handleSort("ttl")}
                  className="py-3 px-4 cursor-pointer hover:text-white transition-colors"
                >
                  <div className="flex items-center gap-1.5">
                    <span>Expiration (TTL)</span>
                    <ArrowUpDown className="h-3 w-3" />
                  </div>
                </th>
                <th
                  onClick={() => handleSort("temp")}
                  className="py-3 px-4 cursor-pointer hover:text-white transition-colors"
                >
                  <div className="flex items-center gap-1.5">
                    <span>Temperature</span>
                    <ArrowUpDown className="h-3 w-3" />
                  </div>
                </th>
                <th
                  onClick={() => handleSort("access")}
                  className="py-3 px-4 cursor-pointer hover:text-white transition-colors"
                >
                  <div className="flex items-center gap-1.5">
                    <span>Accesses</span>
                    <ArrowUpDown className="h-3 w-3" />
                  </div>
                </th>
                <th className="py-3 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-800/60 text-xs">
              {loading && keys.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-16 text-center text-neutral-500">
                    <RefreshCw className="h-6 w-6 animate-spin mx-auto mb-2 text-neutral-400" />
                    Scanning PyRedis database keys...
                  </td>
                </tr>
              ) : displayedKeys.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-16 text-center text-neutral-500">
                    <Database className="h-8 w-8 mx-auto mb-2 text-neutral-600" />
                    <p className="font-semibold text-neutral-300">No keys found</p>
                    <p className="text-xs text-neutral-500 mt-1">
                      No keys match pattern "{pattern}" and filter "{selectedType}".
                    </p>
                    {canWrite && (
                      <button
                        onClick={() => setIsCreateOpen(true)}
                        className="mt-4 px-3.5 py-1.5 rounded-lg bg-neutral-800 hover:bg-neutral-700 text-xs font-medium text-neutral-200 transition-colors"
                      >
                        Create First Key
                      </button>
                    )}
                  </td>
                </tr>
              ) : (
                displayedKeys.map((item) => (
                  <tr
                    key={item.key}
                    onClick={() => openEditor(item.key)}
                    className="hover:bg-neutral-900/80 cursor-pointer transition-colors group"
                  >
                    <td className="py-3 px-4 font-mono font-semibold text-white max-w-xs truncate">
                      {item.key}
                    </td>
                    <td className="py-3 px-4">{renderTypeBadge(item.type)}</td>
                    <td className="py-3 px-4 font-mono text-neutral-300">
                      {formatBytes(item.memory_bytes)}
                    </td>
                    <td className="py-3 px-4 font-mono text-amber-400">
                      {formatTtl(item.ttl_seconds)}
                    </td>
                    <td className="py-3 px-4">{renderTempBadge(item.temperature)}</td>
                    <td className="py-3 px-4 font-mono text-neutral-400">
                      {item.access_count.toLocaleString()}
                    </td>
                    <td className="py-3 px-4 text-right">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          openEditor(item.key);
                        }}
                        className="p-1.5 rounded-lg text-neutral-400 hover:text-white hover:bg-neutral-800 transition-colors"
                        title="Inspect & Edit Key"
                      >
                        <Eye className="h-4 w-4" />
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Footer */}
        {sortedKeys.length > pageSize && (
          <div className="flex items-center justify-between pt-2">
            <div className="text-xs text-neutral-500">
              Showing {(page - 1) * pageSize + 1} to{" "}
              {Math.min(page * pageSize, sortedKeys.length)} of {sortedKeys.length} keys
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="px-3 py-1.5 rounded-lg bg-neutral-950 border border-neutral-800 text-xs text-neutral-400 hover:text-white disabled:opacity-40 transition-colors"
              >
                Previous
              </button>
              <span className="text-xs font-mono text-neutral-400">
                Page {page} of {totalPages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
                className="px-3 py-1.5 rounded-lg bg-neutral-950 border border-neutral-800 text-xs text-neutral-400 hover:text-white disabled:opacity-40 transition-colors"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Create Key Modal */}
      <CreateKeyModal
        isOpen={isCreateOpen}
        onClose={() => setIsCreateOpen(false)}
        onSuccess={() => {
          fetchKeys();
        }}
      />

      {/* Key Editor Drawer */}
      <KeyEditor
        keyName={selectedKey}
        isOpen={isEditorOpen}
        onClose={() => {
          setIsEditorOpen(false);
          setSelectedKey(null);
        }}
        onKeyUpdated={() => {
          fetchKeys();
        }}
        onKeyDeleted={() => {
          fetchKeys();
        }}
      />
    </div>
  );
}
