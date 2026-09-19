import json, base64, urllib.parse, urllib.request, re, os

t = json.load(open(os.path.expanduser('~/.gmail-mcp/automation-token.json')))
def access():
    d = urllib.parse.urlencode({'client_id': t['client_id'], 'client_secret': t['client_secret'],
                                'refresh_token': t['refresh_token'], 'grant_type': 'refresh_token'}).encode()
    return json.load(urllib.request.urlopen(urllib.request.Request(t['token_uri'], data=d)))['access_token']
import time
AT = access()
G = "https://gmail.googleapis.com/gmail/v1/users/me"
D = "https://www.googleapis.com/drive/v3"
UP = "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&fields=id,name,webViewLink"
def req(url, method="GET", data=None, h=None):
    global AT
    for attempt in range(4):
        hh = {"Authorization": "Bearer " + AT}
        if h: hh.update(h)
        try:
            return json.load(urllib.request.urlopen(urllib.request.Request(url, data=data, headers=hh, method=method)))
        except urllib.error.HTTPError as e:
            if e.code in (401, 403, 429) and attempt < 3:
                time.sleep(2 * (attempt + 1)); AT = access(); continue
            raise

# folder + link
fq = urllib.parse.quote("name='costco' and mimeType='application/vnd.google-apps.folder' and trashed=false")
fs = req(D + "/files?q=" + fq + "&fields=files(id,webViewLink)").get("files", [])
fid = fs[0]["id"]; flink = fs[0].get("webViewLink")

# existing names
existing = set(); tok = None
pq = urllib.parse.quote("'" + fid + "' in parents and trashed=false")
while True:
    u = D + "/files?q=" + pq + "&fields=nextPageToken,files(name)&pageSize=1000" + (("&pageToken=" + tok) if tok else "")
    r = req(u); existing.update(f["name"] for f in r.get("files", [])); tok = r.get("nextPageToken")
    if not tok: break

# narrow to brett's emails with 'costco' in the subject
q = urllib.parse.quote('from:brett.mcinnis@grupobimbo.com subject:costco')
ids = []; tok = None
while True:
    u = G + "/messages?q=" + q + "&maxResults=100" + (("&pageToken=" + tok) if tok else "")
    r = req(u); ids += [m["id"] for m in r.get("messages", [])]; tok = r.get("nextPageToken")
    if not tok: break
print("brett emails with 'costco' in subject:", len(ids))

date_re = re.compile(r"(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})")
saved = []; skipped = 0; matched = 0
for mid in ids:
    meta = req(G + "/messages/" + mid + "?format=metadata&metadataHeaders=Subject")
    subj = ""
    for h in meta["payload"].get("headers", []):
        if h["name"] == "Subject": subj = h["value"]
    if "costco #'s" not in subj.lower():
        continue
    matched += 1
    full = req(G + "/messages/" + mid + "?format=full")
    m = date_re.search(subj)
    if not m:
        print("  (no date in subject, skipped):", repr(subj)); continue
    mm, dd, yy = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if yy < 100: yy += 2000
    datestr = "%04d-%02d-%02d" % (yy, mm, dd)
    stack = [full["payload"]]
    while stack:
        p = stack.pop(); stack.extend(p.get("parts", []))
        fn = p.get("filename"); b = p.get("body", {})
        if fn and b.get("attachmentId") and fn.lower().endswith((".xlsx", ".xls", ".csv")):
            ext = os.path.splitext(fn)[1]
            name = "Costco_Nums_" + datestr + ext
            if name in existing:
                skipped += 1; continue
            data = req(G + "/messages/" + mid + "/attachments/" + b["attachmentId"])
            content = base64.urlsafe_b64decode(data["data"])
            boundary = "==b=="
            meta = json.dumps({"name": name, "parents": [fid]}).encode()
            body = (b"--" + boundary.encode() + b"\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n" + meta +
                    b"\r\n--" + boundary.encode() + b"\r\nContent-Type: " + p.get("mimeType", "application/octet-stream").encode() +
                    b"\r\n\r\n" + content + b"\r\n--" + boundary.encode() + b"--")
            req(UP, "POST", body, {"Content-Type": "multipart/related; boundary=" + boundary})
            existing.add(name); saved.append((datestr, name, len(content), fn))

print("\nmatched 'costco #'s' emails:", matched)
print("=== SAVED %d new file(s), skipped %d already present ===" % (len(saved), skipped))
for d, n, sz, orig in sorted(saved):
    print("  %s   <-  %s  (%d bytes)" % (n, orig, sz))
print("\nFOLDER LINK: " + (flink or ("https://drive.google.com/drive/folders/" + fid)))
