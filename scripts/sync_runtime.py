#!/usr/bin/env python3
"""Copy only the explicit dashboard projection from the private engine."""
import json, os, urllib.request
from pathlib import Path
token = os.environ.get("SOURCE_TOKEN", "")
if not token:
    print("::warning::DASHBOARD_SOURCE_TOKEN is missing; retained snapshot will expire normally.")
    raise SystemExit(0)
url = "https://api.github.com/repos/bitcoinforu2-ui/Wallet500-v2/contents/data/v2-runtime-status.json?ref=main"
request = urllib.request.Request(url, headers={"Authorization": "Bearer " + token, "Accept": "application/vnd.github.raw+json", "X-GitHub-Api-Version": "2022-11-28"})
with urllib.request.urlopen(request, timeout=30) as response:
    raw = response.read(2_000_001)
if len(raw) > 2_000_000:
    raise ValueError("Projection exceeds size limit")
source = json.loads(raw)
keys = ("generated_at", "market_observed_at", "status", "scan_outcome", "delivery_status", "delivery_confirmed", "pre_buy_count", "buy_zone_count", "evaluated_targets", "observable_coverage_pct", "error_count", "run_url")
if not isinstance(source, dict) or not isinstance(source.get("decisions"), list):
    raise ValueError("Invalid projection")
result = {key: source.get(key) for key in keys}
result["decisions"] = [{key: row.get(key) for key in ("symbol", "identity_key", "state", "pre_buy", "reasons")} for row in source["decisions"][:100] if isinstance(row, dict)]
target = Path("data/v2-runtime-status.json")
target.parent.mkdir(exist_ok=True)
target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
print("Updated public runtime projection.")
