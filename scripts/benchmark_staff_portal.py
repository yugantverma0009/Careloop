"""
CareLoop Staff Portal Performance & Latency Benchmark Script
Measures response latency and payload size across key Staff Portal endpoints.
"""
import time
import json
import statistics
import urllib.request
import urllib.error

BASE_URL = "http://127.0.0.1:8000"

def login(email="ananya.demo@example.test", password="Demo@12345"):
    data = json.dumps({"email": email, "password": password}).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE_URL}/auth/login",
        data=data,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        return res["access_token"]

def measure_endpoint(token, path, runs=5):
    latencies = []
    payload_size = 0
    status_code = 0
    for _ in range(runs):
        req = urllib.request.Request(
            f"{BASE_URL}{path}",
            headers={"Authorization": f"Bearer {token}"}
        )
        t0 = time.perf_counter()
        with urllib.request.urlopen(req) as resp:
            status_code = resp.status
            content = resp.read()
            dt = (time.perf_counter() - t0) * 1000.0  # ms
            latencies.append(dt)
            payload_size = len(content)
        time.sleep(0.05)
    return {
        "path": path,
        "status": status_code,
        "mean_ms": round(statistics.mean(latencies), 2),
        "median_ms": round(statistics.median(latencies), 2),
        "min_ms": round(min(latencies), 2),
        "max_ms": round(max(latencies), 2),
        "payload_bytes": payload_size
    }

def main():
    print("CareLoop Staff Portal Performance Benchmark")
    print("=" * 60)
    token = login()
    print("✓ Authenticated as Dr. Ananya Sharma")
    
    endpoints = [
        "/staff/worklist",
        "/staff/patients",
        "/staff/patients/1",
        "/staff/patients/1/timeline?limit=100",
        "/staff/patients/1/medicines",
        "/staff/patients/1/rules",
        "/staff/tasks",
        "/staff/summaries",
        "/staff/handoff",
        "/staff/notifications",
        "/staff/insights?range=30d",
        "/staff/pathway-templates",
        "/staff/patients/1/fhir",
        "/staff/patients/1/lace"
    ]
    
    results = []
    print(f"{'Endpoint':<40} {'Status':<8} {'Median (ms)':<12} {'Payload':<10}")
    print("-" * 72)
    for ep in endpoints:
        try:
            r = measure_endpoint(token, ep)
            results.append(r)
            print(f"{r['path']:<40} {r['status']:<8} {r['median_ms']:<12.2f} {r['payload_bytes']:<10}")
        except Exception as e:
            print(f"{ep:<40} ERROR: {e}")

    with open("docs/performance_benchmark_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\nBenchmark results saved to docs/performance_benchmark_results.json")

if __name__ == "__main__":
    main()
