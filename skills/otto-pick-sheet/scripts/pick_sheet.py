#!/usr/bin/env python3
"""pick_sheet.py — build a per-day PICK SHEET from OTTO order data (dl_orders.js / build JSON).

Rows = products (Code + Product), columns = stores, cells = Final Order (F.O.) for that product/store
on the chosen day. Products that are 0 at EVERY store on a sheet are dropped. Excluded stores are left
out. Each sheet is A4-landscape, fit-to-one-page-wide, header repeats on every printed page.

Usage:
    python3 pick_sheet.py --date Oct-1 [--data otto-orders.json] [--out PickSheet.xlsx]
                          [--exclude 1193808,1193811] [--group costco]
--group costco -> two sheets: "Costco" (stores with COSTCO in the name) and "Other" (the rest).
The --date matches the day label prefix (e.g. "Oct-1"); the correct week is found automatically.
Requires: openpyxl
"""
import json, sys, argparse, os, re
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.properties import PageSetupProperties

ap = argparse.ArgumentParser()
ap.add_argument('--date', required=True, help='day prefix, e.g. Oct-1')
ap.add_argument('--data', default='otto-orders.json')
ap.add_argument('--out', default=None)
ap.add_argument('--exclude', default='', help='comma-separated customer ids to leave out')
ap.add_argument('--group', default='none', choices=['none', 'costco'],
                help='costco = separate Costco sheet + one sheet for all others')
ap.add_argument('--drop-empty-stores', action='store_true',
                help='drop store columns whose total is 0 for the whole day')
args = ap.parse_args()

data = json.load(open(args.data))
records = data.get('records', [])
exclude = {x.strip() for x in args.exclude.split(',') if x.strip()}
DATE = args.date.strip()
OUT = args.out or f'PickSheet_{DATE}.xlsx'

def day_index(days):
    for i, d in enumerate(days):
        if d and d.split()[0] == DATE:
            return i
    return -1

def codes(pr):
    name = pr.get('name', '') or ''
    m = re.match(r'^(\d+)\s*(.*)$', name)   # leading material code, glued or space-separated
    material, desc = (m.group(1), m.group(2)) if m else ('', name)
    sku = pr.get('sku', '') or ''
    upc, bimbo = ([s.strip() for s in sku.split(' - ', 1)] if ' - ' in sku else [sku.strip(), ''])
    code = pr.get('bimboCode') or bimbo or pr.get('code') or material
    return code, (pr.get('description') or desc)

store_order = [c for c in data.get('customers', []) if c['id'] not in exclude]

# products[key] = {code, desc, vals:{storeId: qty}}
products = {}
full_day_label = None
stores_with_data = []
for rec in records:
    if rec['customerId'] in exclude:
        continue
    di = day_index(rec['days'])
    if di < 0:
        continue
    if rec['customerId'] not in stores_with_data:
        stores_with_data.append(rec['customerId'])
    full_day_label = rec['days'][di]
    for pr in rec['products']:
        code, desc = codes(pr)
        key = code or desc
        qty = pr['fo'][di] if di < len(pr['fo']) else 0
        p = products.setdefault(key, {'code': code, 'desc': desc, 'vals': {}})
        p['vals'][rec['customerId']] = p['vals'].get(rec['customerId'], 0) + (qty or 0)

if full_day_label is None:
    sys.exit(f'No records contain day "{DATE}". Check the date or the data file.')

cols_all = [c for c in store_order if c['id'] in stores_with_data]

# optionally drop stores that are 0 across every product that day (e.g. the DST holding account)
if args.drop_empty_stores:
    cols_all = [c for c in cols_all
                if sum(p['vals'].get(c['id'], 0) for p in products.values()) > 0]

# order stores by location (first-appearance), and within a location put DL before GR.
# location key = store name with the leading DL/GR (and DELI) stripped, so DL/GR variants of
# the same store group together even when the name has no store number (e.g. Herring Cove).
def _locnum(name):
    k = re.sub(r'^\s*(DL|GR)\b', '', name, flags=re.I)
    k = re.sub(r'\bDELI\b', '', k, flags=re.I)
    k = re.sub(r"[^a-z0-9]+", " ", k.lower()).strip()
    return k or name.lower()
def _typerank(name):
    u = name.upper().lstrip()
    return 0 if u.startswith('DL') else 1 if u.startswith('GR') else 2
_loc_order = {}
for c in cols_all:
    k = _locnum(c['name'])
    if k not in _loc_order: _loc_order[k] = len(_loc_order)
cols_all.sort(key=lambda c: (_loc_order[_locnum(c['name'])], _typerank(c['name'])))

# ---------- styles (black & white print friendly — no bright colors, crisp Arial) ----------
FONT = 'Arial'
title_font = Font(name=FONT, bold=True, size=14, color='000000')
hdr_font = Font(name=FONT, bold=True, size=10, color='000000'); hdr_fill = PatternFill('solid', fgColor='D9D9D9')
base_font = Font(name=FONT, size=10, color='000000')            # Code / Product text
bold = Font(name=FONT, bold=True, size=10, color='000000')
num_font = Font(name=FONT, bold=True, size=11, color='000000')  # order quantities: bold black, larger
zero_font = Font(name=FONT, size=10, color='B0B0B0')            # zeros: faint grey so real picks pop
tot_fill = PatternFill('solid', fgColor='D9D9D9')
thin = Side(style='thin', color='808080'); border = Border(left=thin, right=thin, top=thin, bottom=thin)
center = Alignment(horizontal='center')

def add_sheet(wb, title, cols_stores):
    if not cols_stores:
        return 0
    # products with a nonzero total across THIS sheet's stores
    rows = []
    for p in products.values():
        total = sum(p['vals'].get(c['id'], 0) for c in cols_stores)
        if total > 0:
            rows.append((p, total))
    # sort by the product code number (numeric codes first, then any non-numeric by text)
    def _code_key(p):
        c = (p['code'] or '').strip()
        return (0, int(c), '') if c.isdigit() else (1, 0, c)
    rows.sort(key=lambda x: _code_key(x[0]))

    ws = wb.create_sheet(title[:31])
    ncol = 2 + len(cols_stores) + 1
    ws['A1'] = f'PICK SHEET — {full_day_label} — {title}   (Route {data.get("route","")})'
    ws['A1'].font = title_font
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ncol)
    ws.append([])
    ws.append(['Code', 'Product'] + [c['name'] for c in cols_stores] + ['Total'])
    hrow = ws.max_row
    for j in range(1, ncol + 1):
        c = ws.cell(row=hrow, column=j)
        c.font = hdr_font; c.fill = hdr_fill; c.border = border
        c.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)

    store_totals = [0] * len(cols_stores)
    for p, total in rows:
        r = [p['code'], p['desc']]
        for k, c in enumerate(cols_stores):
            v = p['vals'].get(c['id'], 0); store_totals[k] += v; r.append(v)
        r.append(total)
        ws.append(r)
        rr = ws.max_row
        ws.cell(row=rr, column=1).font = base_font          # Code
        ws.cell(row=rr, column=2).font = base_font          # Product
        for k in range(len(cols_stores)):
            cell = ws.cell(row=rr, column=3 + k); cell.alignment = center
            cell.font = num_font if cell.value else zero_font
        tc = ws.cell(row=rr, column=ncol); tc.font = bold; tc.alignment = center

    ws.append(['', 'TOTAL'] + store_totals + [sum(store_totals)])
    rr = ws.max_row
    for j in range(1, ncol + 1):
        c = ws.cell(row=rr, column=j); c.font = bold; c.fill = tot_fill; c.alignment = center

    for row in ws.iter_rows(min_row=hrow, max_row=ws.max_row, min_col=1, max_col=ncol):
        for c in row: c.border = border

    ws.freeze_panes = ws.cell(row=hrow + 1, column=3)
    ws.column_dimensions['A'].width = 10
    ws.column_dimensions['B'].width = 38
    for k in range(len(cols_stores)):
        ws.column_dimensions[get_column_letter(3 + k)].width = 14
    ws.column_dimensions[get_column_letter(ncol)].width = 9
    ws.row_dimensions[hrow].height = 42

    ws.page_setup.orientation = 'landscape'
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.sheet_properties.pageSetUpPr = PageSetupProperties(fitToPage=True)
    ws.page_setup.fitToWidth = 1; ws.page_setup.fitToHeight = 0
    ws.print_title_rows = f'{hrow}:{hrow}'
    ws.print_options.gridLines = True; ws.print_options.horizontalCentered = True
    ws.page_margins.left = ws.page_margins.right = 0.3
    ws.page_margins.top = ws.page_margins.bottom = 0.4
    ws.page_margins.header = ws.page_margins.footer = 0.2
    ws.oddFooter.center.text = "Pick sheet — &A — page &P of &N"
    return len(rows)

wb = Workbook()
summary = []
if args.group == 'costco':
    costco = [c for c in cols_all if 'COSTCO' in c['name'].upper()]
    other = [c for c in cols_all if 'COSTCO' not in c['name'].upper()]
    summary.append(('Costco', add_sheet(wb, 'Costco', costco), costco))
    summary.append(('Other stores', add_sheet(wb, 'Other stores', other), other))
else:
    summary.append((f'Pick {DATE}', add_sheet(wb, f'Pick {DATE}', cols_all), cols_all))

wb.remove(wb['Sheet'])  # drop the default empty sheet
wb.save(OUT)

print('wrote', OUT, '| day:', full_day_label)
for title, nrows, stores in summary:
    print(f'  [{title}] {nrows} products  ({len(stores)} stores: ' +
          ', '.join(c['name'] for c in stores) + ')')
