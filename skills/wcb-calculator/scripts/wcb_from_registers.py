#!/usr/bin/env python3
"""Compute monthly WCB (employees only) from ADP Payroll Register PDFs.

Extracts each payee's current GROSS (T4 wages) by x-coordinate (contractors' CONTRACT pay is
NOT in the gross column, so they drop out automatically). Sums the registers whose PAY END date
is in the target month, times the WCB rate.

Usage:
  python3 wcb_from_registers.py --dir <folder of register PDFs> --rate 0.0493 \
      --period-end 2026-10-09 --period-end 2026-10-23
"""
import argparse, glob, os, re, sys
try:
    import pdfplumber
except ImportError:
    sys.exit("pip install pdfplumber")

SKIP = ['TOTALS', 'COMPANY', 'CURRENT', 'NET', 'NOM', 'GROSS', 'BRUT', 'ADP', 'SPARKLINX',
        'PAGE', 'NOTE', 'FTAX', 'EARNINGS', 'DEDUCTION', 'REVENU', 'RETENUE']

def pay_end(text):
    m = re.search(r'(\d{4}-\d{2}-\d{2})\s+SPARKLINX', text) or re.search(r'END\D*(\d{4}-\d{2}-\d{2})', text.replace('\n', ' '))
    return m.group(1) if m else None

def employee_gross(pdf_path):
    """Return {name: current_gross_dollars} for employees (gross column at x~144)."""
    per = {}
    with pdfplumber.open(pdf_path) as pdf:
        text = '\n'.join((p.extract_text() or '') for p in pdf.pages)
        for p in pdf.pages:
            rows = {}
            for w in p.extract_words():
                rows.setdefault(round(w['top'] / 2) * 2, []).append((w['x0'], w['text']))
            for top in sorted(rows):
                cells = sorted(rows[top])
                namew = [t for x, t in cells if x < 120 and re.match(r"^[A-Z][A-Za-z.']+$", t)]
                name = ' '.join(namew)
                if not name or any(s in name.upper() for s in SKIP):
                    continue
                gross = None
                for x, t in cells:
                    if 136 <= x <= 158 and re.match(r'^\d+$', t):
                        gross = int(t) / 100
                        break
                if gross is not None:
                    per[name] = per.get(name, 0) + gross
    return per, pay_end(text)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', required=True)
    ap.add_argument('--rate', type=float, default=0.0493, help='WCB rate as a fraction (4.93%% = 0.0493)')
    ap.add_argument('--period-end', action='append', default=[], help='pay-end date(s) YYYY-MM-DD to include')
    ap.add_argument('--glob', default='*Register*.pdf')
    args = ap.parse_args()

    files = sorted(glob.glob(os.path.join(args.dir, args.glob)))
    want = set(args.period_end)
    month = {}
    for f in files:
        if 'Calculate' in os.path.basename(f):
            continue  # use Approve (final) only
        per, pe = employee_gross(f)
        if want and pe not in want:
            continue
        print(f"\n{os.path.basename(f)}  (pay-end {pe})")
        for n, g in per.items():
            print(f"   {n:26s} ${g:,.2f}")
            month[n] = month.get(n, 0) + g
    total = sum(month.values())
    print("\n================ MONTH TOTAL (employees only) ================")
    for n, g in sorted(month.items()):
        print(f"   {n:26s} ${g:,.2f}")
    print(f"   {'TOTAL employee gross':26s} ${total:,.2f}")
    print(f"   WCB @ {args.rate*100:.2f}% (${args.rate*100:.2f} per $100) = ${total*args.rate:,.2f}")

if __name__ == '__main__':
    main()
