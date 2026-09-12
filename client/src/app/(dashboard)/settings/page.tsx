"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  AlertCircle,
  Check,
  Clock,
  Copy,
  Database,
  HardDrive,
  Key,
  Layers,
  Lock,
  Plus,
  RefreshCw,
  Save,
  Server,
  Settings as SettingsIcon,
  Shield,
  Sliders,
  Sparkles,
  Trash2,
  Users,
} from "lucide-react";
import { apiClient } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { ApiKeyItem, AuditLogItem, Role, User } from "@/lib/types";

export default function SettingsPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const isOperator = user?.role === "admin";

  const [activeTab, setActiveTab] = useState<
    "team" | "apikeys" | "eviction" | "persistence" | "ai" | "audit"
  >("team");

  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // 1. Team & RBAC State
  const [users, setUsers] = useState<User[]>([]);
  const [updatingUserId, setUpdatingUserId] = useState<string | null>(null);

  // 2. API Keys State
  const [apiKeys, setApiKeys] = useState<ApiKeyItem[]>([]);
  const [newKeyName, setNewKeyName] = useState("");
  const [newKeyRole, setNewKeyRole] = useState<Role>("developer");
  const [newKeyExpires, setNewKeyExpires] = useState(30);
  const [generatedKey, setGeneratedKey] = useState<string | null>(null);
  const [copiedKey, setCopiedKey] = useState(false);
  const [isCreatingKey, setIsCreatingKey] = useState(false);

  // 3. Eviction Policy State
  const [evictionData, setEvictionData] = useState<{
    policy: string;
    max_memory: number;
    evictions_total: number;
    weights: { frequency: number; recency: number; ttl: number; size: number };
  } | null>(null);
  const [selectedPolicy, setSelectedPolicy] = useState("ADAPTIVE");
  const [weightFrequency, setWeightFrequency] = useState(0.4);
  const [weightRecency, setWeightRecency] = useState(0.3);
  const [weightTtl, setWeightTtl] = useState(0.2);
  const [weightSize, setWeightSize] = useState(0.1);

  // 4. Persistence State
  const [persistenceData, setPersistenceData] = useState<any>(null);
  const [snapshotLoading, setSnapshotLoading] = useState(false);

  // 5. AI Settings State
  const [aiSettings, setAiSettings] = useState<{
    provider: string;
    is_configured: boolean;
    model: string;
    masked_api_key?: string;
  } | null>(null);
  const [newAiKey, setNewAiKey] = useState("");
  const [newAiModel, setNewAiModel] = useState("gemini-1.5-flash");

  // 6. Audit Log State
  const [auditLogs, setAuditLogs] = useState<AuditLogItem[]>([]);

  const fetchUsers = useCallback(async () => {
    if (!isAdmin) return;
    try {
      const res: User[] = await apiClient("/api/users");
      setUsers(res || []);
    } catch {
      setUsers([]);
    }
  }, [isAdmin]);

  const fetchApiKeys = useCallback(async () => {
    try {
      const res: ApiKeyItem[] = await apiClient("/api/auth/api-keys");
      setApiKeys(res || []);
    } catch {
      setApiKeys([]);
    }
  }, []);

  const fetchEviction = useCallback(async () => {
    try {
      const res = await apiClient("/api/eviction");
      setEvictionData(res);
      if (res?.policy) setSelectedPolicy(res.policy.toUpperCase());
      if (res?.weights) {
        setWeightFrequency(res.weights.frequency || 0.4);
        setWeightRecency(res.weights.recency || 0.3);
        setWeightTtl(res.weights.ttl || 0.2);
        setWeightSize(res.weights.size || 0.1);
      }
    } catch {}
  }, []);

  const fetchPersistence = useCallback(async () => {
    try {
      const res = await apiClient("/api/persistence");
      setPersistenceData(res);
    } catch {}
  }, []);

  const fetchAiSettings = useCallback(async () => {
    try {
      const res = await apiClient("/api/ai/settings");
      setAiSettings(res);
      if (res?.model) setNewAiModel(res.model);
    } catch {}
  }, []);

  const fetchAuditLogs = useCallback(async () => {
    if (!isOperator) return;
    try {
      const res: AuditLogItem[] = await apiClient("/api/audit-log?limit=50");
      setAuditLogs(res || []);
    } catch {}
  }, [isOperator]);

  useEffect(() => {
    if (activeTab === "team") fetchUsers();
    if (activeTab === "apikeys") fetchApiKeys();
    if (activeTab === "eviction") fetchEviction();
    if (activeTab === "persistence") fetchPersistence();
    if (activeTab === "ai") fetchAiSettings();
    if (activeTab === "audit") fetchAuditLogs();
  }, [
    activeTab,
    fetchUsers,
    fetchApiKeys,
    fetchEviction,
    fetchPersistence,
    fetchAiSettings,
    fetchAuditLogs,
  ]);

  const handleUpdateUserRole = async (userId: string, newRole: Role) => {
    setUpdatingUserId(userId);
    setErrorMsg(null);
    try {
      await apiClient(`/api/users/${userId}/role`, {
        method: "PATCH",
        body: JSON.stringify({ role: newRole }),
      });
      setSuccessMsg(`User role updated to ${newRole}`);
      setTimeout(() => setSuccessMsg(null), 3000);
      fetchUsers();
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to update user role");
    } finally {
      setUpdatingUserId(null);
    }
  };

  const handleCreateApiKey = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newKeyName.trim()) return;
    setLoading(true);
    setErrorMsg(null);
    try {
      const res: ApiKeyItem = await apiClient("/api/auth/api-keys", {
        method: "POST",
        body: JSON.stringify({
          name: newKeyName.trim(),
          role: newKeyRole,
          expires_in_days: newKeyExpires,
        }),
      });
      setGeneratedKey(res.key || null);
      setNewKeyName("");
      setIsCreatingKey(false);
      fetchApiKeys();
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to create API key");
    } finally {
      setLoading(false);
    }
  };

  const handleRevokeApiKey = async (keyId: string) => {
    try {
      await apiClient(`/api/auth/api-keys/${keyId}`, {
        method: "DELETE",
      });
      fetchApiKeys();
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to revoke key");
    }
  };

  const handleSaveEvictionPolicy = async () => {
    if (!isOperator) return;
    setLoading(true);
    setErrorMsg(null);
    try {
      await apiClient("/api/eviction/policy", {
        method: "PATCH",
        body: JSON.stringify({
          policy: selectedPolicy.toLowerCase(),
          weight_frequency: weightFrequency,
          weight_recency_age: weightRecency,
          weight_ttl_urgency: weightTtl,
          weight_size: weightSize,
        }),
      });
      setSuccessMsg("Eviction policy & weights saved successfully");
      setTimeout(() => setSuccessMsg(null), 3000);
      fetchEviction();
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to update eviction policy");
    } finally {
      setLoading(false);
    }
  };

  const handleTriggerSnapshot = async () => {
    if (!isOperator) return;
    setSnapshotLoading(true);
    setErrorMsg(null);
    try {
      const res = await apiClient<{ keys_saved: number }>("/api/persistence/snapshot", {
        method: "POST",
      });
      setSuccessMsg(`Background snapshot completed: ${res.keys_saved} keys persisted.`);
      setTimeout(() => setSuccessMsg(null), 3000);
      fetchPersistence();
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to trigger snapshot");
    } finally {
      setSnapshotLoading(false);
    }
  };

  const handleSaveAiConfig = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isAdmin) return;
    setLoading(true);
    setErrorMsg(null);
    try {
      await apiClient("/api/ai/settings", {
        method: "POST",
        body: JSON.stringify({
          api_key: newAiKey.trim() || undefined,
          model: newAiModel,
        }),
      });
      setSuccessMsg("Google Gemini AI settings updated.");
      setNewAiKey("");
      setTimeout(() => setSuccessMsg(null), 3000);
      fetchAiSettings();
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to update AI configuration");
    } finally {
      setLoading(false);
    }
  };

  const renderRoleBadge = (role: string) => {
    const styles: Record<string, string> = {
      admin: "bg-purple-500/10 text-purple-400 border-purple-500/30",
      developer: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
    };
    return (
      <span
        className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase tracking-wider border ${
          styles[role] || "bg-neutral-800 text-neutral-300"
        }`}
      >
        {role}
      </span>
    );
  };

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="p-6 rounded-2xl bg-neutral-900/60 border border-neutral-800 backdrop-blur flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-xl bg-red-600/20 border border-red-500/30 flex items-center justify-center text-red-400 shadow-lg shadow-red-600/10">
            <SettingsIcon className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-lg font-bold text-white">Platform Settings & Operations</h1>
            <p className="text-xs text-neutral-400 mt-0.5">
              Team RBAC, API keys, eviction tuning, persistence, and audit logging
            </p>
          </div>
        </div>
      </div>

      {/* Global Alerts */}
      {successMsg && (
        <div className="p-3.5 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-xs text-emerald-400 flex items-center gap-2">
          <Check className="h-4 w-4 shrink-0" />
          <span>{successMsg}</span>
        </div>
      )}

      {errorMsg && (
        <div className="p-3.5 rounded-xl bg-red-500/10 border border-red-500/30 text-xs text-red-400 flex items-center gap-2">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* Navigation Tabs */}
      <div className="flex items-center gap-2 overflow-x-auto pb-1 border-b border-neutral-800">
        <button
          onClick={() => setActiveTab("team")}
          className={`px-3.5 py-2 rounded-lg text-xs font-semibold flex items-center gap-2 transition-all ${
            activeTab === "team"
              ? "bg-red-600/20 text-red-400 border border-red-500/30"
              : "text-neutral-400 hover:text-white"
          }`}
        >
          <Users className="h-4 w-4" />
          Team & RBAC
        </button>
        <button
          onClick={() => setActiveTab("apikeys")}
          className={`px-3.5 py-2 rounded-lg text-xs font-semibold flex items-center gap-2 transition-all ${
            activeTab === "apikeys"
              ? "bg-red-600/20 text-red-400 border border-red-500/30"
              : "text-neutral-400 hover:text-white"
          }`}
        >
          <Key className="h-4 w-4" />
          API Keys
        </button>
        <button
          onClick={() => setActiveTab("eviction")}
          className={`px-3.5 py-2 rounded-lg text-xs font-semibold flex items-center gap-2 transition-all ${
            activeTab === "eviction"
              ? "bg-red-600/20 text-red-400 border border-red-500/30"
              : "text-neutral-400 hover:text-white"
          }`}
        >
          <Sliders className="h-4 w-4" />
          Eviction Policy
        </button>
        <button
          onClick={() => setActiveTab("persistence")}
          className={`px-3.5 py-2 rounded-lg text-xs font-semibold flex items-center gap-2 transition-all ${
            activeTab === "persistence"
              ? "bg-red-600/20 text-red-400 border border-red-500/30"
              : "text-neutral-400 hover:text-white"
          }`}
        >
          <HardDrive className="h-4 w-4" />
          Persistence
        </button>
        <button
          onClick={() => setActiveTab("ai")}
          className={`px-3.5 py-2 rounded-lg text-xs font-semibold flex items-center gap-2 transition-all ${
            activeTab === "ai"
              ? "bg-red-600/20 text-red-400 border border-red-500/30"
              : "text-neutral-400 hover:text-white"
          }`}
        >
          <Sparkles className="h-4 w-4" />
          AI Provider
        </button>
        <button
          onClick={() => setActiveTab("audit")}
          className={`px-3.5 py-2 rounded-lg text-xs font-semibold flex items-center gap-2 transition-all ${
            activeTab === "audit"
              ? "bg-red-600/20 text-red-400 border border-red-500/30"
              : "text-neutral-400 hover:text-white"
          }`}
        >
          <Shield className="h-4 w-4" />
          Audit Log
        </button>
      </div>

      {/* 1. TEAM & RBAC TAB */}
      {activeTab === "team" && (
        <div className="p-6 rounded-2xl bg-neutral-900/60 border border-neutral-800 backdrop-blur space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-sm font-bold text-white uppercase tracking-wider">
                Team Members & Roles
              </h2>
              <p className="text-xs text-neutral-400 mt-0.5">
                Hierarchical RBAC: Admin &gt; Developer
              </p>
            </div>
            {isAdmin && (
              <button
                onClick={fetchUsers}
                className="p-1.5 rounded-lg bg-neutral-950 border border-neutral-800 text-neutral-400 hover:text-white"
              >
                <RefreshCw className="h-4 w-4" />
              </button>
            )}
          </div>

          {!isAdmin ? (
            <div className="p-6 text-center text-xs text-neutral-400 border border-dashed border-neutral-800 rounded-xl">
              User management is restricted to Administrators.
            </div>
          ) : (
            <div className="overflow-x-auto rounded-xl border border-neutral-800 bg-neutral-950">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-neutral-800 bg-neutral-900/80 text-neutral-400 text-[11px] font-semibold uppercase tracking-wider">
                    <th className="py-3 px-4">User</th>
                    <th className="py-3 px-4">Email</th>
                    <th className="py-3 px-4">Current Role</th>
                    <th className="py-3 px-4">Member Since</th>
                    <th className="py-3 px-4 text-right">Modify Role</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-neutral-800/60">
                  {users.map((u) => (
                    <tr key={u.id} className="hover:bg-neutral-900/40">
                      <td className="py-3 px-4 font-semibold text-white">{u.name}</td>
                      <td className="py-3 px-4 font-mono text-neutral-400">{u.email}</td>
                      <td className="py-3 px-4">{renderRoleBadge(u.role)}</td>
                      <td className="py-3 px-4 font-mono text-neutral-500">
                        {new Date(u.created_at * 1000).toLocaleDateString()}
                      </td>
                      <td className="py-3 px-4 text-right">
                        <select
                          value={u.role}
                          disabled={updatingUserId === u.id || u.id === user?.id}
                          onChange={(e) =>
                            handleUpdateUserRole(u.id, e.target.value as Role)
                          }
                          className="px-2 py-1 bg-neutral-900 border border-neutral-700 rounded text-xs text-neutral-200 focus:outline-none focus:border-red-500 font-mono disabled:opacity-50"
                        >
                          <option value="admin">admin</option>
                          <option value="developer">developer</option>
                        </select>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* 2. API KEYS TAB */}
      {activeTab === "apikeys" && (
        <div className="space-y-4">
          {generatedKey && (
            <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-xs text-emerald-400 space-y-2">
              <div className="font-semibold flex items-center gap-1.5">
                <Check className="h-4 w-4" />
                <span>API Key generated! Copy it now as it won't be displayed again:</span>
              </div>
              <div className="flex items-center gap-2">
                <input
                  readOnly
                  value={generatedKey}
                  className="flex-1 px-3 py-2 bg-neutral-950 border border-neutral-800 rounded font-mono text-white text-xs select-all"
                />
                <button
                  onClick={() => {
                    navigator.clipboard.writeText(generatedKey);
                    setCopiedKey(true);
                    setTimeout(() => setCopiedKey(false), 2000);
                  }}
                  className="px-3 py-2 rounded bg-neutral-800 hover:bg-neutral-700 text-white font-medium"
                >
                  {copiedKey ? "Copied" : "Copy"}
                </button>
              </div>
            </div>
          )}

          <div className="p-6 rounded-2xl bg-neutral-900/60 border border-neutral-800 backdrop-blur space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-sm font-bold text-white uppercase tracking-wider">
                  Personal Scoped API Keys
                </h2>
                <p className="text-xs text-neutral-400 mt-0.5">
                  Programmatic Bearer tokens for external microservices and automated workers
                </p>
              </div>
              <button
                onClick={() => setIsCreatingKey(!isCreatingKey)}
                className="px-3 py-1.5 rounded-lg bg-red-600 hover:bg-red-500 text-xs font-semibold text-white flex items-center gap-1.5 transition-colors"
              >
                <Plus className="h-4 w-4" />
                <span>Generate Key</span>
              </button>
            </div>

            {isCreatingKey && (
              <form
                onSubmit={handleCreateApiKey}
                className="p-4 rounded-xl bg-neutral-950 border border-neutral-800 space-y-3"
              >
                <h3 className="text-xs font-bold text-white uppercase tracking-wider">
                  Create New Scoped API Key
                </h3>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  <input
                    type="text"
                    required
                    value={newKeyName}
                    onChange={(e) => setNewKeyName(e.target.value)}
                    placeholder="Key name (e.g. backend-worker)"
                    className="px-3 py-1.5 bg-neutral-900 border border-neutral-800 rounded-lg text-xs text-white placeholder-neutral-500"
                  />
                  <select
                    value={newKeyRole}
                    onChange={(e) => setNewKeyRole(e.target.value as Role)}
                    className="px-3 py-1.5 bg-neutral-900 border border-neutral-800 rounded-lg text-xs text-white"
                  >
                    <option value="developer">developer</option>
                    {isAdmin && <option value="admin">admin</option>}
                  </select>
                  <select
                    value={newKeyExpires}
                    onChange={(e) => setNewKeyExpires(parseInt(e.target.value, 10))}
                    className="px-3 py-1.5 bg-neutral-900 border border-neutral-800 rounded-lg text-xs text-white"
                  >
                    <option value={7}>Expires in 7 days</option>
                    <option value={30}>Expires in 30 days</option>
                    <option value={90}>Expires in 90 days</option>
                    <option value={365}>Expires in 1 year</option>
                  </select>
                </div>
                <div className="flex justify-end gap-2 pt-1">
                  <button
                    type="button"
                    onClick={() => setIsCreatingKey(false)}
                    className="px-3 py-1.5 rounded bg-neutral-800 text-xs text-neutral-300"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={loading}
                    className="px-4 py-1.5 rounded bg-red-600 hover:bg-red-500 text-xs font-semibold text-white"
                  >
                    Generate
                  </button>
                </div>
              </form>
            )}

            <div className="overflow-x-auto rounded-xl border border-neutral-800 bg-neutral-950">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-neutral-800 bg-neutral-900/80 text-neutral-400 text-[11px] font-semibold uppercase tracking-wider">
                    <th className="py-3 px-4">Name</th>
                    <th className="py-3 px-4">Prefix</th>
                    <th className="py-3 px-4">Scoped Role</th>
                    <th className="py-3 px-4">Created</th>
                    <th className="py-3 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-neutral-800/60">
                  {apiKeys.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="py-8 text-center text-neutral-500">
                        No active API keys generated yet.
                      </td>
                    </tr>
                  ) : (
                    apiKeys.map((k) => (
                      <tr key={k.id} className="hover:bg-neutral-900/40">
                        <td className="py-3 px-4 font-semibold text-white">{k.name}</td>
                        <td className="py-3 px-4 font-mono text-neutral-400">
                          {k.prefix}...
                        </td>
                        <td className="py-3 px-4">{renderRoleBadge(k.role)}</td>
                        <td className="py-3 px-4 font-mono text-neutral-500">
                          {new Date(k.created_at * 1000).toLocaleDateString()}
                        </td>
                        <td className="py-3 px-4 text-right">
                          <button
                            onClick={() => handleRevokeApiKey(k.id)}
                            className="p-1 text-neutral-500 hover:text-red-400 transition-colors"
                            title="Revoke Key"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* 3. EVICTION POLICY TAB */}
      {activeTab === "eviction" && (
        <div className="p-6 rounded-2xl bg-neutral-900/60 border border-neutral-800 backdrop-blur space-y-6">
          <div>
            <h2 className="text-sm font-bold text-white uppercase tracking-wider">
              Memory Eviction Engine Configuration
            </h2>
            <p className="text-xs text-neutral-400 mt-0.5">
              Select memory management policy and tune multi-factor adaptive weights
            </p>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-2">
            {["ADAPTIVE", "LRU", "LFU", "TTL", "RANDOM", "NOEVICTION"].map((pol) => (
              <button
                key={pol}
                type="button"
                onClick={() => setSelectedPolicy(pol)}
                className={`py-2 px-3 rounded-xl text-xs font-semibold uppercase border transition-all ${
                  selectedPolicy === pol
                    ? "bg-red-600 text-white border-red-500 shadow-md shadow-red-600/20"
                    : "bg-neutral-950 text-neutral-400 border-neutral-800 hover:bg-neutral-800"
                }`}
              >
                {pol}
              </button>
            ))}
          </div>

          {/* Adaptive Weight Sliders */}
          {selectedPolicy === "ADAPTIVE" && (
            <div className="p-5 rounded-xl bg-neutral-950 border border-neutral-800 space-y-4">
              <h3 className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-1.5">
                <Sliders className="h-4 w-4 text-amber-400" />
                Adaptive Eviction Weight Balancer
              </h3>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <div className="flex justify-between text-xs font-mono">
                    <span className="text-neutral-400">Frequency (LFU) Weight</span>
                    <span className="text-white font-bold">{weightFrequency.toFixed(2)}</span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.05"
                    value={weightFrequency}
                    onChange={(e) => setWeightFrequency(parseFloat(e.target.value))}
                    className="w-full accent-red-600 bg-neutral-800"
                  />
                </div>

                <div className="space-y-1.5">
                  <div className="flex justify-between text-xs font-mono">
                    <span className="text-neutral-400">Recency Age (LRU) Weight</span>
                    <span className="text-white font-bold">{weightRecency.toFixed(2)}</span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.05"
                    value={weightRecency}
                    onChange={(e) => setWeightRecency(parseFloat(e.target.value))}
                    className="w-full accent-red-600 bg-neutral-800"
                  />
                </div>

                <div className="space-y-1.5">
                  <div className="flex justify-between text-xs font-mono">
                    <span className="text-neutral-400">TTL Urgency Weight</span>
                    <span className="text-white font-bold">{weightTtl.toFixed(2)}</span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.05"
                    value={weightTtl}
                    onChange={(e) => setWeightTtl(parseFloat(e.target.value))}
                    className="w-full accent-red-600 bg-neutral-800"
                  />
                </div>

                <div className="space-y-1.5">
                  <div className="flex justify-between text-xs font-mono">
                    <span className="text-neutral-400">Size Penalty Weight</span>
                    <span className="text-white font-bold">{weightSize.toFixed(2)}</span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.05"
                    value={weightSize}
                    onChange={(e) => setWeightSize(parseFloat(e.target.value))}
                    className="w-full accent-red-600 bg-neutral-800"
                  />
                </div>
              </div>
            </div>
          )}

          {isOperator && (
            <button
              onClick={handleSaveEvictionPolicy}
              disabled={loading}
              className="px-5 py-2.5 rounded-xl bg-red-600 hover:bg-red-500 text-xs font-semibold text-white flex items-center gap-2 transition-colors disabled:opacity-50"
            >
              <Save className="h-4 w-4" />
              <span>Save Eviction Settings</span>
            </button>
          )}
        </div>
      )}

      {/* 4. PERSISTENCE TAB */}
      {activeTab === "persistence" && (
        <div className="p-6 rounded-2xl bg-neutral-900/60 border border-neutral-800 backdrop-blur space-y-6">
          <div>
            <h2 className="text-sm font-bold text-white uppercase tracking-wider">
              AOF & Snapshot Persistence Engine
            </h2>
            <p className="text-xs text-neutral-400 mt-0.5">
              Append-Only File fsync durability and asynchronous point-in-time snapshots
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="p-5 rounded-xl bg-neutral-950 border border-neutral-800 space-y-3">
              <h3 className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-1.5">
                <HardDrive className="h-4 w-4 text-emerald-400" />
                Append-Only File (AOF)
              </h3>
              <div className="space-y-1.5 text-xs text-neutral-300 font-mono">
                <div className="flex justify-between">
                  <span className="text-neutral-500">Status:</span>
                  <span className="text-emerald-400 font-bold">Enabled</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-neutral-500">Fsync Policy:</span>
                  <span>EverySec (1s async flush)</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-neutral-500">Auto-Rewrite:</span>
                  <span>Active on 100% growth</span>
                </div>
              </div>
            </div>

            <div className="p-5 rounded-xl bg-neutral-950 border border-neutral-800 space-y-3">
              <h3 className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-1.5">
                <Database className="h-4 w-4 text-cyan-400" />
                Point-In-Time Snapshots
              </h3>
              <div className="space-y-1.5 text-xs text-neutral-300 font-mono">
                <div className="flex justify-between">
                  <span className="text-neutral-500">Status:</span>
                  <span className="text-cyan-400 font-bold">Operational</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-neutral-500">Last Snapshot:</span>
                  <span>
                    {persistenceData?.snapshot?.last_save
                      ? new Date(persistenceData.snapshot.last_save * 1000).toLocaleTimeString()
                      : "Never"}
                  </span>
                </div>
              </div>
              {isOperator && (
                <button
                  onClick={handleTriggerSnapshot}
                  disabled={snapshotLoading}
                  className="w-full mt-2 py-2 px-3 rounded-lg bg-neutral-900 hover:bg-neutral-800 border border-neutral-700 text-xs font-semibold text-white flex items-center justify-center gap-2 transition-colors disabled:opacity-50"
                >
                  {snapshotLoading ? (
                    <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <HardDrive className="h-3.5 w-3.5" />
                  )}
                  <span>Trigger Manual BGSAVE</span>
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* 5. AI PROVIDER TAB */}
      {activeTab === "ai" && (
        <div className="p-6 rounded-2xl bg-neutral-900/60 border border-neutral-800 backdrop-blur space-y-6">
          <div>
            <h2 className="text-sm font-bold text-white uppercase tracking-wider">
              Google Gemini AI Integration
            </h2>
            <p className="text-xs text-neutral-400 mt-0.5">
              Configure generative models and semantic embedding engines for DBA intelligence
            </p>
          </div>

          <div className="p-5 rounded-xl bg-neutral-950 border border-neutral-800 space-y-3">
            <div className="flex items-center justify-between text-xs font-mono">
              <span className="text-neutral-400">AI Provider:</span>
              <span className="text-white font-bold">Google Gemini</span>
            </div>
            <div className="flex items-center justify-between text-xs font-mono">
              <span className="text-neutral-400">Configuration Status:</span>
              <span
                className={`font-bold ${
                  aiSettings?.is_configured ? "text-emerald-400" : "text-amber-400"
                }`}
              >
                {aiSettings?.is_configured ? "Active (Grounded)" : "Mock/Unconfigured"}
              </span>
            </div>
            <div className="flex items-center justify-between text-xs font-mono">
              <span className="text-neutral-400">Masked API Key:</span>
              <span className="text-neutral-300">
                {aiSettings?.masked_api_key || "No key registered"}
              </span>
            </div>
          </div>

          {isAdmin && (
            <form onSubmit={handleSaveAiConfig} className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-neutral-300 uppercase tracking-wider mb-1.5">
                    Gemini Model
                  </label>
                  <select
                    value={newAiModel}
                    onChange={(e) => setNewAiModel(e.target.value)}
                    className="w-full px-3.5 py-2 bg-neutral-950 border border-neutral-800 rounded-lg text-xs text-white"
                  >
                    <option value="gemini-1.5-flash">gemini-1.5-flash (Fast & responsive)</option>
                    <option value="gemini-1.5-pro">gemini-1.5-pro (Deep reasoning)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-neutral-300 uppercase tracking-wider mb-1.5">
                    Gemini API Key
                  </label>
                  <input
                    type="password"
                    value={newAiKey}
                    onChange={(e) => setNewAiKey(e.target.value)}
                    placeholder="Enter new Gemini API key to update..."
                    className="w-full px-3.5 py-2 bg-neutral-950 border border-neutral-800 rounded-lg text-xs text-white placeholder-neutral-500 font-mono"
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="px-5 py-2.5 rounded-xl bg-red-600 hover:bg-red-500 text-xs font-semibold text-white flex items-center gap-2 transition-colors disabled:opacity-50"
              >
                <Save className="h-4 w-4" />
                <span>Update AI Configuration</span>
              </button>
            </form>
          )}
        </div>
      )}

      {/* 6. AUDIT LOG TAB */}
      {activeTab === "audit" && (
        <div className="p-6 rounded-2xl bg-neutral-900/60 border border-neutral-800 backdrop-blur space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-sm font-bold text-white uppercase tracking-wider">
                Platform Security & Audit Trail
              </h2>
              <p className="text-xs text-neutral-400 mt-0.5">
                Cryptographically tracked record of all administrative, mutation, and authentication events
              </p>
            </div>
            {isOperator && (
              <button
                onClick={fetchAuditLogs}
                className="p-1.5 rounded-lg bg-neutral-950 border border-neutral-800 text-neutral-400 hover:text-white"
              >
                <RefreshCw className="h-4 w-4" />
              </button>
            )}
          </div>

          <div className="overflow-x-auto rounded-xl border border-neutral-800 bg-neutral-950 max-h-[500px]">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="border-b border-neutral-800 bg-neutral-900/80 text-neutral-400 text-[11px] font-semibold uppercase tracking-wider sticky top-0">
                  <th className="py-3 px-4">Timestamp</th>
                  <th className="py-3 px-4">Actor</th>
                  <th className="py-3 px-4">Action</th>
                  <th className="py-3 px-4">Target</th>
                  <th className="py-3 px-4">Outcome</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-800/60">
                {auditLogs.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="py-12 text-center text-neutral-500">
                      No security audit entries recorded yet.
                    </td>
                  </tr>
                ) : (
                  auditLogs.map((log) => (
                    <tr key={log.id} className="hover:bg-neutral-900/40">
                      <td className="py-2.5 px-4 font-mono text-neutral-500">
                        {new Date(log.timestamp * 1000).toLocaleTimeString()}
                      </td>
                      <td className="py-2.5 px-4 font-mono text-neutral-300">
                        {log.actor_email || log.actor_id} ({log.actor_role})
                      </td>
                      <td className="py-2.5 px-4 font-mono font-bold text-white">
                        {log.action}
                      </td>
                      <td className="py-2.5 px-4 font-mono text-neutral-400">
                        {log.target || "-"}
                      </td>
                      <td className="py-2.5 px-4">
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold ${
                            log.outcome === "SUCCESS"
                              ? "bg-emerald-500/15 text-emerald-400"
                              : "bg-red-500/15 text-red-400"
                          }`}
                        >
                          {log.outcome}
                        </span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
