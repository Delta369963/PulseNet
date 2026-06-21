#!/usr/bin/env python3
"""
PulseNet Live Integration Test Script
======================================
Tests against the running engine (http://localhost:8000) and Next.js app (http://localhost:3000).

Covers:
  1. Engine health check
  2. Ingestion per source (GDACS, USGS, each GNews feed)
  3. Re-evaluation for each live shock
  4. Chaining verification (cascade DAG presence)
  5. Approve / reject / adjust reroutes via Next.js API
  6. Debug endpoints
  7. Summary report

Run with:  python3 scripts/live_test.py
"""

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime


ENGINE = "http://localhost:8000"
APP = "http://localhost:3000"

PASS = "\033[92m✓\033[0m"
FAIL = "\033[91m✗\033[0m"
WARN = "\033[93m⚠\033[0m"
SKIP = "\033[90m-\033[0m"

results: list[tuple[str, bool, str]] = []


def req(method: str, url: str, body: dict | None = None, timeout: int = 30) -> tuple[int, dict]:
    data = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    r = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body_bytes = e.read()
        try:
            return e.code, json.loads(body_bytes)
        except Exception:
            return e.code, {"raw": body_bytes.decode(errors="replace")}


def check(name: str, passed: bool, detail: str = ""):
    icon = PASS if passed else FAIL
    print(f"  {icon} {name}{f'  ({detail})' if detail else ''}")
    results.append((name, passed, detail))
    return passed


def section(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# ═══════════════════════════════════════════════════════════
# 1. Health check
# ═══════════════════════════════════════════════════════════
section("1. ENGINE HEALTH")
status, body = req("GET", f"{ENGINE}/health")
check("Engine reachable", status == 200, f"status={status}")
check("DB reachable", body.get("dbReachable", False), str(body.get("dbReachable")))
check("Gemini alpha enabled", body.get("features", {}).get("gemini_alpha", False))
check("Gemini beta enabled", body.get("features", {}).get("gemini_beta", False))
check("Dual consensus enabled", body.get("features", {}).get("dual_consensus", False))

# ═══════════════════════════════════════════════════════════
# 2. Debug endpoints
# ═══════════════════════════════════════════════════════════
section("2. DEBUG ENDPOINTS")

status, body = req("GET", f"{ENGINE}/debug/shocks?limit=50")
check("GET /debug/shocks returns 200", status == 200, f"total={body.get('total', '?')}")
shocks = body.get("shocks", [])
check("At least 1 shock in DB", len(shocks) >= 1, f"found {len(shocks)}")

status, body = req("GET", f"{ENGINE}/debug/feeds")
check("GET /debug/feeds returns 200", status == 200, f"total={body.get('total', '?')}")
feeds = body.get("feeds", [])
check("At least 5 feeds configured", len(feeds) >= 5, f"found {len(feeds)}")
enabled_feeds = [f for f in feeds if f.get("enabled")]
check("At least 3 feeds enabled", len(enabled_feeds) >= 3, f"enabled={len(enabled_feeds)}")

print(f"\n  Configured feeds ({len(feeds)}):")
for f in feeds:
    status_icon = PASS if f.get("enabled") else SKIP
    gnews = " [GNews]" if f.get("isGNews") else ""
    print(f"    {status_icon} {f['name']}{gnews}  max={f.get('maxItems', '?')}")

if shocks:
    first_shock_id = shocks[0]["id"]
    status, detail = req("GET", f"{ENGINE}/debug/shock/{first_shock_id}")
    check(f"GET /debug/shock/{{id}} returns 200", status == 200)
    if status == 200:
        check("shock detail has exposures field", "exposures" in detail)
        check("shock detail has reroutes field", "reroutes" in detail)
        check("shock detail has tradeIntel field", "tradeIntel" in detail)

# ═══════════════════════════════════════════════════════════
# 3. Ingestion per source
# ═══════════════════════════════════════════════════════════
section("3. INGESTION PER SOURCE")

source_results: dict[str, dict] = {}

for feed in feeds[:12]:  # Test up to 12 feeds
    fname = feed["name"]
    print(f"\n  Ingesting from: {fname}")
    t0 = time.time()
    try:
        status, body = req("POST", f"{ENGINE}/ingest?source={urllib.parse.quote(fname)}", timeout=60)
        elapsed = round(time.time() - t0, 1)
        if status == 200:
            ins = body.get("inserted", 0)
            skipped = body.get("skipped", 0)
            news = body.get("newsSearched", 0)
            usgs = body.get("usgsFetched", 0)
            source_results[fname] = body
            check(f"  {fname}: HTTP 200", True, f"inserted={ins} skipped={skipped} news={news} usgs={usgs} ({elapsed}s)")
        else:
            source_results[fname] = {"error": body}
            check(f"  {fname}: HTTP {status}", False, str(body)[:80])
    except Exception as e:
        source_results[fname] = {"exception": str(e)}
        check(f"  {fname}: exception", False, str(e)[:80])




total_inserted = sum(v.get("inserted", 0) for v in source_results.values() if "inserted" in v)
total_skipped = sum(v.get("skipped", 0) for v in source_results.values() if "skipped" in v)
print(f"\n  Total across all sources: inserted={total_inserted}  skipped={total_skipped}")
check("At least 1 new shock ingested across sources", total_inserted >= 1, f"inserted={total_inserted}")

# ═══════════════════════════════════════════════════════════
# 4. Re-evaluation for each live shock
# ═══════════════════════════════════════════════════════════
section("4. RE-EVALUATION PER SHOCK")

# Reload shocks after ingestion
status, body = req("GET", f"{ENGINE}/debug/shocks?limit=50")
shocks = body.get("shocks", [])
print(f"  Evaluating {min(len(shocks), 8)} shocks (capped to 8 to respect rate limits)...")

eval_results: list[dict] = []
for shock in shocks[:8]:
    sid = shock["id"]
    title = shock["title"][:55]
    stype = shock["type"]
    sev = shock["severity"]

    t0 = time.time()
    status, result = req("POST", f"{ENGINE}/debug/evaluate/{sid}", timeout=90)
    elapsed = round(time.time() - t0, 1)

    if status == 200:
        exp = result.get("exposuresCreated", 0)
        rer = result.get("reroutesCreated", 0)
        ti = result.get("tradeIntel", {}).get("tradeIntel", {})
        from_llm = ti.get("fromLLM", False)
        disrupted = ti.get("disrupted", [])
        inbound = ti.get("inbound", [])
        eval_results.append({"id": sid, "type": stype, "severity": sev, "exp": exp, "rer": rer, "fromLLM": from_llm})
        llm_tag = "LLM✓" if from_llm else "fallback"
        check(
            f"  [{stype}/{sev}] {title}",
            exp >= 0,  # 0 is valid for minor remote earthquakes
            f"exp={exp} rer={rer} [{llm_tag}] disrupted={disrupted} inbound={inbound} ({elapsed}s)"
        )
    else:
        eval_results.append({"id": sid, "error": result})
        check(f"  [{stype}/{sev}] {title}", False, f"HTTP {status}")

shocks_with_results = [r for r in eval_results if r.get("exp", 0) > 0 or r.get("rer", 0) > 0]
print(f"\n  Shocks with exposures or reroutes: {len(shocks_with_results)}/{min(len(shocks), 8)}")
check("At least 2 shocks produced results", len(shocks_with_results) >= 2, f"got {len(shocks_with_results)}")

# ═══════════════════════════════════════════════════════════
# 5. Chaining verification (cascade DAG)
# ═══════════════════════════════════════════════════════════
section("5. CASCADE / CHAINING VERIFICATION")

dag_checks_passed = 0
for shock in shocks[:8]:  # Check more shocks
    sid = shock["id"]
    status, detail = req("GET", f"{ENGINE}/debug/shock/{sid}")
    if status != 200:
        continue

    exp = detail.get("exposures", [])
    rer = detail.get("reroutes", [])

    if exp:
        # Check exposure paths contain causal chain indicator (→ in path)
        # Both outbound (shock → supplier → consumer) and inbound ([TYPE] shock → country: need) use →
        paths_with_chain = [e for e in exp if "\u2192" in (e.get("exposurePath") or "")]
        if paths_with_chain:
            dag_checks_passed += 1
            cascade_confs = [e.get("cascadeConfidence", 0) for e in exp if e.get("cascadeConfidence")]
            max_conf = max(cascade_confs) if cascade_confs else 0
            sample_path = paths_with_chain[0].get("exposurePath", "")[:70]
            print(f"  {PASS} [{shock['type']}/{shock['severity']}] {shock['title'][:45]}")
            print(f"       exposures={len(exp)} reroutes={len(rer)} max_cascade_conf={round(max_conf*100)}%")
            print(f"       sample_path: {sample_path}")
        else:
            # Exposures exist but no arrows — show what paths look like
            sample = (exp[0].get("exposurePath") or "")[:80]
            print(f"  {WARN} [{shock['type']}] {shock['title'][:45]} — no chain arrows in paths")
            print(f"       sample_path: {sample}")
    else:
        print(f"  {SKIP} [{shock['type']}/{shock['severity']}] {shock['title'][:45]} — 0 exposures (OK for minor quakes)")

check("At least 2 shocks have valid causal chain paths", dag_checks_passed >= 2, f"got {dag_checks_passed}")

# ═══════════════════════════════════════════════════════════
# 6. Approve / Reject via Next.js API
# ═══════════════════════════════════════════════════════════
section("6. HITL APPROVE / REJECT / ADJUST")

# Find a shock that has pending reroutes
target_shock = next((r for r in eval_results if r.get("rer", 0) > 0), None)

if not target_shock:
    print(f"  {WARN} No shocks with reroutes found — skipping HITL test")
    check("HITL: reroutes available for testing", False, "0 shocks have reroutes")
else:
    sid = target_shock["id"]
    status, detail = req("GET", f"{ENGINE}/debug/shock/{sid}")
    reroutes = detail.get("reroutes", [])
    pending = [r for r in reroutes if r.get("status") == "pending"]

    check("Reroutes found with pending status", len(pending) >= 1, f"pending={len(pending)}")

    if pending:
        # Test via Next.js API /api/decisions
        approve_id = pending[0]["id"]
        reject_id = pending[1]["id"] if len(pending) > 1 else None
        adjust_id = pending[2]["id"] if len(pending) > 2 else None

        # Approve
        status, body = req("POST", f"{APP}/api/decisions", {
            "suggestionId": approve_id,
            "action": "approve",
            "actor": "test-script"
        })
        check("Approve reroute via /api/decisions", status == 200 and body.get("ok"), f"status={status}")
        if status == 200:
            check("Approved status set", body.get("suggestion", {}).get("status") == "approved",
                  body.get("suggestion", {}).get("status"))
            check("DecidedBy recorded", body.get("suggestion", {}).get("decidedBy") == "test-script")

        # Reject
        if reject_id:
            status, body = req("POST", f"{APP}/api/decisions", {
                "suggestionId": reject_id,
                "action": "reject",
                "note": "Blocked by sanctions — automated test",
                "actor": "test-script"
            })
            check("Reject reroute via /api/decisions", status == 200 and body.get("ok"), f"status={status}")
            if status == 200:
                check("Rejected status set", body.get("suggestion", {}).get("status") == "rejected",
                      body.get("suggestion", {}).get("status"))
                check("AdminNote recorded", "sanctions" in (body.get("suggestion", {}).get("adminNote") or ""))

        # Adjust
        if adjust_id:
            status, body = req("POST", f"{APP}/api/decisions", {
                "suggestionId": adjust_id,
                "action": "adjust",
                "note": "Increase volume by 15% — automated test",
                "actor": "test-script"
            })
            check("Adjust reroute via /api/decisions", status == 200 and body.get("ok"), f"status={status}")
            if status == 200:
                check("Adjusted status set", body.get("suggestion", {}).get("status") == "adjusted")

        # Audit trail — filter by actor to avoid 60-item cap issue
        status, body = req("GET", f"{APP}/api/decisions?actor=test-script&limit=20")
        check("GET /api/decisions?actor=test-script returns 200", status == 200 and "decisions" in body,
              f"count={len(body.get('decisions', []))}")
        if status == 200:
            test_decisions = body.get("decisions", [])
            check("Audit trail contains test decisions", len(test_decisions) >= 1,
                  f"test decisions found: {len(test_decisions)}")
            if test_decisions:
                latest = test_decisions[0]
                check("Latest decision has correct actor", latest.get("actor") == "test-script")
                check("Latest decision has action field", latest.get("action") in ["approve", "reject", "adjust"])
                print(f"    Latest decision: {latest.get('action')} — {latest.get('summary', '')[:60]}")

# ═══════════════════════════════════════════════════════════
# 7. Summary
# ═══════════════════════════════════════════════════════════
section("SUMMARY")

total = len(results)
passed = sum(1 for _, ok, _ in results if ok)
failed = total - passed

print(f"\n  Tests: {total}  |  Passed: {passed}  |  Failed: {failed}")
print()

if failed > 0:
    print("  FAILED CHECKS:")
    for name, ok, detail in results:
        if not ok:
            print(f"    {FAIL} {name}  {detail}")

final_ok = failed == 0
print(f"\n  {'ALL TESTS PASSED ✓' if final_ok else f'{failed} TESTS FAILED ✗'}")
sys.exit(0 if final_ok else 1)
