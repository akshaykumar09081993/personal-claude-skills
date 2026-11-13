#!/usr/bin/env python3
"""Confirm-gated Discord trading bot (day-trader-skill on a dedicated VM).

You chat in the #trading channel; Claude runs the trader-* skills (scanner, news,
entry, exit, timemachine, budget, risk, broker) in ~/trading and replies. It will
build an order TICKET but it can NOT place an order on a normal message — the order
tools are withheld. An order only becomes possible when you reply with a message that
starts with `CONFIRM`, which unlocks the Alpaca order tool for that single run.

Two safety gates, both enforced here (the headless CLI has no Allow/Deny card):
  1. trader-risk must PASS the exact order (the broker skill checks it).
  2. You must type `CONFIRM ...` — only then is mcp__alpaca__place_stock_order allowed.

Paper trading by default (ALPACA_PAPER_TRADE=true). Going live is the user's own edit.

Env (see ~/trading/.env):
  DISCORD_BOT_TOKEN         bot token
  CH_TRADING               numeric channel id for interactive trading
  CH_ALERTS                numeric channel id for read-only alerts (not listened to)
  ANTHROPIC_API_KEY        Claude Code billing/auth
  ALPACA_API_KEY/SECRET    paper keys, consumed by the alpaca MCP server
  CLAUDE_BIN               path to claude (default: claude)
  WS                       workspace dir (default: ~/trading)
"""
import os, json, asyncio, subprocess, pathlib
import discord

TOKEN = os.environ["DISCORD_BOT_TOKEN"]
CLAUDE = os.environ.get("CLAUDE_BIN", "claude")
WS = os.path.expanduser(os.environ.get("WS", "~/trading"))
TIMEOUT = int(os.environ.get("CLAUDE_TIMEOUT", "1800"))
CH_TRADING = os.environ.get("CH_TRADING", "")

# Read-only / analysis tools: skills run as python via Bash; Alpaca READ tools allowed.
# NOTE: order/mutating Alpaca tools are deliberately absent here.
ANALYSIS_TOOLS = [
    "Bash", "Read", "Write", "Edit", "Glob", "Grep",
    "mcp__alpaca__get_account_info", "mcp__alpaca__get_all_positions",
    "mcp__alpaca__get_open_position", "mcp__alpaca__get_orders",
    "mcp__alpaca__get_clock", "mcp__alpaca__get_stock_snapshot",
    "mcp__alpaca__get_stock_latest_quote",
]
# Mutating tools, unlocked ONLY on a CONFIRM message:
ORDER_TOOLS = [
    "mcp__alpaca__place_stock_order",
    "mcp__alpaca__cancel_order_by_id",
    "mcp__alpaca__close_position",
]
# Always forbidden (bulk / options / crypto): never unlocked by this bot.
DENY_TOOLS = [
    "mcp__alpaca__close_all_positions", "mcp__alpaca__cancel_all_orders",
    "mcp__alpaca__place_option_order", "mcp__alpaca__place_crypto_order",
    "mcp__alpaca__exercise_options_position",
]

BASE_SCOPE = (
    "You are the day-trading assistant running in ~/trading on a dedicated VM, driving the "
    "trader-* skills in ~/.claude/skills (scanner, news, entry, exit, timemachine, risk, budget, "
    "broker, alerts, analyst, pelosi). US stocks only. The account is Alpaca PAPER unless the env "
    "says otherwise. Follow the skills' pipeline: scanner -> news -> entry -> exit -> timemachine -> "
    "budget -> risk -> broker. Always run trader-risk and only treat a READY (risk PASS) ticket as "
    "placeable. Size every trade with trader-budget's config (~/trading/trader/config.json). Keep "
    "replies short and concrete for a phone screen. Never use margin, shorts, options or crypto."
)
ANALYSIS_SCOPE = BASE_SCOPE + (
    " THIS MESSAGE IS ANALYSIS ONLY. You do NOT have the order tools and you must NOT attempt to "
    "place, cancel or close any order. When a trade is ready, show the trader-broker TICKET exactly "
    "(symbol, side, qty, stop-loss, take-profit, max loss) and end with one line: "
    "'To place it, reply: CONFIRM <side> <qty> <SYMBOL>'. Then stop."
)
EXEC_SCOPE = BASE_SCOPE + (
    " The user has just sent an explicit CONFIRM for one specific order. Re-run trader-risk to confirm "
    "it still PASSES, verify the order matches their CONFIRM (same side, qty, symbol), then place EXACTLY "
    "that one order via trader-broker / place_stock_order and report the fill. Place ONE order only. If "
    "the CONFIRM does not match a current READY ticket, place nothing and say why."
)


def run_claude(prompt, scope, allowed, session_id):
    cmd = [CLAUDE, "-p", prompt, "--output-format", "json",
           "--append-system-prompt", scope,
           "--allowedTools", ",".join(allowed),
           "--disallowedTools", ",".join(DENY_TOOLS)]
    if session_id:
        cmd += ["--resume", session_id]
    r = subprocess.run(cmd, cwd=WS, capture_output=True, text=True, timeout=TIMEOUT)
    try:
        j = json.loads(r.stdout.strip())
        return (j.get("result") or "(done)"), j.get("session_id")
    except Exception:
        return ((r.stdout or r.stderr or "(no output)").strip()[:1800]), session_id


intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)
SESSION = {"id": None}  # single trading session, resumed across messages


@client.event
async def on_ready():
    print("Trader bot online as", client.user, "| trading channel:", CH_TRADING, flush=True)
    for g in client.guilds:
        for ch in getattr(g, "text_channels", []):
            if str(ch.id) == CH_TRADING:
                print(f"  watching #{ch.name} ({ch.id})", flush=True)


async def send_chunks(channel, text):
    text = text or "(done)"
    for i in range(0, len(text), 1900):
        await channel.send(text[i:i + 1900])


@client.event
async def on_message(msg):
    if msg.author.bot or str(msg.channel.id) != CH_TRADING:
        return
    text = msg.content.strip()
    is_confirm = text.upper().startswith("CONFIRM")
    scope = EXEC_SCOPE if is_confirm else ANALYSIS_SCOPE
    allowed = (ANALYSIS_TOOLS + ORDER_TOOLS) if is_confirm else ANALYSIS_TOOLS
    tag = "EXECUTE" if is_confirm else "analyze"
    async with msg.channel.typing():
        loop = asyncio.get_event_loop()
        try:
            result, sid = await loop.run_in_executor(
                None, run_claude, text, scope, allowed, SESSION["id"])
            if sid:
                SESSION["id"] = sid
            await send_chunks(msg.channel, f"**[{tag}]** {result}")
        except subprocess.TimeoutExpired:
            await msg.channel.send(f"⏱️ timed out after {TIMEOUT//60} min.")
        except Exception as e:
            await msg.channel.send(f"⚠️ error: {e}")


if __name__ == "__main__":
    if not CH_TRADING:
        raise SystemExit("CH_TRADING not set in env")
    client.run(TOKEN)
