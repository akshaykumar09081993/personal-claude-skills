# trader-bot — confirm-gated Discord day-trading bot

Runs the `day-trader-skill` (the 11 `trader-*` skills) on a dedicated GCP VM and
lets you drive it from Discord on your phone. US stocks, **Alpaca paper by default**.

## Where it runs
- VM: `trader-bot` (GCP project `sparklinxgroup`, zone `northamerica-northeast1-b`), isolated from `rst-prod`.
- SSH: `gcloud compute ssh trader-bot --zone=northamerica-northeast1-b --project=sparklinxgroup`
- Workspace: `/home/avu/trading` (holds `trader/config.json` = paper + budget/risk limits, `.mcp.json` = Alpaca MCP, `.env` = secrets).
- Skills: `/home/avu/.claude/skills/trader-*`
- Bot: `/home/avu/trader-bot/bot.py` → systemd `trader-bot.service`
- Alerts: `/home/avu/trader-bot/alerts_post.py` via crontab (ET), posts to `#alerts`.

## Safety model (two gates, bot-enforced)
The headless Claude CLI has no Allow/Deny card, so the gates are enforced in `bot.py`:
1. **Tool withholding** — a normal `#trading` message runs Claude with analysis/read-only
   tools only; the Alpaca **order tools are not passed**, so an order is impossible. Claude
   builds the ticket and tells you the exact `CONFIRM ...` phrase.
2. **Typed CONFIRM** — only a message starting with `CONFIRM` runs Claude with
   `mcp__alpaca__place_stock_order` unlocked, and `trader-risk` must still PASS the order.
Bulk/options/crypto tools (`close_all_positions`, `place_option_order`, …) are permanently denied.

## Going live (user action only)
Edit `/home/avu/trading/.env`: set live Alpaca keys and `ALPACA_PAPER_TRADE=false`, and set
`"paper": false` in `trader/config.json`. Restart: `sudo systemctl restart trader-bot`.

## Secrets (`/home/avu/trading/.env`, chmod 600)
`ANTHROPIC_API_KEY`, `ALPACA_API_KEY`, `ALPACA_SECRET_KEY`, `DISCORD_BOT_TOKEN`,
`CH_TRADING`, `CH_ALERTS`. Never commit these.
