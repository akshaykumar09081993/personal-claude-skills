import json, base64, urllib.parse, urllib.request, email.utils, datetime, os

t = json.load(open(os.path.expanduser('~/.gmail-mcp/automation-token.json')))

def access():
    d = urllib.parse.urlencode({'client_id': t['client_id'], 'client_secret': t['client_secret'],
                                'refresh_token': t['refresh_token'], 'grant_type': 'refresh_token'}).encode()
    return json.load(urllib.request.urlopen(urllib.request.Request(t['token_uri'], data=d)))['access_token']

AT = access()
G = "https://gmail.googleapis.com/gmail/v1/users/me"
D = "https://www.googleapis.com/drive/v3"
UP = "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&fields=id,name,webViewLink"

def req(url, method="GET", data=None, h=None):
    hh = {"Authorization": "Bearer " + AT}
    if h: hh.update(h)
    return json.load(urllib.request.urlopen(urllib.request.Request(url, data=data, headers=hh, method=method)))

# ensure folder + link
fq = urllib.parse.quote("name='costco' and mimeType='application/vnd.google-apps.folder' and trashed=false")
fs = req(D + "/files?q=" + fq + "&fields=files(id,name,webViewLink)").get("files", [])
if fs:
    fid = fs[0]["id"]; flink = fs[0].get("webViewLink")
else:
    r = req(D + "/files?fields=id,webViewLink", "POST",
            json.dumps({"name": "costco", "mimeType": "application/vnd.google-apps.folder"}).encode(),
            {"Content-Type": "application/json"})
    fid = r["id"]; flink = r.get("webViewLink")

# existing names to skip dups
existing = set(); tok = None
pq = urllib.parse.quote("'" + fid + "' in parents and trashed=false")
while True:
    u = D + "/files?q=" + pq + "&fields=nextPageToken,files(name)&pageSize=1000" + (("&pageToken=" + tok) if tok else "")
    r = req(u); existing.update(f["name"] for f in r.get("files", [])); tok = r.get("nextPageToken")
    if not tok: break
print("existing files in folder:", len(existing))

# all Costco sales emails (full history)
q = urllib.parse.quote('from:noreply@costco.com subject:"Costco Last 7 Days Sales"')
ids = []; tok = None
while True:
    u = G + "/messages?q=" + q + "&maxResults=100" + (("&pageToken=" + tok) if tok else "")
    r = req(u); ids += [m["id"] for m in r.get("messages", [])]; tok = r.get("nextPageToken")
    if not tok: break
print("Costco emails found:", len(ids))

saved = []; skipped = 0
for mid in ids:
    full = req(G + "/messages/" + mid + "?format=full")
    hdrs = {h['name']: h['value'] for h in full['payload'].get('headers', [])}
    try:
        dt = email.utils.parsedate_to_datetime(hdrs.get('Date', ''))
    except Exception:
        dt = datetime.datetime.utcfromtimestamp(int(full['internalDate']) / 1000)
    datestr = dt.strftime('%Y-%m-%d')
    stack = [full['payload']]
    while stack:
        p = stack.pop()
        stack.extend(p.get('parts', []))
        fn = p.get('filename'); b = p.get('body', {})
        if fn and b.get('attachmentId') and fn.lower().endswith(('.xlsx', '.xls', '.csv')):
            name = "Costco_Sales_" + datestr + "_" + fn.replace(' ', '_')
            if name in existing:
                skipped += 1; continue
            data = req(G + "/messages/" + mid + "/attachments/" + b['attachmentId'])
            content = base64.urlsafe_b64decode(data['data'])
            boundary = "==b=="
            meta = json.dumps({"name": name, "parents": [fid]}).encode()
            body = (b"--" + boundary.encode() + b"\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n" + meta +
                    b"\r\n--" + boundary.encode() + b"\r\nContent-Type: " + p.get("mimeType", "application/octet-stream").encode() +
                    b"\r\n\r\n" + content + b"\r\n--" + boundary.encode() + b"--")
            req(UP, "POST", body, {"Content-Type": "multipart/related; boundary=" + boundary})
            existing.add(name); saved.append((datestr, name, len(content)))

print("\n=== SAVED %d new file(s), skipped %d already present ===" % (len(saved), skipped))
for d, n, sz in sorted(saved):
    print("  %s  (%d bytes)" % (n, sz))
print("\nFOLDER LINK: " + (flink or ("https://drive.google.com/drive/folders/" + fid)))
