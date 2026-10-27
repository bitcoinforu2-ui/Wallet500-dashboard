#!/usr/bin/env python3
"""Copy only the explicit dashboard projection from the private engine."""
import json, os, time, urllib.request
from datetime import datetime, timezone
from pathlib import Path
token = os.environ.get("SOURCE_TOKEN", "")
if not token:
    print("::warning::DASHBOARD_SOURCE_TOKEN is missing; retained snapshot will expire normally.")
    raise SystemExit(0)
url = "https://api.github.com/repos/bitcoinforu2-ui/Wallet500-v2/contents/data/v2-runtime-status.json?ref=main"
request = urllib.request.Request(url, headers={"Authorization": "Bearer " + token, "Accept": "application/vnd.github.raw+json", "Cache-Control": "no-cache", "X-GitHub-Api-Version": "2022-11-28"})
def fetch_source():
    with urllib.request.urlopen(request, timeout=30) as response:
        raw = response.read(2_000_001)
    if len(raw) > 2_000_000:
        raise ValueError("Projection exceeds size limit")
    source = json.loads(raw)
    if not isinstance(source, dict) or not isinstance(source.get("decisions"), list):
        raise ValueError("Invalid projection")
    return source

def source_age(source):
    try:
        stamp = datetime.fromisoformat(str(source.get("generated_at")).replace("Z", "+00:00"))
        age = (datetime.now(timezone.utc) - stamp).total_seconds()
        return age if age >= -120 else float("inf")
    except (ValueError, TypeError):
        return float("inf")

def wait_for_projection(fetch, *, budget=900, clock=time.monotonic, pause=time.sleep):
    started = clock()
    source = fetch()
    # A source older than six hours cannot plausibly be caught up by waiting
    # for one currently overlapping engine run. Publish the unchanged, stale
    # timestamps immediately so the dashboard shows the outage truthfully.
    # Never manufacture a new market/decision timestamp here.
    if source_age(source) > 6 * 3600:
        print("::warning::DASHBOARD_UPSTREAM_SCAN_OVER_6H_STALE; skip the 15-minute wait.")
        return source
    # For a recent overlapping scan, give the producer time to publish.
    while source_age(source) > 900 and clock() - started < budget:
        pause(min(20, max(0, budget - (clock() - started))))
        source = fetch()
    return source

# Do not spend 15 minutes blocking the Pages queue when private Actions are
# down. Dashboards must publish the historical snapshot with its original
# timestamps and explicit stale banner instead of waiting for a dead runner.
source = wait_for_projection(fetch_source, budget=60)
if source_age(source) > 1500:
    print("::warning::Engine projection is stale; original timestamps are preserved.")
keys = ("generated_at", "market_observed_at", "status", "scan_outcome", "delivery_status", "delivery_confirmed", "pre_buy_count", "buy_zone_count", "evaluated_targets", "observable_coverage_pct", "error_count", "run_url", "scan_completed_at", "decisions_at", "data_quality", "observable_targets", "market_targets_attempted", "market_targets_deferred", "pre_buy_delivered", "risk_alerts_delivered", "decisions_total", "market_data_target_count", "market_data_observed_count", "market_data_coverage_pct", "market_data_observed_at", "market_data_deferred_count", "market_data_unavailable_count", "market_data_request_count", "market_data_semantics", "deep_coverage_pct", "deep_observable_targets")
if not isinstance(source, dict) or not isinstance(source.get("decisions"), list):
    raise ValueError("Invalid projection")
result = {key: source.get(key) for key in keys}
# This diagnostic is derived from the original timestamp, never from the
# dashboard deployment time. The browser must continue treating stale decisions
# as historical research only; it is not an alternative signal engine.
age_seconds = source_age(source)
result["source_freshness"] = {
    "source_age_minutes_at_sync": round(age_seconds / 60, 1) if age_seconds != float("inf") else None,
    "source_is_stale_at_sync": age_seconds > 1500,
    "source_generated_at": source.get("generated_at"),
    "last_successful_scan_at": source.get("scan_completed_at"),
    "semantics": "HISTORICAL_ONLY_WHEN_STALE_NO_BUY_OR_TG_ACTION",
}
followup = source.get("discovery_followup")
followup_keys = ("registered", "interval_seconds", "late_after_seconds", "basic_overdue_1h", "basic_overdue_2h", "full_verification_due", "semantics")
result["discovery_followup"] = {key: followup.get(key) for key in followup_keys} if isinstance(followup, dict) else {}
result["decisions"] = [{key: row.get(key) for key in ("symbol", "identity_key", "state", "pre_buy", "reasons", "observed_at", "observable", "market", "market_observation")} for row in source["decisions"][:100] if isinstance(row, dict)]
result["discovery_movers"] = [{key: row.get(key) for key in ("symbol", "price_usd", "change_24h_pct", "volume_24h_usd", "observed_at", "url", "state")} for row in (source.get("discovery_movers") or [])[:30] if isinstance(row, dict)]
target = Path("data/v2-runtime-status.json")
target.parent.mkdir(exist_ok=True)
target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
print("Updated public runtime projection.")
