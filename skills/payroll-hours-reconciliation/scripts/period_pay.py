#!/usr/bin/env python3
"""Tally a Sat->Fri fortnight from a WORK SCHEDULE SHEET route tab.

Reads the schedule grid for a date range and sums each employee code's Morning /
Afternoon hours (bare cells use per-store standard hours; explicit CODE(n) overrides)
plus the Monitoring-column flat $. Prints a tally you then shape into a pay block.

  python3 period_pay.py --tab Schedule-1702 --start 2026/11/07 --end 2026/11/20

Auth: reuses the Google OAuth token Claude Code stored in the macOS keychain (same as
the accessing-google-drive skill). macOS only.
"""
import argparse, json, re, subprocess, urllib.request, urllib.parse, datetime, sys

SHEET = "18_BWXOARekLXgM4Br9tbQ1q6d2gX5SVRm0kk7fYY7h4"

# Per-tab grid layout: morning cols -> standard hrs, afternoon cols (standard 1), monitoring col.
# Standard hrs only known for the 1702 stores; 1736 stores expect explicit (n).
LAYOUT = {
    "Schedule-1702": {
        "morning": {2: 3, 4: 2, 6: 3, 8: 3},   # C HerringCove, E MumfordSobeys, G WalMumford, I Chainlake
        "afternoon": [3, 5, 7, 9],              # D, F, H, J  (standard 1 hr)
        "monitoring": 10,                       # K  (bare $ amount)
    },
    "Schedule-1736": {
        "morning": {2: None, 4: None, 6: None}, # C Clayton, E Timberlea, G Freshco (no standard)
        "afternoon": [3, 5, 7],
        "monitoring": 8,                        # I  (CODE($) )
    },
}
TOKRE = re.compile(r"([A-Za-z]+)\s*\(([\d.]+)\)")


def token():
    raw = subprocess.check_output(
        ["security", "find-generic-password", "-s", "Claude Code-credentials", "-w"])
    d = json.loads(raw)
    return next(v["accessToken"] for k, v in d["mcpOAuth"].items() if k.startswith("gdrive"))


def get_values(tab, tok):
    u = (f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET}/values/"
         f"{urllib.parse.quote(tab)}?majorDimension=ROWS")
    req = urllib.request.Request(u, headers={"Authorization": f"Bearer {tok}"})
    return json.load(urllib.request.urlopen(req)).get("values", [])


def codes(cell):
    cell = str(cell).strip()
    if not cell:
        return []
    toks = TOKRE.findall(cell)
    if toks:
        return [(c.upper(), float(n)) for c, n in toks]
    return [(cell.upper(), None)]   # bare code -> use standard


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tab", required=True, choices=list(LAYOUT))
    ap.add_argument("--start", required=True, help="YYYY/MM/DD")
    ap.add_argument("--end", required=True, help="YYYY/MM/DD inclusive")
    a = ap.parse_args()
    lay = LAYOUT[a.tab]

    d0 = datetime.date.fromisoformat(a.start.replace("/", "-"))
    d1 = datetime.date.fromisoformat(a.end.replace("/", "-"))
    want = {(d0 + datetime.timedelta(days=i)).strftime("%Y/%m/%d")
            for i in range((d1 - d0).days + 1)}

    hrs, flat, bare = {}, {}, {}
    for r in get_values(a.tab, token()):
        if not r or str(r[0]).strip() not in want:
            continue
        for ci, std in lay["morning"].items():
            if ci < len(r):
                for c, n in codes(r[ci]):
                    if n is None and std is None:
                        bare[c] = bare.get(c, 0) + 1
                    else:
                        hrs.setdefault(c, [0.0, 0.0])[0] += (std if n is None else n)
        for ci in lay["afternoon"]:
            if ci < len(r):
                for c, n in codes(r[ci]):
                    if n is None and a.tab == "Schedule-1736":
                        bare[c] = bare.get(c, 0) + 1
                    else:
                        hrs.setdefault(c, [0.0, 0.0])[1] += (1 if n is None else n)
        mi = lay["monitoring"]
        if mi < len(r):
            for c, n in codes(r[mi]):
                if n is not None:            # CODE($) form (1736)
                    flat[c] = flat.get(c, 0) + n
                else:                        # bare "$" number (1702) -> unattributed
                    m = re.match(r"[\d.]+$", str(r[mi]).strip())
                    if m:
                        flat["(monitoring)"] = flat.get("(monitoring)", 0) + float(m.group())

    print(f"# {a.tab}  {a.start} -> {a.end}")
    print("code  morning  afternoon")
    for c in sorted(hrs):
        print(f"  {c:4} {hrs[c][0]:7g}  {hrs[c][1]:8g}")
    if bare:
        print("bare cells (no hours; need standard / flat):", bare)
    if flat:
        print("monitoring/flat $:", {k: round(v, 2) for k, v in flat.items()})
    print("\nreminders: SU=flat $810 · skip MI (and TL on 1736) unless told · "
          "1702 monitoring $ -> HA warehouse · HA advance deduction not in grid")


if __name__ == "__main__":
    main()
