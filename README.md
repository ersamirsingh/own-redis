# PyRedis — AI-Native In-Memory Data Platform

PyRedis is a production-oriented in-memory data platform built from scratch in Python (asyncio + FastAPI) and Next.js / TypeScript.

## Architecture

* **Backend Engine (`pyredis/`)**:
  - Pure Python RESP2 protocol parser & encoder (zero external Redis dependency).
  - High-concurrency `asyncio` TCP server (default port 6379).
  - In-memory data structures: String, List, Set, Hash, Sorted Set (SkipList), JSON documents.
  - TTL min-heap engine with active & lazy expiration.
  - Persistence: Append-Only File (AOF) with configurable fsync policies (`always`, `everysec`, `no`) + Snapshotting (RDB).
  - Adaptive memory eviction policies (LRU, LFU, and custom Adaptive scoring).
  - Distributed locking, Token Bucket rate limiting, and pub/sub channels.
  - Multi-role Authentication & RBAC (Admin, Operator, Developer, ReadOnly) via Argon2id and JWT.
  - Distributed tracing with waterfall spans and latency percentiles.
  - Google Gemini AI integration: Semantic memory, vector embeddings, and grounded autonomous DBA diagnostics.

* **Frontend Dashboard (`dashboard/`)**:
  - Next.js 15 App Router + TypeScript + Tailwind CSS.
  - Operational Data Console with type-aware editors (String, List, Set, Hash, Sorted Set, JSON).
  - Monaco-based in-browser Command Console with history and autocomplete.
  - Real-time telemetry dashboards over WebSockets (Memory, Latency, Hit Ratio, Commands).
  - Trace Explorer waterfall view.
  - AI Diagnostics, natural language query assistant, and settings management.

## Quick Start

### 1. Backend Setup
```bash
cd pyredis
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Unix:
# source .venv/bin/activate

pip install -e .
python -m pyredis.main
```

### 2. Frontend Setup
```bash
cd dashboard
npm install
npm run dev
```

Visit `http://localhost:3000` to access the PyRedis platform.
