export type Role = "admin" | "operator" | "developer" | "readonly";

export interface User {
  id: string;
  email: string;
  name: string;
  role: Role;
  created_at: number;
}

export interface AuthResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: User;
}

export interface KeyItem {
  key: string;
  type: "string" | "list" | "set" | "hash" | "zset" | "json";
  memory_bytes: number;
  ttl_seconds: number | null;
  temperature: "HOT" | "WARM" | "COLD" | "UNKNOWN";
  access_count: number;
}

export interface TelemetryData {
  memory_used_bytes: number;
  total_keys: number;
  ops_per_second: number;
  total_commands: number;
  cache_hit_ratio: number;
  latency_p50_ms: number;
  latency_p90_ms: number;
  latency_p99_ms: number;
  temperature?: {
    hot: number;
    warm: number;
    cold: number;
    total: number;
  };
}

export interface NotificationItem {
  id: string;
  title: string;
  message: string;
  type: "info" | "warning" | "alert" | "success";
  timestamp: number;
  read?: boolean;
}

export interface KeyDetail extends KeyItem {
  value: any;
  created_at: number;
  last_accessed_at: number;
}

export interface KeyRevisionItem {
  version: number;
  timestamp: number;
  data_type: string;
  value_repr: string;
  size_bytes: number;
}

export interface CommandExecutionResult {
  command: string;
  result: any;
  duration_ms: number;
  timestamp: number;
  error?: string;
}

export interface SpanItem {
  name: string;
  start_time: number;
  duration_ms: number;
  metadata?: Record<string, any>;
}

export interface TraceItem {
  trace_id: string;
  command: string;
  client_id?: string | null;
  client_ip?: string | null;
  start_time: number;
  duration_ms: number;
  status: "OK" | "ERROR" | string;
  error_message?: string | null;
  sanitized_args: string[];
  spans: SpanItem[];
}

export interface DistributedLockItem {
  key: string;
  owner: string;
  acquired_at: number;
  expires_at: number;
  ttl_remaining_ms: number;
}
