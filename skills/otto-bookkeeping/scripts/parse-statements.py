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
from datetime import date

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
    m = re.search(r'FOR WEEK:\s*(\d{4}-\d{2}-\d{2})\s*-\s*(\d{4}-\d{2}-\d{2})', txt)
    rec['week_from'], rec['week_to'] = (m.group(1), m.group(2)) if m else ('', '')

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

def in_paid_window(week_to, paid_month):
    """week-ending date within [previous-month-start .. paid-month end]."""
    if not paid_month or not week_to:
        return True
    y, m = map(int, paid_month.split('-'))
    prev_y, prev_m = (y - 1, 12) if m == 1 else (y, m - 1)
    lo = date(prev_y, prev_m, 1)
    hi = date(y, 12, 31) if m == 12 else date(y, m + 1, 1)  # exclusive-ish upper
    try:
        d = date.fromisoformat(week_to)
    except ValueError:
        return True
    return lo <= d < hi

def money(x): return f"{x:,.2f}"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', required=True)
    ap.add_argument('--csv')
    ap.add_argument('--paid-month')
    ap.add_argument('--route', default='1702')
    a = ap.parse_args()

    root = os.path.expanduser(a.dir)
    pdfs = [f for f in glob.glob(os.path.join(root, '**', '*.pdf'), recursive=True)
            if re.search(r'distributor weekly statement', os.path.basename(f), re.I)]
    if not pdfs:
        sys.exit(f"No 'Distributor Weekly Statement' PDFs found under {root}")

    recs = []
    for f in sorted(pdfs):
        try:
            r = parse_pdf(f)
        except Exception as e:
            print(f"  ! skip {os.path.basename(f)}: {e}", file=sys.stderr); continue
        if a.route != 'all' and r['route'] and r['route'] != a.route:
            continue
        if not in_paid_window(r['week_to'], a.paid_month):
            continue
        recs.append(r)

    if not recs:
        sys.exit("No statements matched the filters.")
    recs.sort(key=lambda r: r['week_to'])

    cols = ['week_from','week_to','route','statement_no','product_total','total_credit',
            'distributor_fees','distributor_fees_tax','fixed_distributor_fee','fixed_fee_tax',
            'deposit','total_manual_adj','balance_due_week','balance_due_ytd','file']
    out = os.path.expanduser(a.csv) if a.csv else os.path.join(root, 'statements-ledger.csv')
    with open(out, 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=cols); w.writeheader()
        for r in recs: w.writerow(r)

    # summary
    tot = lambda k: sum(r[k] for r in recs)
    print(f"\nParsed {len(recs)} weekly statement(s)" + (f" for payments in {a.paid_month}" if a.paid_month else "") + f" (route {a.route}).")
    print(f"CSV ledger: {out}\n")
    hdr = f"{'Week ending':12} {'Product $':>13} {'Total credit':>13} {'Dist. fees':>12} {'Balance (net)':>14}"
    print(hdr); print('-' * len(hdr))
    for r in recs:
        print(f"{r['week_to']:12} {money(r['product_total']):>13} {money(r['total_credit']):>13} "
              f"{money(r['distributor_fees']):>12} {money(r['balance_due_week']):>14}")
    print('-' * len(hdr))
    print(f"{'TOTAL':12} {money(tot('product_total')):>13} {money(tot('total_credit')):>13} "
          f"{money(tot('distributor_fees')):>12} {money(tot('balance_due_week')):>14}")
    print(f"\nNet settled across these weeks (sum of weekly Balance Due): {money(tot('balance_due_week'))}")

if __name__ == '__main__':
    main()
