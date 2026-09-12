"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  AlertCircle,
  Check,
  Clock,
  Copy,
  KeyRound,
  Lock,
  Plus,
  RefreshCw,
  RotateCw,
  ShieldAlert,
  Unlock,
  X,
  Zap,
} from "lucide-react";
import { apiClient } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { DistributedLockItem } from "@/lib/types";

export default function DistributedLocksPage() {
  const { user } = useAuth();
  const canForceRelease = user?.role === "admin";
  const canAcquire = user?.role === "admin" || user?.role === "developer";

  const [locks, setLocks] = useState<DistributedLockItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Modal State
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [newKey, setNewKey] = useState("");
  const [newOwner, setNewOwner] = useState("");
  const [newTtlMs, setNewTtlMs] = useState(30000);
  const [modalLoading, setModalLoading] = useState(false);
  const [modalError, setModalError] = useState<string | null>(null);

  // Force break state
  const [confirmKey, setConfirmKey] = useState<string | null>(null);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  const fetchLocks = useCallback(async () => {
    try {
      const res: DistributedLockItem[] = await apiClient("/api/locks");
      setLocks(res || []);
      setError(null);
    } catch (err: any) {
      setError(err.message || "Failed to query distributed locks");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchLocks();
    const timer = setInterval(() => {
      fetchLocks();
    }, 2000);
    return () => clearInterval(timer);
  }, [fetchLocks]);

  const handleAcquireLock = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newKey.trim() || !newOwner.trim()) {
      setModalError("Key name and owner identifier are required.");
      return;
    }

    setModalLoading(true);
    setModalError(null);

    try {
      const res = await apiClient<{ result: number }>("/api/commands", {
        method: "POST",
        body: JSON.stringify({
          command: `LOCK "${newKey.trim()}" "${newOwner.trim()}" ${newTtlMs}`,
        }),
      });

      if (res.result === 1) {
        setSuccessMsg(`Lock acquired successfully on '${newKey.trim()}'.`);
        setTimeout(() => setSuccessMsg(null), 3000);
        setIsModalOpen(false);
        setNewKey("");
        setNewOwner("");
        fetchLocks();
      } else {
        setModalError(`Failed to acquire lock: Resource is already locked by another owner.`);
      }
    } catch (err: any) {
      setModalError(err.message || "Failed to acquire lock");
    } finally {
      setModalLoading(false);
    }
  };

  const handleReleaseLock = async (key: string, owner: string) => {
    try {
      const res = await apiClient<{ result: number }>("/api/commands", {
        method: "POST",
        body: JSON.stringify({
          command: `UNLOCK "${key}" "${owner}"`,
        }),
      });

      if (res.result === 1) {
        setSuccessMsg(`Lock '${key}' released by owner.`);
        setTimeout(() => setSuccessMsg(null), 3000);
        fetchLocks();
      } else {
        setError(`Cannot release lock '${key}': Owner token verification failed.`);
      }
    } catch (err: any) {
      setError(err.message || "Failed to release lock");
    }
  };

  const handleExtendLock = async (key: string, owner: string, extendMs: number = 15000) => {
    try {
      const res = await apiClient<{ result: number }>("/api/commands", {
        method: "POST",
        body: JSON.stringify({
          command: `LOCK.EXTEND "${key}" "${owner}" ${extendMs}`,
        }),
      });

      if (res.result === 1) {
        setSuccessMsg(`Lease extended for '${key}' (+${extendMs / 1000}s).`);
        setTimeout(() => setSuccessMsg(null), 3000);
        fetchLocks();
      } else {
        setError(`Failed to extend lease for '${key}'.`);
      }
    } catch (err: any) {
      setError(err.message || "Failed to extend lock");
    }
  };

  const handleForceRelease = async (key: string) => {
    if (confirmKey !== key) {
      setConfirmKey(key);
      return;
    }

    try {
      await apiClient("/api/locks/force-release", {
        method: "POST",
        body: JSON.stringify({ key }),
      });
      setSuccessMsg(`Lock '${key}' forcefully released by administrator.`);
      setTimeout(() => setSuccessMsg(null), 3000);
      setConfirmKey(null);
      fetchLocks();
    } catch (err: any) {
      setError(err.message || "Failed to force-release lock");
    }
  };

  const handleCopy = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedKey(id);
    setTimeout(() => setCopiedKey(null), 2000);
  };

  const expiringSoonCount = locks.filter((l) => l.ttl_remaining_ms < 10000).length;

  return (
    <div className="space-y-6">
      {/* Overview Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="p-4 rounded-xl bg-neutral-900/60 border border-neutral-800 backdrop-blur">
          <div className="text-xs font-semibold text-neutral-400 uppercase tracking-wider">
            Active Leases
          </div>
          <div className="text-2xl font-bold font-mono text-white mt-1">
            {locks.length.toLocaleString()}
          </div>
          <div className="text-[11px] text-neutral-500 mt-1">Acquired distributed locks</div>
        </div>

        <div className="p-4 rounded-xl bg-neutral-900/60 border border-neutral-800 backdrop-blur">
          <div className="text-xs font-semibold text-neutral-400 uppercase tracking-wider">
            Expiring Soon
          </div>
          <div className="text-2xl font-bold font-mono text-amber-400 mt-1">
            {expiringSoonCount}
          </div>
          <div className="text-[11px] text-neutral-500 mt-1">Lease remaining &lt; 10s</div>
        </div>

        <div className="p-4 rounded-xl bg-neutral-900/60 border border-neutral-800 backdrop-blur">
          <div className="text-xs font-semibold text-neutral-400 uppercase tracking-wider">
            Safety Algorithm
          </div>
          <div className="text-sm font-semibold font-mono text-emerald-400 mt-2">
            Owner Fencing
          </div>
          <div className="text-[11px] text-neutral-500 mt-1">Cryptographic token check</div>
        </div>

        <div className="p-4 rounded-xl bg-neutral-900/60 border border-neutral-800 backdrop-blur">
          <div className="text-xs font-semibold text-neutral-400 uppercase tracking-wider">
            Re-entrancy
          </div>
          <div className="text-sm font-semibold font-mono text-purple-400 mt-2">
            Supported
          </div>
          <div className="text-[11px] text-neutral-500 mt-1">Same owner auto-refreshes</div>
        </div>
      </div>

      {/* Main Locks Container */}
      <div className="p-6 rounded-2xl bg-neutral-900/60 border border-neutral-800 backdrop-blur space-y-5">
        {/* Header Bar */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h2 className="text-base font-bold text-white flex items-center gap-2">
              <Lock className="h-4 w-4 text-red-500" />
              Distributed Locks Subsystem
            </h2>
            <p className="text-xs text-neutral-400 mt-0.5">
              Atomic coordination with lease timeout expiration and owner verification
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={fetchLocks}
              disabled={loading}
              className="p-2 rounded-lg bg-neutral-950 border border-neutral-800 hover:bg-neutral-800 text-neutral-400 hover:text-white transition-colors"
              title="Refresh Locks"
            >
              <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            </button>

            {canAcquire && (
              <button
                onClick={() => {
                  setNewKey(`resource:order:${Math.floor(1000 + Math.random() * 9000)}`);
                  setNewOwner(`worker-pod-${Math.random().toString(36).substring(2, 6)}`);
                  setModalError(null);
                  setIsModalOpen(true);
                }}
                className="px-3.5 py-2 rounded-lg bg-red-600 hover:bg-red-500 text-xs font-semibold text-white flex items-center gap-1.5 shadow-lg shadow-red-600/20 transition-all"
              >
                <Plus className="h-4 w-4" />
                <span>Acquire Lock</span>
              </button>
            )}
          </div>
        </div>

        {/* Alerts */}
        {error && (
          <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/30 text-xs text-red-400 flex items-center gap-2">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {successMsg && (
          <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-xs text-emerald-400 flex items-center gap-2">
            <Check className="h-4 w-4 shrink-0" />
            <span>{successMsg}</span>
          </div>
        )}

        {/* Locks Table */}
        <div className="overflow-x-auto rounded-xl border border-neutral-800 bg-neutral-950">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-neutral-800 bg-neutral-900/80 text-neutral-400 text-[11px] font-semibold uppercase tracking-wider">
                <th className="py-3 px-4">Resource Key</th>
                <th className="py-3 px-4">Owner Token</th>
                <th className="py-3 px-4">Acquired At</th>
                <th className="py-3 px-4">Remaining Lease</th>
                <th className="py-3 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-800/60 text-xs">
              {loading && locks.length === 0 ? (
                <tr>
                  <td colSpan={5} className="py-16 text-center text-neutral-500">
                    <RefreshCw className="h-6 w-6 animate-spin mx-auto mb-2 text-neutral-400" />
                    Checking distributed lock leases...
                  </td>
                </tr>
              ) : locks.length === 0 ? (
                <tr>
                  <td colSpan={5} className="py-16 text-center text-neutral-500">
                    <Lock className="h-8 w-8 mx-auto mb-2 text-neutral-700" />
                    <p className="font-semibold text-neutral-300">No active distributed locks</p>
                    <p className="text-xs text-neutral-500 mt-1">
                      No resources are currently leased by any worker.
                    </p>
                    {canAcquire && (
                      <button
                        onClick={() => {
                          setNewKey(`resource:order:${Math.floor(1000 + Math.random() * 9000)}`);
                          setNewOwner(`worker-pod-${Math.random().toString(36).substring(2, 6)}`);
                          setModalError(null);
                          setIsModalOpen(true);
                        }}
                        className="mt-4 px-3.5 py-1.5 rounded-lg bg-neutral-800 hover:bg-neutral-700 text-xs font-medium text-neutral-200 transition-colors"
                      >
                        Acquire Demo Lock
                      </button>
                    )}
                  </td>
                </tr>
              ) : (
                locks.map((lock) => {
                  const remainingSec = Math.max(0, lock.ttl_remaining_ms / 1000);
                  const isExpiring = remainingSec < 10;

                  return (
                    <tr key={lock.key} className="hover:bg-neutral-900/60 transition-colors">
                      <td className="py-3 px-4 font-mono font-semibold text-white">
                        <div className="flex items-center gap-1.5">
                          <Lock className="h-3.5 w-3.5 text-red-400 shrink-0" />
                          <span className="truncate max-w-xs">{lock.key}</span>
                          <button
                            onClick={() => handleCopy(lock.key, `key-${lock.key}`)}
                            className="p-1 text-neutral-500 hover:text-white"
                          >
                            {copiedKey === `key-${lock.key}` ? (
                              <Check className="h-3 w-3 text-emerald-400" />
                            ) : (
                              <Copy className="h-3 w-3" />
                            )}
                          </button>
                        </div>
                      </td>

                      <td className="py-3 px-4 font-mono text-neutral-300">
                        <div className="flex items-center gap-1.5">
                          <span className="px-2 py-0.5 rounded bg-neutral-900 border border-neutral-800 text-xs">
                            {lock.owner}
                          </span>
                          <button
                            onClick={() => handleCopy(lock.owner, `owner-${lock.key}`)}
                            className="p-1 text-neutral-500 hover:text-white"
                          >
                            {copiedKey === `owner-${lock.key}` ? (
                              <Check className="h-3 w-3 text-emerald-400" />
                            ) : (
                              <Copy className="h-3 w-3" />
                            )}
                          </button>
                        </div>
                      </td>

                      <td className="py-3 px-4 font-mono text-neutral-400">
                        {new Date(lock.acquired_at * 1000).toLocaleTimeString()}
                      </td>

                      <td className="py-3 px-4">
                        <div className="space-y-1 max-w-xs">
                          <div className="flex items-center justify-between text-[11px] font-mono">
                            <span
                              className={`font-semibold ${
                                isExpiring ? "text-red-400 animate-pulse" : "text-amber-400"
                              }`}
                            >
                              {remainingSec.toFixed(1)}s left
                            </span>
                            <span className="text-neutral-500">
                              exp: {new Date(lock.expires_at * 1000).toLocaleTimeString()}
                            </span>
                          </div>
                          <div className="h-1.5 w-full bg-neutral-900 rounded-full overflow-hidden">
                            <div
                              className={`h-full rounded-full transition-all duration-500 ${
                                isExpiring ? "bg-red-500" : "bg-amber-400"
                              }`}
                              style={{
                                width: `${Math.min(100, (lock.ttl_remaining_ms / 30000) * 100)}%`,
                              }}
                            />
                          </div>
                        </div>
                      </td>

                      <td className="py-3 px-4 text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          {/* Extend Lease */}
                          <button
                            onClick={() => handleExtendLock(lock.key, lock.owner, 15000)}
                            className="px-2.5 py-1 rounded bg-neutral-900 hover:bg-neutral-800 border border-neutral-800 text-neutral-300 hover:text-white text-[11px] font-medium flex items-center gap-1 transition-colors"
                            title="Extend lease by +15s"
                          >
                            <RotateCw className="h-3 w-3 text-amber-400" />
                            <span>+15s</span>
                          </button>

                          {/* Normal Release by Owner */}
                          <button
                            onClick={() => handleReleaseLock(lock.key, lock.owner)}
                            className="px-2.5 py-1 rounded bg-neutral-900 hover:bg-neutral-800 border border-neutral-800 text-neutral-300 hover:text-white text-[11px] font-medium flex items-center gap-1 transition-colors"
                            title="Release lock as owner"
                          >
                            <Unlock className="h-3 w-3 text-emerald-400" />
                            <span>Release</span>
                          </button>

                          {/* Force Break (Admin / Operator) */}
                          {canForceRelease && (
                            <button
                              onClick={() => handleForceRelease(lock.key)}
                              className={`px-2.5 py-1 rounded text-[11px] font-semibold flex items-center gap-1 transition-colors ${
                                confirmKey === lock.key
                                  ? "bg-red-600 text-white animate-pulse"
                                  : "bg-red-500/10 text-red-400 hover:bg-red-500/20 border border-red-500/30"
                              }`}
                              title="Force break active lock"
                            >
                              <ShieldAlert className="h-3 w-3" />
                              <span>{confirmKey === lock.key ? "Confirm Break" : "Force Break"}</span>
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Acquire Lock Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-in fade-in duration-100">
          <div className="w-full max-w-md bg-neutral-900 border border-neutral-800 rounded-2xl shadow-2xl overflow-hidden flex flex-col">
            <div className="px-6 py-4 border-b border-neutral-800 flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="h-8 w-8 rounded-lg bg-red-500/10 border border-red-500/20 flex items-center justify-center">
                  <Lock className="h-4 w-4 text-red-400" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-white">Acquire Distributed Lock</h3>
                  <p className="text-xs text-neutral-400">Lease a shared resource safely</p>
                </div>
              </div>
              <button
                onClick={() => setIsModalOpen(false)}
                className="p-1.5 rounded-lg text-neutral-400 hover:text-white hover:bg-neutral-800 transition-colors"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <form onSubmit={handleAcquireLock} className="p-6 space-y-4">
              {modalError && (
                <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-xs text-red-400 flex items-center gap-2">
                  <AlertCircle className="h-4 w-4 shrink-0" />
                  <span>{modalError}</span>
                </div>
              )}

              <div>
                <label className="block text-xs font-semibold text-neutral-300 uppercase tracking-wider mb-1.5">
                  Resource Key
                </label>
                <input
                  type="text"
                  required
                  value={newKey}
                  onChange={(e) => setNewKey(e.target.value)}
                  placeholder="e.g. order:checkout:1002"
                  className="w-full px-3.5 py-2 bg-neutral-950 border border-neutral-800 rounded-lg text-sm text-white placeholder-neutral-500 font-mono focus:outline-none focus:border-red-500 transition-colors"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-neutral-300 uppercase tracking-wider mb-1.5">
                  Owner Token Identifier
                </label>
                <input
                  type="text"
                  required
                  value={newOwner}
                  onChange={(e) => setNewOwner(e.target.value)}
                  placeholder="e.g. worker-node-1"
                  className="w-full px-3.5 py-2 bg-neutral-950 border border-neutral-800 rounded-lg text-sm text-white placeholder-neutral-500 font-mono focus:outline-none focus:border-red-500 transition-colors"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-neutral-300 uppercase tracking-wider mb-1.5">
                  Lease Duration (TTL)
                </label>
                <div className="grid grid-cols-4 gap-2">
                  {[
                    { label: "5s", ms: 5000 },
                    { label: "15s", ms: 15000 },
                    { label: "30s", ms: 30000 },
                    { label: "60s", ms: 60000 },
                  ].map((preset) => (
                    <button
                      key={preset.ms}
                      type="button"
                      onClick={() => setNewTtlMs(preset.ms)}
                      className={`py-1.5 px-2 rounded-lg text-xs font-semibold font-mono border transition-all ${
                        newTtlMs === preset.ms
                          ? "bg-red-600 text-white border-red-500"
                          : "bg-neutral-950 text-neutral-400 border-neutral-800 hover:bg-neutral-800"
                      }`}
                    >
                      {preset.label}
                    </button>
                  ))}
                </div>
              </div>

              <div className="pt-2 flex items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="px-4 py-2 rounded-lg bg-neutral-800 hover:bg-neutral-700 text-xs font-semibold text-neutral-300 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={modalLoading}
                  className="px-4 py-2 rounded-lg bg-red-600 hover:bg-red-500 text-xs font-semibold text-white flex items-center gap-1.5 transition-colors disabled:opacity-50"
                >
                  {modalLoading && <RefreshCw className="h-3.5 w-3.5 animate-spin" />}
                  <span>Acquire Lock</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
