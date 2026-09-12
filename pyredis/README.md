# PyRedis Backend Engine

High-performance, asyncio-powered in-memory data platform built from scratch in Python 3.12+.

## Features
- Full RESP2 protocol implementation.
- Custom storage engine for String, List, Set, Hash, Sorted Set (SkipList), JSON.
- Min-Heap TTL engine and Adaptive Eviction policy.
- AOF and Snapshot persistence.
- Argon2id + JWT authentication with RBAC (Admin, Operator, Developer, ReadOnly).
- Distributed tracing, real-time WebSocket telemetry, and Google Gemini AI integration.

## Installation
```bash
python -m venv .venv
# Activate virtualenv
pip install -e ".[dev]"
```

## Running
```bash
python -m pyredis.main
```
