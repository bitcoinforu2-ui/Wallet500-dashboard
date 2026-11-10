"""Fail dashboard deployment on broken HTML/JavaScript or malformed projection.

Prevents successful GitHub Pages publishes of a white/blank screen. The
validator does not access personal data or connect to external providers.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path


def validate(page, data):
    html = Path(page).read_text(encoding="utf-8")
    if not (
        html.lower().count("<!doctype html>") == 1
        and html.count("</html>") == 1
        and html.count("</script>") == 1
        and "<script>" in html
    ):
        raise ValueError("INVALID_STATIC_HTML_STRUCTURE")
    for marker in ('id="earlyPulse"', 'id="newPools"', 'id="studyStats"',
                   'id="candidates"', 'id="truthbox"'):
        if html.count(marker) != 1:
            raise ValueError("MISSING_OR_DUPLICATED_DASHBOARD_COMPONENT:"+marker)
    js = html.split("<script>", 1)[1].split("</script>", 1)[0]
    if len(js) < 1000:
        raise ValueError("TRUNCATED_DASHBOARD_JS")
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "dashboard.js"
        path.write_text(js, encoding="utf-8")
        subprocess.run(["node", "--check", str(path)], check=True, timeout=15)
    result = json.loads(Path(data).read_text(encoding="utf-8"))
    if not isinstance(result, dict) or not isinstance(result.get("decisions"), list):
        raise ValueError("INVALID_PUBLIC_RUNTIME_PROJECTION")
    for field in ("early_pulse_shadow", "new_pool_shadow", "early_pulse_study"):
        value = result.get(field)
        if value is not None and not isinstance(value, dict):
            raise ValueError("INVALID_RESEARCH_PROJECTION:"+field)
    return True


if __name__ == "__main__":
    validate(*sys.argv[1:3])
    print("WALLET500_DASHBOARD_VALIDATED_JS_AND_PROJECTION")
