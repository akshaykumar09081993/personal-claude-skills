#!/usr/bin/env python3
"""pick_sheet.py — build a per-day PICK SHEET from OTTO order data (dl_orders.js / build JSON).

Rows = products (Code + Product), columns = stores, cells = Final Order (F.O.) for that product/store
on the chosen day. Products that are 0 at EVERY store are dropped. Excluded stores are left out.

Usage:
    python3 pick_sheet.py --date Oct-1 [--data otto-orders.json] [--out PickSheet.xlsx]
                          [--exclude 1193808,1193811]
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

# ordered store list (respect customers order), excluding requested ids and any with no data that day
store_order = [c for c in data.get('customers', []) if c['id'] not in exclude]

# products[code] = {code, desc, vals:{storeId: qty}}
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

# columns = only stores that actually have data for this day, in customer order
cols_stores = [c for c in store_order if c['id'] in stores_with_data]

# drop products that are 0 at every store; sort by description
rows = []
for p in products.values():
    total = sum(p['vals'].get(c['id'], 0) for c in cols_stores)
    if total > 0:
        rows.append((p, total))
rows.sort(key=lambda x: (x[0]['desc'] or ''))

# ---------------- workbook ----------------
hdr_font = Font(bold=True, color='FFFFFF'); hdr_fill = PatternFill('solid', fgColor='305496')
bold = Font(bold=True); center = Alignment(horizontal='center', vertical='center', wrap_text=True)
tot_fill = PatternFill('solid', fgColor='FCE4D6'); zero_font = Font(color='BFBFBF')
thin = Side(style='thin', color='D9D9D9'); border = Border(left=thin, right=thin, top=thin, bottom=thin)

wb = Workbook(); ws = wb.active; ws.title = f'Pick {DATE}'
ws['A1'] = f'PICK SHEET — {full_day_label}   (Route {data.get("route","")})'
ws['A1'].font = Font(bold=True, size=14)
ncol = 2 + len(cols_stores) + 1
ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ncol)

header = ['Code', 'Product'] + [c['name'] for c in cols_stores] + ['Total']
ws.append([])  # row 2 spacer
ws.append(header)
hrow = ws.max_row
for j in range(1, ncol + 1):
    c = ws.cell(row=hrow, column=j); c.font = hdr_font; c.fill = hdr_fill; c.alignment = center; c.border = border

store_totals = [0] * len(cols_stores)
for p, total in rows:
    r = [p['code'], p['desc']]
    for k, c in enumerate(cols_stores):
        v = p['vals'].get(c['id'], 0)
        store_totals[k] += v
        r.append(v)
    r.append(total)
    ws.append(r)
    rr = ws.max_row
    for k in range(len(cols_stores)):
        cell = ws.cell(row=rr, column=3 + k); cell.alignment = Alignment(horizontal='center')
        if not cell.value: cell.font = zero_font
    tcell = ws.cell(row=rr, column=ncol); tcell.font = bold; tcell.alignment = Alignment(horizontal='center')

# totals row
trow = ['', 'TOTAL'] + store_totals + [sum(store_totals)]
ws.append(trow)
rr = ws.max_row
for j in range(1, ncol + 1):
    c = ws.cell(row=rr, column=j); c.font = bold; c.fill = tot_fill; c.alignment = Alignment(horizontal='center')

ws.freeze_panes = ws.cell(row=hrow + 1, column=3)
ws.column_dimensions['A'].width = 10
ws.column_dimensions['B'].width = 38
for k in range(len(cols_stores)):
    ws.column_dimensions[get_column_letter(3 + k)].width = 14
ws.column_dimensions[get_column_letter(ncol)].width = 9
ws.row_dimensions[hrow].height = 42

# thin borders on the whole table so it prints as a clean grid
for row in ws.iter_rows(min_row=hrow, max_row=ws.max_row, min_col=1, max_col=ncol):
    for c in row:
        c.border = border

# ---- print setup: A4, landscape, fit to one page wide, repeat header each page ----
ws.page_setup.orientation = 'landscape'
ws.page_setup.paperSize = ws.PAPERSIZE_A4            # A4
ws.sheet_properties.pageSetUpPr = PageSetupProperties(fitToPage=True)
ws.page_setup.fitToWidth = 1                          # squeeze all columns onto one page wide
ws.page_setup.fitToHeight = 0                         # as many pages tall as needed
ws.print_title_rows = f'{hrow}:{hrow}'               # repeat the column header on every printed page
ws.print_options.gridLines = True
ws.print_options.horizontalCentered = True
ws.page_margins.left = ws.page_margins.right = 0.3
ws.page_margins.top = ws.page_margins.bottom = 0.4
ws.page_margins.header = ws.page_margins.footer = 0.2
ws.oddFooter.center.text = "Pick sheet — &A — page &P of &N"

wb.save(OUT)
print('wrote', OUT)
print('day:', full_day_label, '| stores:', len(cols_stores), '| products (non-zero):', len(rows))
print('stores:', ', '.join(f"{c['id']} {c['name']}" for c in cols_stores))
