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

# Do not re-commit or redeploy the dashboard merely because the wall-clock age
# changed. The browser calculates age from market_observed_at at display time.
# A repeated/older source must never replace the last verified newer projection.
def trusted_generated_at(value):
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc) if dt.tzinfo else None
    except (ValueError, TypeError, OverflowError):
        return None

source_stamp = trusted_generated_at(source.get("generated_at"))
if source_stamp is None:
    raise ValueError("Upstream projection has no valid, timezone-aware generated_at")
target = Path("data/v2-runtime-status.json")
if target.exists():
    try:
        previous = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        previous = {}
    previous_stamp = trusted_generated_at(previous.get("generated_at")) if isinstance(previous, dict) else None
    if previous_stamp is not None and source_stamp <= previous_stamp:
        print("DASHBOARD_SYNC_NO_NEW_SOURCE; preserve verified projection and skip redundant commit.")
        raise SystemExit(0)
keys = ("generated_at", "market_observed_at", "cadence_target_minutes", "last_observation_gap_minutes", "last_interval_meets_target", "status", "scan_outcome", "delivery_status", "delivery_confirmed", "pre_buy_count", "buy_zone_count", "evaluated_targets", "observable_coverage_pct", "error_count", "run_url", "scan_completed_at", "decisions_at", "data_quality", "observable_targets", "market_targets_attempted", "market_targets_deferred", "pre_buy_delivered", "pre_buy_delivered_symbols", "final_buy_delivered_symbols", "telegram_delivery_ledger_warnings", "telegram_delivery_semantics", "risk_alerts_delivered", "decisions_total", "market_data_target_count", "market_data_observed_count", "market_data_coverage_pct", "market_data_observed_at", "market_data_deferred_count", "market_data_unavailable_count", "market_data_request_count", "market_data_semantics", "deep_coverage_pct", "deep_observable_targets")
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

# Forward only the explicitly sanitized research-only pulse subset; no private
# wallet IDs, logs, Telegram configuration, or decision authority is published.
pulse = source.get("early_pulse_shadow")
pulse = pulse if isinstance(pulse, dict) else {}
pulse_signals = pulse.get("signals") if isinstance(pulse.get("signals"), list) else []
pulse_fields = ("currency_pair", "symbol", "status", "observed_at",
                "quote_volume_5m_usd", "quote_volume_15m_usd",
                "volume_5m_multiple", "volume_15m_multiple",
                "price_change_5m_pct", "research_priority_score")
# Newly created pools: expose only verified exact addresses and public market facts.
# No pool alone can create a BUY or Telegram action.
new_pool = source.get("new_pool_shadow")
new_pool = new_pool if isinstance(new_pool, dict) else {}
new_pool_signals = new_pool.get("pools") if isinstance(new_pool.get("pools"), list) else []
pool_fields = ("network", "pool_address", "token_address", "symbol", "created_at",
               "age_minutes_at_scan", "liquidity_usd", "volume_5m_usd",
               "buy_transactions_5m", "sell_transactions_5m", "link", "status", "triage_flags", "triage_status")
result["new_pool_shadow"] = {
    "mode": "RESEARCH_ONLY_NEVER_BUY",
    "generated_at": new_pool.get("generated_at"),
    "networks_failed": new_pool.get("networks_failed"),
    "networks_healthy": new_pool.get("networks_healthy"),
    "provider_status": new_pool.get("provider_status"),
    "pools_verified_identity_and_age": new_pool.get("pools_verified_identity_and_age"),
    "pools": [{k: row.get(k) for k in pool_fields} for row in new_pool_signals[:10] if isinstance(row, dict)],
}

result["early_pulse_shadow"] = {
    "mode": "SHADOW_RESEARCH_ONLY_NEVER_BUY",
    "generated_at": pulse.get("generated_at"),
    "probes_attempted": pulse.get("probes_attempted"),
    "probes_verified_closed_candles": pulse.get("probes_verified_closed_candles"),
    "probes_missing_or_rejected": pulse.get("probes_missing_or_rejected"),
    "pulse_count": pulse.get("pulse_count"),
    "divergence_research_count": pulse.get("divergence_research_count"),
    "signals": [{k: row.get(k) for k in pulse_fields} for row in pulse_signals[:8] if isinstance(row, dict)],
}

# Sanitized, aggregate-only prospective study; NEVER export individual call records.
study_source = source.get("early_pulse_study")
study_source = study_source if isinstance(study_source, dict) else {}
study_summary = study_source.get("summary") if isinstance(study_source.get("summary"), dict) else {}
study_out = {}
for horizon in ("60m", "240m"):
    entry = study_summary.get(horizon) if isinstance(study_summary.get(horizon), dict) else {}
    clean = {}
    for cohort in ("pulse", "volume_price_divergence", "matched_control", "near_miss_control", "background_control"):
        raw = entry.get(cohort) if isinstance(entry.get(cohort), dict) else {}
        clean[cohort] = {k: raw.get(k) for k in ("matured", "observed", "missing_window",
                                               "median_gross_reference_change_pct", "outcome_capture_pct",
                                               "fraction_above_21pct")}
    for k in ("total_matured", "total_observed", "outcome_capture_pct",
              "coverage_state", "sampled_unflagged_observed"):
        clean[k] = entry.get(k)
    clean["matched_pairs_observed"] = entry.get("matched_pairs_observed")
    clean["sampled_unflagged_up_21pct"] = entry.get("sampled_unflagged_up_21pct")
    clean["median_paired_difference_pct_points"] = entry.get("median_paired_difference_pct_points")
    clean["evidence_of_outperformance"] = entry.get("evidence_of_outperformance")
    study_out[horizon] = clean
result["early_pulse_study"] = {
    "mode": "PROSPECTIVE_RESEARCH_NO_BUY",
    "updated_at": study_source.get("updated_at"),
    "total_events": study_source.get("total_events"),
    "summary": study_out,
}

target = Path("data/v2-runtime-status.json")
target.parent.mkdir(exist_ok=True)
target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
print("Updated public runtime projection.")
