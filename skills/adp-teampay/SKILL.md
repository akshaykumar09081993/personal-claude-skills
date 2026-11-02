---
name: adp-teampay
description: >-
  Log into the ADP "TeamPay" payroll admin portal (online.adp.com/signin → teampay.adp.com,
  APPID=TeamPAY) and download employee pay statements (paystubs) and payroll reports
  (Payroll Register, Journal Entry, Totals, ROE, Employee Status, etc.) as PDFs. Use whenever
  the user asks to pull/download their ADP paystubs, payroll reports, T4-related registers, or
  "get me <employee>'s paystubs / the October payroll reports". CRITICAL: ADP's login actively
  blocks automated/headless browsers (returns a bogus "user ID and/or password are incorrect"
  even when the password is right), so you MUST drive the user's REAL Chrome over its DevTools
  (CDP) port — never a fresh Playwright/Chromium browser. macOS; Playwright + the user's Chrome.
---

# ADP TeamPay — download paystubs & payroll reports

## Why this skill exists (the hard-won lesson)
ADP's sign-in page (`online.adp.com/signin`) **fingerprints the browser and rejects automation**.
A fresh Playwright/Chromium browser gets the *correct* password rejected with a generic
*"Your user ID and/or password are incorrect"* — and a brand-new device also triggers MFA.
Do **NOT** keep retrying (ADP locks the account after a few failed attempts).

**The fix that works:** connect Playwright over CDP to the user's **real Chrome** (real
fingerprint, no `navigator.webdriver`). The login then goes through normally.

## Prerequisites
- **Playwright** at `/Users/avu/Documents/Claude/node_modules` → run node with
  `NODE_PATH=/Users/avu/Documents/Claude/node_modules`.
- The user's **Chrome** with the ADP-logged-in profile. Find which profile:
  `Local State` → `profile.info_cache` (e.g. "Business" = `Profile 1`).
- **Credentials at runtime only** (this repo is public — NEVER commit them): env
  `ADP_USER`, `ADP_PASS`. ADP User IDs look like `user@ClientID`; the password is case-sensitive.

## Flow
1. **Launch CDP Chrome** (separate instance from the user's normal Chrome; needs a *non-default*
   user-data-dir, so copy the profile):
   ```bash
   scripts/cdp-chrome.sh "Profile 1"      # quits nothing of yours; copies profile to /tmp and launches on :9222
   ```
2. **Log in + navigate + download** over CDP:
   ```bash
   NODE_PATH=/Users/avu/Documents/Claude/node_modules \
     ADP_USER='user@CLIENTID' ADP_PASS='secret' node scripts/adp-cdp.js paystubs "SUKHDEV"   # employee paystubs
   NODE_PATH=/Users/avu/Documents/Claude/node_modules node scripts/adp-cdp.js reports 2026-01-01 2026-10-31  # payroll reports in a date range
   ```
3. **Clean up** (the /tmp copy holds the session cookie):
   ```bash
   pkill -f "user-data-dir=/tmp/adp-chrome-profile"; rm -rf /tmp/adp-chrome-profile
   ```

## Key portal facts (dijit/dojo EnhancedGrids)
- After login you land on `teampay.adp.com/Payroll/Admin/Main/Default.aspx`.
- The sign-in form uses **web components** (`sdf-input`): the real field is `#login-form_username input`
  / `#login-form_password input`. Fill those, click `#verifUseridBtn` (Next) then `#signBtn` (Sign in).
  When the profile remembers the user it shows "Hello, <name>" and only asks for the password.
- **Employee paystubs:** Home → click the employee card → **Pay Statements** tab. Grid id prefix
  `MainContent_tabManageEmployee_emPractitionerPayStatements_payStatementDataGrid`. Each row's Pay-Date
  link = `…_row_{N}_cell_4_hyperlink`.
- **Payroll reports:** dashboard "View Reports" link → grid id prefix
  `MainContent_ucPayrollOutputReports_payrollDataGrid`. Report-type link = `…_row_{N}_cell_0_hyperlink`.
  Columns: 0=Report Type, 1=Sub-type/Payee, 2=Pay Date, 3=Period End, 4=Pay Period, 5=Function, 6=Produced On.
  Date filter inputs: `…_txtStartDate` / `…_txtEndDate` (dd/mm/yyyy); default window is only ~3 months —
  widen it to get a full year. "Function" = Calculate (pre-approval) vs **Approve** (final).
- **Downloading:** clicking any such hyperlink opens a NEW TAB at
  `teampay.adp.com/payroll/admin/Common/DownloadPages/Download.aspx?id=<GUID>` = the PDF (GUID is
  minted per click). Fetch the bytes with `ctx.request.get(url)` (shares the session), save, close the tab.
- **Pagination:** dijit grids use `…_first_link` / `…_next_link` (reset to first page before scanning;
  a fresh CDP connection may leave the grid on the last page). ~10–30 rows/page.
- `new URL(page.url()).hostname === 'teampay.adp.com'` to detect "logged in" — don't substring-match the
  signin URL (it contains `teampay.adp.com/Payroll` inside its `TARGET=` param → false positive).

## Related skills
- `wcb-calculator` — turn the downloaded Payroll Registers into a monthly WCB figure.
- `payroll-hours-reconciliation` — compare flat pay vs actual hours using the paystub figures.
