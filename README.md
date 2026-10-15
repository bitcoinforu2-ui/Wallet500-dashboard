# Wallet500 Dashboard

Mobile-friendly Hebrew dashboard using only the sanitized runtime projection from Wallet500-v2. No scanner, trading or Telegram sender runs here.

## Setup

1. Settings → Pages → Source: GitHub Actions.
2. Add Actions secret `DASHBOARD_SOURCE_TOKEN`: fine-grained read-only token restricted to Wallet500-v2, with Contents: read access. Never put it in HTML or source code.
3. Run “Sync and deploy Wallet500 dashboard” in Actions.

The scheduled workflow refreshes the projection every ten minutes (GitHub schedules may be delayed). Without the source token, the last snapshot is retained, and the UI hides current metrics and decisions after 25 minutes. Publication requires Pages availability for this repository.

Expected URL after successful deployment: https://bitcoinforu2-ui.github.io/Wallet500-dashboard/
