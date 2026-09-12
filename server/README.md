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
# or
python scripts/run_server.py
```

## Project Structure
```
server/
├── pyredis/          # Core package
│   ├── api/          # FastAPI REST & WebSocket endpoints
│   ├── auth/         # Argon2id, JWT, RBAC, User repository
│   ├── commands/     # Command implementations & registry
│   ├── core/         # Config, types, exceptions
│   ├── events/       # Internal asynchronous event bus
│   ├── eviction/     # LRU, LFU, Random, FIFO eviction
│   ├── expiration/   # Min-heap TTL scheduler
│   ├── metrics/      # Telemetry, histograms, percentiles
│   ├── persistence/  # AOF engine and RDB snapshotting
│   ├── protocol/     # RESP2 streaming parser and encoder
│   ├── server/       # Asyncio TCP protocol server
│   ├── storage/      # DataStore, SkipList, Object wrappers
│   ├── tracing/      # Distributed tracer & span models
│   └── main.py       # Application bootstrap
├── tests/            # Pytest test suite
├── scripts/          # Utility scripts (run_server.py)
├── benchmarks/       # Performance benchmarks
├── requirements.txt  # Production dependencies
├── pyproject.toml    # Packaging metadata
└── Dockerfile
```
