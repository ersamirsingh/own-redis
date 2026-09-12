"use client";

import React, { useState } from "react";
import {
  Bell,
  CheckCircle,
  ChevronDown,
  LogOut,
  Radio,
  Shield,
  User as UserIcon,
} from "lucide-react";
import { useAuth } from "@/lib/auth";
import { useTelemetrySocket } from "@/lib/websocket";
import { Role } from "@/lib/types";

function RoleBadge({ role }: { role?: Role }) {
  if (!role) return null;

  const styles: Record<Role, string> = {
    admin: "bg-purple-500/15 text-purple-400 border-purple-500/30",
    operator: "bg-blue-500/15 text-blue-400 border-blue-500/30",
    developer: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
    readonly: "bg-amber-500/15 text-amber-400 border-amber-500/30",
  };

  return (
    <span
      className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold uppercase tracking-wider border ${
        styles[role] || "bg-neutral-800 text-neutral-300"
      }`}
    >
      <Shield className="h-3 w-3" />
      {role}
    </span>
  );
}

export function Header() {
  const { user, logout } = useAuth();
  const { connected } = useTelemetrySocket();
  const [showProfileMenu, setShowProfileMenu] = useState(false);
  const [showNotifications, setShowNotifications] = useState(false);

  return (
    <header className="h-16 border-b border-neutral-800 bg-neutral-900/60 backdrop-blur px-6 flex items-center justify-between sticky top-0 z-20">
      {/* Workspace Selector */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-neutral-800/80 border border-neutral-700/60 text-xs font-medium text-neutral-300 hover:bg-neutral-800 cursor-pointer transition-colors">
          <div className="h-2 w-2 rounded-full bg-red-500" />
          <span>production-main</span>
          <ChevronDown className="h-3 w-3 text-neutral-400" />
        </div>

        {/* Live Socket Status */}
        <div className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-neutral-950/60 border border-neutral-800 text-[11px] font-mono">
          <span
            className={`h-2 w-2 rounded-full ${
              connected ? "bg-emerald-500 animate-pulse" : "bg-amber-500"
            }`}
          />
          <span className={connected ? "text-emerald-400" : "text-amber-400"}>
            {connected ? "Live Telemetry" : "Connecting..."}
          </span>
        </div>
      </div>

      {/* Right Controls */}
      <div className="flex items-center gap-4">
        {/* User Role */}
        <RoleBadge role={user?.role} />

        {/* Notifications Bell */}
        <div className="relative">
          <button
            onClick={() => setShowNotifications(!showNotifications)}
            className="p-2 rounded-lg text-neutral-400 hover:text-neutral-200 hover:bg-neutral-800/60 relative transition-colors"
          >
            <Bell className="h-4 w-4" />
            <span className="absolute top-1.5 right-1.5 h-2 w-2 rounded-full bg-red-500 ring-2 ring-neutral-900" />
          </button>

          {showNotifications && (
            <div className="absolute right-0 mt-2 w-72 rounded-xl bg-neutral-900 border border-neutral-800 shadow-xl py-2 z-30 animate-in fade-in zoom-in-95 duration-100">
              <div className="px-4 py-2 border-b border-neutral-800 flex items-center justify-between">
                <span className="text-xs font-semibold text-neutral-200">Alerts & Events</span>
                <span className="text-[10px] text-neutral-500">Live</span>
              </div>
              <div className="px-4 py-3 text-xs text-neutral-400 space-y-2">
                <div className="flex items-start gap-2">
                  <CheckCircle className="h-3.5 w-3.5 text-emerald-400 shrink-0 mt-0.5" />
                  <div>
                    <p className="text-neutral-200 font-medium">Engine Boot Nominal</p>
                    <p className="text-[11px] text-neutral-500">AOF persistence and min-heap TTL running.</p>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* User Profile Menu */}
        <div className="relative">
          <button
            onClick={() => setShowProfileMenu(!showProfileMenu)}
            className="flex items-center gap-2 p-1.5 rounded-lg hover:bg-neutral-800/60 transition-colors"
          >
            <div className="h-7 w-7 rounded-full bg-gradient-to-br from-neutral-700 to-neutral-800 border border-neutral-600 flex items-center justify-center text-xs font-semibold text-neutral-200">
              {user?.name ? user.name[0].toUpperCase() : "U"}
            </div>
            <span className="text-xs font-medium text-neutral-300 hidden md:inline">
              {user?.name || user?.email || "User"}
            </span>
            <ChevronDown className="h-3 w-3 text-neutral-400" />
          </button>

          {showProfileMenu && (
            <div className="absolute right-0 mt-2 w-56 rounded-xl bg-neutral-900 border border-neutral-800 shadow-xl py-2 z-30 animate-in fade-in zoom-in-95 duration-100">
              <div className="px-4 py-2 border-b border-neutral-800">
                <p className="text-xs font-semibold text-neutral-200">{user?.name || "User"}</p>
                <p className="text-[11px] text-neutral-500 truncate">{user?.email}</p>
              </div>
              <div className="py-1">
                <button
                  onClick={logout}
                  className="w-full px-4 py-2 text-left text-xs text-red-400 hover:bg-neutral-800/80 flex items-center gap-2 transition-colors"
                >
                  <LogOut className="h-3.5 w-3.5" />
                  Sign Out
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
