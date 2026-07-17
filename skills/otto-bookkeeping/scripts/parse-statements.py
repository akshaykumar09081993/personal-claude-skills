#!/usr/bin/env python3
"""
parse-statements.py — turn OTTO "Distributor Weekly Statement" PDFs into a bookkeeping ledger.

Reads every "Distributor Weekly Statement ... .pdf" in a folder, extracts the money lines, writes:
  - a CSV ledger  (one row per weekly statement)
  - a printed monthly summary

This is step 2 of the flow: run `otto-download-statements` first (it saves the PDFs into
~/Documents/bookeeping/<year>/<Month>/Checking), then run this over that folder.

Requires: pdfplumber   (pip install pdfplumber --break-system-packages)

Usage:
  python3 parse-statements.py --dir ~/Documents/bookeeping/2026/June/Checking
  python3 parse-statements.py --dir ~/Documents/bookeeping/2026/June/Checking --paid-month 2026-06
  python3 parse-statements.py --dir <folder> --csv ~/Documents/bookeeping/2026/June/ledger-june.csv

Options:
  --dir DIR          folder containing the statement PDFs (searched recursively). REQUIRED.
  --csv PATH         output CSV path (default: <dir>/statements-ledger.csv)
  --paid-month YYYY-MM  only include statements whose week-ending date falls in
                        [previous-month-start .. that month end] (the "paid this month" window);
                        omit to include all statements found.
  --route 1702       route filter (default 1702; use 'all' for every route).

Each statement's "Current Week" column is the weekly figure; the LAST number on a line is YTD,
the SECOND-LAST is the Current Week value.
"""
import argparse, csv, os, re, sys, glob
from datetime import date, timedelta

try:
    import pdfplumber
except ImportError:
    sys.exit("pdfplumber missing. Install: python3 -m pip install pdfplumber --break-system-packages")

NUM = r'-?[\d,]+\.\d{2}'

def nums(line):
    return [float(x.replace(',', '')) for x in re.findall(NUM, line)]

def current_week(line):
    """Second-to-last number on a line = Current Week; last = YTD."""
    n = nums(line)
    return n[-2] if len(n) >= 2 else (n[-1] if n else 0.0)

def ytd(line):
    n = nums(line)
    return n[-1] if n else 0.0

def grab(lines, label, exact=True):
    for ln in lines:
        s = ln.strip()
        if exact:
            if s == label or s.startswith(label + ' '):
                if re.search(NUM, s):
                    return s
        else:
            if label.lower() in s.lower() and re.search(NUM, s):
                return s
    return None

def parse_pdf(fp):
    with pdfplumber.open(fp) as pdf:
        txt = "\n".join((pg.extract_text() or "") for pg in pdf.pages)
    lines = txt.split('\n')
    rec = {'file': os.path.basename(fp)}
    m = re.search(r'ROUTE ID:\s*(\d+)', txt);            rec['route'] = m.group(1) if m else ''
    m = re.search(r'STATEMENT NUMBER:\s*(\S+)', txt);     rec['statement_no'] = m.group(1) if m else ''
    # Week dates: the FILENAME is OTTO's label; the PDF body "FOR WEEK" is what the file ACTUALLY contains.
    # OTTO sometimes mis-links a week to a prior-year file, so capture both and flag any mismatch.
    fn = re.search(r'From\s*(\d{4}-\d{2}-\d{2})\s*To\s*(\d{4}-\d{2}-\d{2})', os.path.basename(fp))
    cm = re.search(r'FOR WEEK:\s*(\d{4}-\d{2}-\d{2})\s*-\s*(\d{4}-\d{2}-\d{2})', txt)
    rec['content_week_to'] = cm.group(2) if cm else ''
    if fn:
        rec['week_from'], rec['week_to'] = fn.group(1), fn.group(2)
    elif cm:
        rec['week_from'], rec['week_to'] = cm.group(1), cm.group(2)
    else:
        rec['week_from'], rec['week_to'] = '', ''
    rec['mismatch'] = bool(fn and cm and fn.group(2) != cm.group(2))

    def cw(label, exact=True):
        ln = grab(lines, label, exact)
        return round(current_week(ln), 2) if ln else 0.0

    rec['product_total']        = cw('Product Total')
    rec['total_credit']         = cw('Total Credit')
    rec['distributor_fees']     = cw('Distributor Fees')          # base fee (excl GST)
    rec['distributor_fees_tax'] = cw('Distributor Fees GST/HST')
    rec['fixed_distributor_fee']= cw('Fixed Distributor Fee')
    rec['fixed_fee_tax']        = cw('Fixed Distributor Fee HST/GST')
    rec['deposit']              = cw('Deposit')
    rec['total_manual_adj']     = cw('Total Manual Adjustment')
    rec['balance_due_week']     = cw('Balance Due')               # <-- net settled for the week
    ln = grab(lines, 'Balance Due')
    rec['balance_due_ytd']      = round(ytd(ln), 2) if ln else 0.0
    return rec

def payment_date(week_to):
    """Statement week ends Saturday -> generated Sunday -> paid the next Friday = week_to + 6 days."""
    return date.fromisoformat(week_to) + timedelta(days=6)

def in_paid_window(week_to, paid_month):
    """Include if the PAYMENT (week-ending Saturday + 6 days = next Friday) falls in paid_month."""
    if not paid_month or not week_to:
        return True
    try:
        pd = payment_date(week_to)
    except ValueError:
        return True
    return pd.strftime('%Y-%m') == paid_month

def money(x): return f"{x:,.2f}"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', required=True)
    ap.add_argument('--csv')
    ap.add_argument('--paid-month')
    ap.add_argument('--route', default='1702')
    ap.add_argument('--strict', action='store_true',
                    help="exclude files whose internal FOR WEEK date differs from the filename week")
    a = ap.parse_args()

    root = os.path.expanduser(a.dir)
    pdfs = [f for f in glob.glob(os.path.join(root, '**', '*.pdf'), recursive=True)
            if re.search(r'distributor weekly statement', os.path.basename(f), re.I)]
    if not pdfs:
        sys.exit(f"No 'Distributor Weekly Statement' PDFs found under {root}")

    recs = []
    mismatches = []
    for f in sorted(pdfs):
        try:
            r = parse_pdf(f)
        except Exception as e:
            print(f"  ! skip {os.path.basename(f)}: {e}", file=sys.stderr); continue
        if a.route != 'all' and r['route'] and r['route'] != a.route:
            continue
        if not in_paid_window(r['week_to'], a.paid_month):
            continue
        try:
            r['payment_date'] = payment_date(r['week_to']).isoformat()
        except Exception:
            r['payment_date'] = ''
        if r.get('mismatch'):
            mismatches.append(r)
            if a.strict:   # --strict: drop files whose internal date != filename week
                continue
        recs.append(r)

    if mismatches:
        verb = "EXCLUDED (--strict)" if a.strict else "INCLUDED (OTTO filename week is authoritative)"
        print(f"\nNote: OTTO printed a different (prior-year) 'FOR WEEK' date inside these files — {verb}:")
        for r in mismatches:
            print(f"    • week {r['week_from']}..{r['week_to']}  (file's internal FOR WEEK says "
                  f"{r['content_week_to']}, stmt {r['statement_no']})")
        print()

    if not recs:
        sys.exit("No statements matched the filters.")
    recs.sort(key=lambda r: r['week_to'])

    cols = ['week_from','week_to','content_week_to','payment_date','route','statement_no','product_total','total_credit',
            'distributor_fees','distributor_fees_tax','fixed_distributor_fee','fixed_fee_tax',
            'deposit','total_manual_adj','balance_due_week','balance_due_ytd','file']
    out = os.path.expanduser(a.csv) if a.csv else os.path.join(root, 'statements-ledger.csv')
    with open(out, 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction='ignore'); w.writeheader()
        for r in recs: w.writerow(r)

    # summary
    tot = lambda k: sum(r[k] for r in recs)
    print(f"\nParsed {len(recs)} weekly statement(s)" + (f" for payments in {a.paid_month}" if a.paid_month else "") + f" (route {a.route}).")
    print(f"CSV ledger: {out}\n")
    hdr = f"{'Week ending':12} {'Paid (Fri)':12} {'Product $':>13} {'Total credit':>13} {'Dist. fees':>12} {'Balance (net)':>14}"
    print(hdr); print('-' * len(hdr))
    for r in recs:
        print(f"{r['week_to']:12} {r.get('payment_date',''):12} {money(r['product_total']):>13} {money(r['total_credit']):>13} "
              f"{money(r['distributor_fees']):>12} {money(r['balance_due_week']):>14}")
    print('-' * len(hdr))
    print(f"{'TOTAL':12} {'':12} {money(tot('product_total')):>13} {money(tot('total_credit')):>13} "
          f"{money(tot('distributor_fees')):>12} {money(tot('balance_due_week')):>14}")
    print(f"\nNet settled across these weeks (sum of weekly Balance Due): {money(tot('balance_due_week'))}")

if __name__ == '__main__':
    main()
