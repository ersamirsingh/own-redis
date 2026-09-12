"use client";

import React, { useState } from "react";
import { Clock, Database, Plus, Trash2, X } from "lucide-react";
import { apiClient } from "@/lib/api";

interface CreateKeyModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

type DataType = "string" | "list" | "set" | "hash" | "zset" | "json";

export function CreateKeyModal({ isOpen, onClose, onSuccess }: CreateKeyModalProps) {
  const [key, setKey] = useState("");
  const [type, setType] = useState<DataType>("string");
  const [ttlPreset, setTtlPreset] = useState<string>("none");
  const [customTtl, setCustomTtl] = useState<string>("");

  // Type specific states
  const [stringValue, setStringValue] = useState("");
  const [listItems, setListItems] = useState<string[]>([""]);
  const [setMembers, setSetMembers] = useState<string[]>([""]);
  const [hashEntries, setHashEntries] = useState<Array<{ field: string; value: string }>>([
    { field: "", value: "" },
  ]);
  const [zsetEntries, setZsetEntries] = useState<Array<{ member: string; score: number }>>([
    { member: "", score: 1 },
  ]);
  const [jsonValue, setJsonValue] = useState("{\n  \"example\": \"value\"\n}");

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!key.trim()) {
      setError("Key name is required.");
      return;
    }

    let calculatedTtl: number | null = null;
    if (ttlPreset === "custom") {
      const val = parseInt(customTtl, 10);
      if (isNaN(val) || val <= 0) {
        setError("Please enter a valid positive TTL in seconds.");
        return;
      }
      calculatedTtl = val;
    } else if (ttlPreset !== "none") {
      calculatedTtl = parseInt(ttlPreset, 10);
    }

    let payloadValue: any;
    try {
      if (type === "string") {
        payloadValue = stringValue;
      } else if (type === "list") {
        payloadValue = listItems.map((i) => i.trim()).filter(Boolean);
      } else if (type === "set") {
        payloadValue = setMembers.map((m) => m.trim()).filter(Boolean);
      } else if (type === "hash") {
        const mapping: Record<string, string> = {};
        for (const entry of hashEntries) {
          if (entry.field.trim()) {
            mapping[entry.field.trim()] = entry.value;
          }
        }
        payloadValue = mapping;
      } else if (type === "zset") {
        payloadValue = zsetEntries
          .filter((z) => z.member.trim())
          .map((z) => ({ member: z.member.trim(), score: z.score }));
      } else if (type === "json") {
        payloadValue = JSON.parse(jsonValue);
      }
    } catch (err: any) {
      setError(`Invalid value: ${err.message}`);
      return;
    }

    setLoading(true);
    try {
      await apiClient("/api/keys", {
        method: "POST",
        body: JSON.stringify({
          key: key.trim(),
          type,
          value: payloadValue,
          ttl_seconds: calculatedTtl,
        }),
      });

      onSuccess();
      onClose();
    } catch (err: any) {
      setError(err.message || "Failed to create key");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-in fade-in duration-100">
      <div className="w-full max-w-xl bg-neutral-900 border border-neutral-800 rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Modal Header */}
        <div className="px-6 py-4 border-b border-neutral-800 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="h-8 w-8 rounded-lg bg-red-500/10 border border-red-500/20 flex items-center justify-center">
              <Database className="h-4 w-4 text-red-400" />
            </div>
            <div>
              <h2 className="text-base font-bold text-white">Create New Key</h2>
              <p className="text-xs text-neutral-400">Initialize a typed in-memory record</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-neutral-400 hover:text-white hover:bg-neutral-800 transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Modal Body */}
        <form onSubmit={handleSubmit} className="p-6 space-y-5 overflow-y-auto flex-1">
          {error && (
            <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-xs text-red-400">
              {error}
            </div>
          )}

          {/* Key Name Input */}
          <div>
            <label className="block text-xs font-semibold text-neutral-300 uppercase tracking-wider mb-1.5">
              Key Identifier
            </label>
            <input
              type="text"
              required
              value={key}
              onChange={(e) => setKey(e.target.value)}
              placeholder="e.g. user:1001:profile or app:config"
              className="w-full px-3.5 py-2 bg-neutral-950 border border-neutral-800 rounded-lg text-sm text-white placeholder-neutral-500 focus:outline-none focus:border-red-500 transition-colors font-mono"
            />
          </div>

          {/* Type Selector Pills */}
          <div>
            <label className="block text-xs font-semibold text-neutral-300 uppercase tracking-wider mb-1.5">
              Data Structure Type
            </label>
            <div className="grid grid-cols-3 sm:grid-cols-6 gap-2">
              {(["string", "list", "set", "hash", "zset", "json"] as DataType[]).map((t) => (
                <button
                  type="button"
                  key={t}
                  onClick={() => setType(t)}
                  className={`py-1.5 px-2 rounded-lg text-xs font-semibold uppercase tracking-wider border transition-all ${
                    type === t
                      ? "bg-red-600 text-white border-red-500 shadow-md shadow-red-600/20"
                      : "bg-neutral-950 text-neutral-400 border-neutral-800 hover:bg-neutral-800 hover:text-neutral-200"
                  }`}
                >
                  {t}
                </button>
              ))}
            </div>
          </div>

          {/* TTL Selector */}
          <div>
            <label className="block text-xs font-semibold text-neutral-300 uppercase tracking-wider mb-1.5 flex items-center gap-1.5">
              <Clock className="h-3.5 w-3.5 text-neutral-400" />
              Time-To-Live (Expiration)
            </label>
            <div className="grid grid-cols-5 gap-2">
              {[
                { label: "No TTL", val: "none" },
                { label: "60s", val: "60" },
                { label: "5m", val: "300" },
                { label: "1h", val: "3600" },
                { label: "Custom", val: "custom" },
              ].map((opt) => (
                <button
                  type="button"
                  key={opt.val}
                  onClick={() => setTtlPreset(opt.val)}
                  className={`py-1.5 px-2 rounded-lg text-xs font-medium border transition-colors ${
                    ttlPreset === opt.val
                      ? "bg-neutral-800 text-red-400 border-red-500/40"
                      : "bg-neutral-950 text-neutral-400 border-neutral-800 hover:bg-neutral-800"
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
            {ttlPreset === "custom" && (
              <input
                type="number"
                min="1"
                value={customTtl}
                onChange={(e) => setCustomTtl(e.target.value)}
                placeholder="Enter expiration duration in seconds"
                className="mt-2 w-full px-3.5 py-2 bg-neutral-950 border border-neutral-800 rounded-lg text-sm text-white placeholder-neutral-500 focus:outline-none focus:border-red-500 transition-colors font-mono"
              />
            )}
          </div>

          {/* Type-Specific Initial Value Inputs */}
          <div>
            <label className="block text-xs font-semibold text-neutral-300 uppercase tracking-wider mb-1.5">
              Initial Payload
            </label>

            {type === "string" && (
              <textarea
                rows={3}
                value={stringValue}
                onChange={(e) => setStringValue(e.target.value)}
                placeholder="Enter string value..."
                className="w-full px-3.5 py-2 bg-neutral-950 border border-neutral-800 rounded-lg text-sm text-white placeholder-neutral-500 focus:outline-none focus:border-red-500 transition-colors font-mono"
              />
            )}

            {type === "list" && (
              <div className="space-y-2">
                {listItems.map((item, idx) => (
                  <div key={idx} className="flex items-center gap-2">
                    <input
                      type="text"
                      value={item}
                      onChange={(e) => {
                        const updated = [...listItems];
                        updated[idx] = e.target.value;
                        setListItems(updated);
                      }}
                      placeholder={`Element #${idx + 1}`}
                      className="flex-1 px-3.5 py-1.5 bg-neutral-950 border border-neutral-800 rounded-lg text-xs text-white placeholder-neutral-500 font-mono"
                    />
                    {listItems.length > 1 && (
                      <button
                        type="button"
                        onClick={() => setListItems(listItems.filter((_, i) => i !== idx))}
                        className="p-1.5 text-neutral-500 hover:text-red-400"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    )}
                  </div>
                ))}
                <button
                  type="button"
                  onClick={() => setListItems([...listItems, ""])}
                  className="text-xs text-red-400 hover:text-red-300 flex items-center gap-1 font-medium pt-1"
                >
                  <Plus className="h-3.5 w-3.5" /> Add List Element
                </button>
              </div>
            )}

            {type === "set" && (
              <div className="space-y-2">
                {setMembers.map((m, idx) => (
                  <div key={idx} className="flex items-center gap-2">
                    <input
                      type="text"
                      value={m}
                      onChange={(e) => {
                        const updated = [...setMembers];
                        updated[idx] = e.target.value;
                        setSetMembers(updated);
                      }}
                      placeholder={`Member #${idx + 1}`}
                      className="flex-1 px-3.5 py-1.5 bg-neutral-950 border border-neutral-800 rounded-lg text-xs text-white placeholder-neutral-500 font-mono"
                    />
                    {setMembers.length > 1 && (
                      <button
                        type="button"
                        onClick={() => setSetMembers(setMembers.filter((_, i) => i !== idx))}
                        className="p-1.5 text-neutral-500 hover:text-red-400"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    )}
                  </div>
                ))}
                <button
                  type="button"
                  onClick={() => setSetMembers([...setMembers, ""])}
                  className="text-xs text-red-400 hover:text-red-300 flex items-center gap-1 font-medium pt-1"
                >
                  <Plus className="h-3.5 w-3.5" /> Add Set Member
                </button>
              </div>
            )}

            {type === "hash" && (
              <div className="space-y-2">
                {hashEntries.map((entry, idx) => (
                  <div key={idx} className="flex items-center gap-2">
                    <input
                      type="text"
                      value={entry.field}
                      onChange={(e) => {
                        const updated = [...hashEntries];
                        updated[idx].field = e.target.value;
                        setHashEntries(updated);
                      }}
                      placeholder="field"
                      className="w-1/3 px-3 py-1.5 bg-neutral-950 border border-neutral-800 rounded-lg text-xs text-white font-mono"
                    />
                    <input
                      type="text"
                      value={entry.value}
                      onChange={(e) => {
                        const updated = [...hashEntries];
                        updated[idx].value = e.target.value;
                        setHashEntries(updated);
                      }}
                      placeholder="value"
                      className="flex-1 px-3 py-1.5 bg-neutral-950 border border-neutral-800 rounded-lg text-xs text-white font-mono"
                    />
                    {hashEntries.length > 1 && (
                      <button
                        type="button"
                        onClick={() => setHashEntries(hashEntries.filter((_, i) => i !== idx))}
                        className="p-1.5 text-neutral-500 hover:text-red-400"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    )}
                  </div>
                ))}
                <button
                  type="button"
                  onClick={() => setHashEntries([...hashEntries, { field: "", value: "" }])}
                  className="text-xs text-red-400 hover:text-red-300 flex items-center gap-1 font-medium pt-1"
                >
                  <Plus className="h-3.5 w-3.5" /> Add Hash Field
                </button>
              </div>
            )}

            {type === "zset" && (
              <div className="space-y-2">
                {zsetEntries.map((entry, idx) => (
                  <div key={idx} className="flex items-center gap-2">
                    <input
                      type="text"
                      value={entry.member}
                      onChange={(e) => {
                        const updated = [...zsetEntries];
                        updated[idx].member = e.target.value;
                        setZsetEntries(updated);
                      }}
                      placeholder="member"
                      className="flex-1 px-3 py-1.5 bg-neutral-950 border border-neutral-800 rounded-lg text-xs text-white font-mono"
                    />
                    <input
                      type="number"
                      value={entry.score}
                      onChange={(e) => {
                        const updated = [...zsetEntries];
                        updated[idx].score = parseFloat(e.target.value) || 0;
                        setZsetEntries(updated);
                      }}
                      placeholder="score"
                      className="w-24 px-3 py-1.5 bg-neutral-950 border border-neutral-800 rounded-lg text-xs text-white font-mono"
                    />
                    {zsetEntries.length > 1 && (
                      <button
                        type="button"
                        onClick={() => setZsetEntries(zsetEntries.filter((_, i) => i !== idx))}
                        className="p-1.5 text-neutral-500 hover:text-red-400"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    )}
                  </div>
                ))}
                <button
                  type="button"
                  onClick={() => setZsetEntries([...zsetEntries, { member: "", score: 0 }])}
                  className="text-xs text-red-400 hover:text-red-300 flex items-center gap-1 font-medium pt-1"
                >
                  <Plus className="h-3.5 w-3.5" /> Add Ranked Member
                </button>
              </div>
            )}

            {type === "json" && (
              <textarea
                rows={5}
                value={jsonValue}
                onChange={(e) => setJsonValue(e.target.value)}
                placeholder="Enter valid JSON..."
                className="w-full px-3.5 py-2 bg-neutral-950 border border-neutral-800 rounded-lg text-xs text-white placeholder-neutral-500 focus:outline-none focus:border-red-500 transition-colors font-mono"
              />
            )}
          </div>

          {/* Modal Footer */}
          <div className="pt-4 border-t border-neutral-800 flex items-center justify-end gap-3">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 bg-neutral-800 hover:bg-neutral-700 text-xs font-semibold text-neutral-300 rounded-lg transition-colors cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="px-5 py-2 bg-red-600 hover:bg-red-500 text-xs font-semibold text-white rounded-lg shadow-md shadow-red-600/20 disabled:opacity-50 transition-colors cursor-pointer"
            >
              {loading ? "Creating Key..." : "Create Key"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
