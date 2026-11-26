import sys
from pathlib import Path

# Ensure backend root is on sys.path
backend_dir = Path(__file__).resolve().parent.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

import time
import statistics
import concurrent.futures
from typing import List, Dict, Any
from fastapi.testclient import TestClient

from app.main import app

ENDPOINTS = [
    ("/api/v1/discovery/home?city_slug=hyderabad", "GET"),
    ("/api/v1/discovery/search?q=hyderabad&category=ALL", "GET"),
    ("/api/v1/locations/cities", "GET"),
    ("/api/v1/locations/localities?city_slug=hyderabad", "GET"),
    ("/health/ready", "GET"),
]

TOTAL_REQUESTS = 200
CONCURRENCY = 20


def execute_request(client: TestClient, endpoint: str) -> Dict[str, Any]:
    t0 = time.perf_counter()
    resp = client.get(endpoint, headers={"X-Correlation-ID": f"loadtest-{time.time()}"})
    duration_ms = (time.perf_counter() - t0) * 1000
    return {
        "status_code": resp.status_code,
        "duration_ms": duration_ms,
        "endpoint": endpoint
    }


def main():
    print(f"\n================================================================================")
    print(f"🚀 GO BEYOND - Performance & Realistic Concurrent Load Test")
    print(f"Target: In-Process FastAPI + PostgreSQL 16 + Redis 7")
    print(f"Concurrency: {CONCURRENCY} parallel virtual users | Total Requests: {TOTAL_REQUESTS}")
    print(f"================================================================================\n")

    client = TestClient(app)
    results: List[Dict[str, Any]] = []

    start_wall_clock = time.perf_counter()

    with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENCY) as executor:
        futures = []
        for i in range(TOTAL_REQUESTS):
            endpoint, _ = ENDPOINTS[i % len(ENDPOINTS)]
            futures.append(executor.submit(execute_request, client, endpoint))

        for f in concurrent.futures.as_completed(futures):
            results.append(f.result())

    total_time = time.perf_counter() - start_wall_clock
    rps = len(results) / total_time if total_time > 0 else 0

    latencies = [r["duration_ms"] for r in results]
    latencies.sort()

    status_counts = {}
    for r in results:
        status_counts[r["status_code"]] = status_counts.get(r["status_code"], 0) + 1

    p50 = statistics.median(latencies)
    p95 = latencies[int(len(latencies) * 0.95)]
    p99 = latencies[int(len(latencies) * 0.99)]
    avg = statistics.mean(latencies)
    min_lat = min(latencies)
    max_lat = max(latencies)

    print("📊 Load Test Performance Results:")
    print(f"  • Total Requests Completed: {len(results)}")
    print(f"  • Total Time Elapsed:       {total_time:.2f} seconds")
    print(f"  • Throughput:               {rps:.1f} req/sec")
    print(f"  • Min Latency:              {min_lat:.2f} ms")
    print(f"  • Mean Latency:             {avg:.2f} ms")
    print(f"  • Median (p50) Latency:     {p50:.2f} ms")
    print(f"  • 95th Percentile (p95):    {p95:.2f} ms")
    print(f"  • 99th Percentile (p99):    {p99:.2f} ms")
    print(f"  • Max Latency:              {max_lat:.2f} ms\n")

    print("📈 HTTP Status Code Breakdown:")
    for code, count in sorted(status_counts.items()):
        pct = (count / len(results)) * 100
        print(f"  • HTTP {code}: {count} ({pct:.1f}%)")

    # Assertions
    errors_5xx = sum(count for code, count in status_counts.items() if code >= 500)
    print(f"\n✅ Server 5xx Errors: {errors_5xx}")

    if errors_5xx > 0:
        print("❌ FAILED: Load test encountered internal server errors (5xx)!")
        sys.exit(1)
    else:
        print("🎉 SUCCESS: Platform sustained concurrent load with 0 internal server errors!\n")


if __name__ == "__main__":
    main()

