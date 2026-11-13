#!/usr/bin/env python3
"""Read-only market alerts -> Discord #alerts. Run from cron. No order path.

Runs a trader-* skill tool and posts a trimmed result to the CH_ALERTS channel
using the bot token (Discord REST). Usage:
    alerts_post.py premarket     # scan.py daily (pre-market setups)
    alerts_post.py orb           # scan.py orb --at <now ET>
    alerts_post.py news TSLA,NVDA # news.py on a watchlist
    alerts_post.py pelosi        # ptr.py index --member pelosi
Env: DISCORD_BOT_TOKEN, CH_ALERTS. Keys never printed.
"""
import os, sys, json, subprocess, urllib.request, pathlib

SKILLS = os.path.expanduser("~/.claude/skills")
TOKEN = os.environ["DISCORD_BOT_TOKEN"]
CH = os.environ["CH_ALERTS"]


def py(skill, *args):
    tool = {"scanner": "scan.py", "news": "news.py", "pelosi": "ptr.py"}[skill]
    p = subprocess.run(["python3", f"{SKILLS}/trader-{skill}/{tool}", *args],
                       capture_output=True, text=True, timeout=600)
    return (p.stdout or p.stderr or "(no output)").strip()


def post(content):
    content = content[:1900] or "(nothing)"
    req = urllib.request.Request(
        f"https://discord.com/api/v10/channels/{CH}/messages",
        data=json.dumps({"content": content}).encode(),
        headers={"Authorization": f"Bot {TOKEN}", "Content-Type": "application/json"},
        method="POST")
    urllib.request.urlopen(req, timeout=30)


def main():
    job = sys.argv[1] if len(sys.argv) > 1 else "premarket"
    if job == "premarket":
        out = py("scanner", "daily"); head = "📈 **Pre-market setups**"
    elif job == "orb":
        out = py("scanner", "orb"); head = "🔔 **Opening-range breakouts**"
    elif job == "news":
        tickers = sys.argv[2] if len(sys.argv) > 2 else "TSLA,NVDA,AAPL"
        out = py("news", "--tickers", tickers, "--hours", "12"); head = f"📰 **News: {tickers}**"
    elif job == "pelosi":
        out = py("pelosi", "index", "--member", "pelosi"); head = "🏛️ **Congress filings**"
    else:
        out = f"unknown job {job}"; head = "⚠️"
    post(f"{head}\n```\n{out[:1700]}\n```")


if __name__ == "__main__":
    main()
