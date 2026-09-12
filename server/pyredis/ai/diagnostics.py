"""Autonomous DBA Grounded Diagnostics Engine powered by Google Gemini."""

import json
import logging
import time
from typing import Any, Dict, List, Optional
from pyredis.ai.provider import gemini_provider
from pyredis.core.config import settings
from pyredis.metrics import metrics_collector
from pyredis.storage.store import DataStore

logger = logging.getLogger("pyredis.ai.diagnostics")


class DiagnosticsEngine:
    """Collects actual runtime engine telemetry and produces grounded DBA recommendations."""

    def __init__(self) -> None:
        self._action_proposals: Dict[str, Dict[str, Any]] = {}

    def collect_telemetry_context(
        self,
        store: Optional[DataStore] = None,
        evict_mgr: Optional[Any] = None,
        exp_mgr: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Compile a sanitized, compact operational telemetry payload."""
        summary = metrics_collector.get_summary()

        mem_bytes = store.memory_usage() if store else 0
        total_keys = store.dbsize() if store else 0
        max_mem = evict_mgr.max_memory if evict_mgr else settings.MAX_MEMORY_BYTES
        mem_pct = round((mem_bytes / max_mem * 100.0), 2) if max_mem > 0 else 0.0

        types_count: Dict[str, int] = {}
        if store:
            for k in store.keys():
                t = store.get_type(k)
                if t:
                    types_count[t.value] = types_count.get(t.value, 0) + 1

        ttl_stats = exp_mgr.get_metrics() if exp_mgr else {}
        temp_stats = evict_mgr.get_temperature_stats() if evict_mgr else {}
        slow_queries = metrics_collector.get_slow_log(limit=5)

        context: Dict[str, Any] = {
            "timestamp": time.time(),
            "memory": {
                "used_bytes": mem_bytes,
                "max_bytes": max_mem,
                "usage_percentage": mem_pct,
            },
            "keys": {
                "total_count": total_keys,
                "types_breakdown": types_count,
            },
            "eviction": {
                "policy": evict_mgr.policy.value if evict_mgr else settings.EVICTION_POLICY.value,
                "evictions_total": evict_mgr.evictions_total if evict_mgr else 0,
                "temperature": temp_stats,
            },
            "ttl": ttl_stats,
            "performance": {
                "ops_per_second": summary.get("ops_per_second", 0.0),
                "total_commands": summary.get("total_commands", 0),
                "cache_hit_ratio": summary.get("cache_hit_ratio", 1.0),
                "latency_p50_ms": summary.get("latency_p50_ms", 0.0),
                "latency_p99_ms": summary.get("latency_p99_ms", 0.0),
                "slow_queries_count": len(slow_queries),
            },
        }
        return context

    async def run_diagnostics(
        self,
        store: Optional[DataStore] = None,
        evict_mgr: Optional[Any] = None,
        exp_mgr: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Generate structured diagnostics findings grounded on live system metrics."""
        telemetry = self.collect_telemetry_context(store, evict_mgr, exp_mgr)

        # Default heuristic baseline
        health_score = 100
        status = "HEALTHY"
        findings: List[Dict[str, Any]] = []
        recommendations: List[str] = []
        proposed_actions: List[Dict[str, Any]] = []

        mem_pct = telemetry["memory"]["usage_percentage"]
        if mem_pct > 85.0:
            health_score -= 30
            status = "CRITICAL"
            findings.append({
                "severity": "critical",
                "title": "High Memory Pressure",
                "detail": f"Engine memory utilization is at {mem_pct}%. Approaching max memory threshold.",
            })
            recommendations.append("Switch to 'allkeys-lru' or 'adaptive' eviction to reclaim cold memory.")
            act_id = f"act_evict_{int(time.time())}"
            proposed_actions.append({
                "id": act_id,
                "description": "Switch eviction policy to adaptive",
                "command": "CONFIG SET maxmemory-policy adaptive",
                "impact": "low",
            })
            self._action_proposals[act_id] = proposed_actions[-1]

        elif mem_pct > 65.0:
            health_score -= 15
            status = "WARNING"
            findings.append({
                "severity": "warning",
                "title": "Elevated Memory Consumption",
                "detail": f"Memory utilization is at {mem_pct}%.",
            })
            recommendations.append("Audit large keys and apply TTL expiration to transient datasets.")

        slow_count = telemetry["performance"]["slow_queries_count"]
        if slow_count > 0:
            health_score -= 10
            findings.append({
                "severity": "warning",
                "title": "Slow Commands Detected",
                "detail": f"{slow_count} slow queries recorded in the slowlog buffer exceeding latency threshold.",
            })
            recommendations.append("Review slow query log for high-complexity operations (e.g. KEYS * or large LRANGE).")

        hit_ratio = telemetry["performance"]["cache_hit_ratio"]
        if hit_ratio < 0.70 and telemetry["performance"]["total_commands"] > 20:
            health_score -= 10
            findings.append({
                "severity": "info",
                "title": "Low Cache Hit Ratio",
                "detail": f"Cache hit ratio is currently {round(hit_ratio * 100, 1)}%.",
            })
            recommendations.append("Consider lengthening TTLs on frequently queried read paths.")

        if not findings:
            findings.append({
                "severity": "info",
                "title": "All Systems Nominal",
                "detail": "Memory, throughput, latency, and hit ratios are operating within optimal parameters.",
            })
            recommendations.append("System is healthy. Enable AOF persistence and regular snapshots for maximum durability.")

        # If Gemini is configured, enhance findings with LLM reasoning
        if gemini_provider.is_configured:
            prompt = (
                f"You are the PyRedis Autonomous Senior Database Administrator.\n"
                f"Analyze this operational telemetry JSON:\n"
                f"{json.dumps(telemetry, indent=2)}\n\n"
                f"Provide an insightful analysis with health score, status, findings, and recommendations."
            )
            llm_summary = await gemini_provider.generate_text(
                prompt=prompt,
                system_instruction="You are an expert in-memory database systems engineer. Be concise, diagnostic, and precise.",
            )
        else:
            llm_summary = (
                f"PyRedis autonomous DBA evaluated {telemetry['keys']['total_count']} keys "
                f"across {telemetry['memory']['used_bytes']} bytes. System health score is {health_score}/100 ({status})."
            )

        return {
            "health_score": max(0, min(100, health_score)),
            "status": status,
            "summary": llm_summary,
            "findings": findings,
            "recommendations": recommendations,
            "proposed_actions": proposed_actions,
            "telemetry_context": telemetry,
            "generated_at": time.time(),
        }

    def get_proposed_action(self, action_id: str) -> Optional[Dict[str, Any]]:
        return self._action_proposals.get(action_id)


# Global DiagnosticsEngine singleton
diagnostics_engine = DiagnosticsEngine()
