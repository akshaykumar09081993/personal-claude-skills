#!/usr/bin/env python3
"""Flat-pay vs actual-hours overpayment reconciliation.

Per cycle: wage diff = flat - actual; employer CPP/EI prorated by actual/flat; WCB on total wage.
Optionally fold in a prior settled period (paid vs earned totals) and amounts already repaid.

  python3 reconcile.py --flat 810 --cpp 40.19 --ei 18.48 --wcb-rate 0.0493 \
      --actual 461.50 --actual 284.00 ... \
      [--before-paid 6480 --before-earned 3609.25] [--repaid 3000 --repaid 3000]
"""
import argparse

def block(label, wage, cpp_paid, ei_paid, paid_total, earned_total, wcb_rate):
    # CPP/EI prorated by earned/paid; WCB on wage overpaid
    cpp = cpp_paid * (1 - earned_total / paid_total) if paid_total else 0
    ei = ei_paid * (1 - earned_total / paid_total) if paid_total else 0
    wcb = wage * wcb_rate
    print(f"\n--- {label} ---")
    print(f"  Wage overpayment      ${wage:,.2f}")
    print(f"  Employer CPP overpaid ${cpp:,.2f}")
    print(f"  Employer EI overpaid  ${ei:,.2f}")
    print(f"  WCB @ {wcb_rate*100:.2f}%         ${wcb:,.2f}")
    sub = wage + cpp + ei + wcb
    print(f"  {label} total owed    ${sub:,.2f}")
    return sub

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--flat', type=float, required=True)
    ap.add_argument('--cpp', type=float, required=True, help='employer CPP per cycle (= employee CPP)')
    ap.add_argument('--ei', type=float, required=True, help='employer EI per cycle (= 1.4 x employee EI)')
    ap.add_argument('--wcb-rate', type=float, default=0.0493)
    ap.add_argument('--actual', type=float, action='append', default=[], help='actual earned per after-cycle')
    ap.add_argument('--before-paid', type=float, default=0.0)
    ap.add_argument('--before-earned', type=float, default=0.0)
    ap.add_argument('--repaid', type=float, action='append', default=[])
    a = ap.parse_args()

    grand = 0.0
    # AFTER (flat) period, per cycle
    if a.actual:
        n = len(a.actual)
        paid_total = n * a.flat
        earned_total = sum(a.actual)
        print("Per-cycle (flat period):")
        for i, act in enumerate(a.actual, 1):
            print(f"  cycle {i:2d}: actual ${act:>8,.2f}  wageΔ ${a.flat-act:>8,.2f}")
        grand += block(f"AFTER / flat ({n} cycles x ${a.flat:g})", paid_total - earned_total,
                       n * a.cpp, n * a.ei, paid_total, earned_total, a.wcb_rate)
    # BEFORE settled period (totals only)
    if a.before_paid:
        cycles = round(a.before_paid / a.flat)
        grand += block(f"BEFORE / settled ({cycles} cycles)", a.before_paid - a.before_earned,
                       cycles * a.cpp, cycles * a.ei, a.before_paid, a.before_earned, a.wcb_rate)

    print(f"\n================ TOTAL OWED  ${grand:,.2f} ================")
    for i, r in enumerate(a.repaid, 1):
        print(f"  less repaid {i}: -${r:,.2f}")
    remaining = grand - sum(a.repaid)
    print(f"  REMAINING BALANCE OWED  ${remaining:,.2f}")

if __name__ == '__main__':
    main()
