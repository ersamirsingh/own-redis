"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  Bot,
  Database,
  Layers,
  Lock,
  Radio,
  Settings,
  Terminal,
} from "lucide-react";
import { useAuth } from "@/lib/auth";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Overview", icon: Activity },
  { href: "/data", label: "Data Console", icon: Database },
  { href: "/commands", label: "Command Console", icon: Terminal },
  { href: "/traces", label: "Distributed Traces", icon: Layers },
  { href: "/diagnostics", label: "AI Diagnostics", icon: Bot },
  { href: "/locks", label: "Distributed Locks", icon: Lock },
  { href: "/settings", label: "Settings & Team", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  const { user } = useAuth();

  return (
    <aside className="w-64 border-r border-neutral-800 bg-neutral-900/90 backdrop-blur flex flex-col shrink-0 h-screen sticky top-0">
      {/* Brand Header */}
      <div className="h-16 px-6 border-b border-neutral-800 flex items-center gap-3">
        <div className="h-9 w-9 rounded-lg bg-gradient-to-tr from-red-600 to-red-400 flex items-center justify-center shadow-lg shadow-red-500/20">
          <Database className="h-5 w-5 text-white" />
        </div>
        <div>
          <div className="flex items-center gap-1.5">
            <span className="font-bold text-white tracking-wide">PyRedis</span>
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-red-500/20 text-red-400 font-mono font-semibold">
              v0.1
            </span>
          </div>
          <p className="text-xs text-neutral-400">AI-Native In-Memory</p>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const isActive = pathname === item.href || pathname.startsWith(item.href + "/");

          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-sm font-medium transition-all ${
                isActive
                  ? "bg-red-600/15 text-red-400 border border-red-500/20"
                  : "text-neutral-400 hover:text-neutral-100 hover:bg-neutral-800/60"
              }`}
            >
              <Icon className={`h-4 w-4 ${isActive ? "text-red-400" : "text-neutral-400"}`} />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>

      {/* Engine Status Card */}
      <div className="p-4 border-t border-neutral-800">
        <div className="p-3 rounded-lg bg-neutral-950/80 border border-neutral-800/80 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs text-neutral-400 font-medium">Engine Mode</span>
            <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-400">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-ping" />
              Asyncio
            </span>
          </div>
          <div className="text-[11px] text-neutral-500 font-mono">
            RESP2 :6379 • REST :8000
          </div>
        </div>
      </div>
    </aside>
  );
}
