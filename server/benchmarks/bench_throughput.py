"""In-memory throughput benchmark for PyRedis storage and command pipeline."""

import asyncio
import time
import pyredis.commands  # Registers all command handlers
from pyredis.commands.registry import registry, CommandContext
from pyredis.storage.store import DataStore
from pyredis.storage.object import create_string


async def run_benchmark(num_ops: int = 50_000) -> None:
    store = DataStore()
    context = CommandContext(store=store)

    print("=== PyRedis In-Memory Throughput Benchmark ===")
    print(f"Total Operations: {num_ops:,} direct SET/GET and 10,000 pipelined command executions\n")

    # Benchmark direct storage SET
    start = time.perf_counter()
    for i in range(num_ops):
        store.set(f"bench_key_{i}", create_string(f"bench_value_{i}"))
    elapsed_set = time.perf_counter() - start
    set_ops_sec = num_ops / elapsed_set
    print(f"[Direct Storage] SET: {num_ops:,} ops in {elapsed_set:.3f}s -> {set_ops_sec:,.0f} ops/sec")

    # Benchmark direct storage GET
    start = time.perf_counter()
    for i in range(num_ops):
        _ = store.get(f"bench_key_{i}")
    elapsed_get = time.perf_counter() - start
    get_ops_sec = num_ops / elapsed_get
    print(f"[Direct Storage] GET: {num_ops:,} ops in {elapsed_get:.3f}s -> {get_ops_sec:,.0f} ops/sec")

    # Benchmark Command Registry Pipeline execution
    pipe_ops = min(num_ops, 10_000)
    start = time.perf_counter()
    for i in range(pipe_ops):
        registry.execute("SET", [f"pipe_key_{i}", f"pipe_val_{i}"], context)
    elapsed_pipe = time.perf_counter() - start
    pipe_ops_sec = pipe_ops / elapsed_pipe
    print(f"[Command Pipeline] SET: {pipe_ops:,} ops in {elapsed_pipe:.3f}s -> {pipe_ops_sec:,.0f} ops/sec")

    start = time.perf_counter()
    for i in range(pipe_ops):
        _ = registry.execute("GET", [f"pipe_key_{i}"], context)
    elapsed_pipe_get = time.perf_counter() - start
    pipe_get_ops_sec = pipe_ops / elapsed_pipe_get
    print(f"[Command Pipeline] GET: {pipe_ops:,} ops in {elapsed_pipe_get:.3f}s -> {pipe_get_ops_sec:,.0f} ops/sec")

    print("\n===============================================")


if __name__ == "__main__":
    asyncio.run(run_benchmark())
