"""Costco daily forward + Drive archive — Cloud Function (Gen2, HTTP).

Runs on a Cloud Scheduler daily trigger. Uses a user OAuth refresh token
(gmail.modify + drive.file) stored in Secret Manager and mounted as TOKEN_JSON.
Finds the Costco sales email, forwards it, saves attachments to Drive/<folder>,
and labels it so it is never processed twice.
"""
import os, json, base64, urllib.parse, urllib.request, email, email.policy, email.utils, datetime

FORWARD_TO   = os.environ.get("FORWARD_TO", "tlaceycanadabread@hotmail.com")
SUBJECT_HINT = os.environ.get("SUBJECT_HINT", "Costco Last 7 Days Sales - CANADA BREAD")
DRIVE_FOLDER = os.environ.get("DRIVE_FOLDER", "costco")
LABEL_NAME   = os.environ.get("LABEL_NAME", "costco-forwarded")
TOKEN        = json.loads(os.environ["TOKEN_JSON"])

GMAIL = "https://gmail.googleapis.com/gmail/v1/users/me"
DRIVE = "https://www.googleapis.com/drive/v3"
UPLOAD = "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&fields=id,name"


def _access_token():
    data = urllib.parse.urlencode({
        "client_id": TOKEN["client_id"], "client_secret": TOKEN["client_secret"],
        "refresh_token": TOKEN["refresh_token"], "grant_type": "refresh_token"}).encode()
    r = urllib.request.urlopen(urllib.request.Request(TOKEN["token_uri"], data=data))
    return json.load(r)["access_token"]


def _req(url, at, method="GET", data=None, headers=None, raw=False):
    h = {"Authorization": "Bearer " + at}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    resp = urllib.request.urlopen(req)
    return resp.read() if raw else json.load(resp)


def _get_label_id(at):
    labels = _req(f"{GMAIL}/labels", at).get("labels", [])
    for l in labels:
        if l["name"] == LABEL_NAME:
            return l["id"]
    body = json.dumps({"name": LABEL_NAME, "labelListVisibility": "labelShow",
                       "messageListVisibility": "show"}).encode()
    return _req(f"{GMAIL}/labels", at, "POST", body, {"Content-Type": "application/json"})["id"]


def _folder_id(at):
    q = urllib.parse.quote(f"name='{DRIVE_FOLDER}' and "
                           "mimeType='application/vnd.google-apps.folder' and trashed=false")
    files = _req(f"{DRIVE}/files?q={q}&fields=files(id,name)", at).get("files", [])
    if files:
        return files[0]["id"]
    body = json.dumps({"name": DRIVE_FOLDER,
                       "mimeType": "application/vnd.google-apps.folder"}).encode()
    return _req(f"{DRIVE}/files?fields=id", at, "POST", body,
                {"Content-Type": "application/json"})["id"]


def _my_email(at):
    return _req(f"{GMAIL}/profile", at)["emailAddress"]


def _forward(at, msg_id, me, datestr):
    raw_b64 = _req(f"{GMAIL}/messages/{msg_id}?format=raw", at)["raw"]
    raw = base64.urlsafe_b64decode(raw_b64)
    m = email.message_from_bytes(raw, policy=email.policy.default)
    subj = m["Subject"] or SUBJECT_HINT
    for hdr in ["To", "Cc", "Bcc", "From", "Subject", "Message-ID", "Message-Id",
                "Return-Path", "Delivered-To", "Reply-To", "DKIM-Signature",
                "ARC-Seal", "ARC-Message-Signature", "ARC-Authentication-Results"]:
        while hdr in m:
            del m[hdr]
    m["From"] = me
    m["To"] = FORWARD_TO
    m["Subject"] = "Fwd: " + subj + " - " + datestr
    out = base64.urlsafe_b64encode(m.as_bytes()).decode()
    _req(f"{GMAIL}/messages/send", at, "POST",
         json.dumps({"raw": out}).encode(), {"Content-Type": "application/json"})


def _save_attachments(at, msg, folder_id, datestr):
    saved = []
    def walk(part):
        for p in part.get("parts", []):
            walk(p)
        fn = part.get("filename")
        body = part.get("body", {})
        if fn and body.get("attachmentId"):
            data = _req(f"{GMAIL}/messages/{msg['id']}/attachments/{body['attachmentId']}", at)
            content = base64.urlsafe_b64decode(data["data"])
            name = f"Costco_Sales_{datestr}_{fn.replace(' ', '_')}"
            _drive_upload(at, folder_id, name,
                          part.get("mimeType", "application/octet-stream"), content)
            saved.append(name)
    walk(msg["payload"])
    return saved


def _drive_upload(at, folder_id, name, mime, content):
    boundary = "==costcoboundary=="
    meta = json.dumps({"name": name, "parents": [folder_id]}).encode()
    body = (b"--" + boundary.encode() + b"\r\n"
            b"Content-Type: application/json; charset=UTF-8\r\n\r\n" + meta + b"\r\n"
            b"--" + boundary.encode() + b"\r\n"
            b"Content-Type: " + mime.encode() + b"\r\n\r\n" + content + b"\r\n"
            b"--" + boundary.encode() + b"--")
    _req(UPLOAD, at, "POST", body,
         {"Content-Type": f"multipart/related; boundary={boundary}"})


def costco(request):
    at = _access_token()
    me = _my_email(at)
    label_id = _get_label_id(at)
    folder_id = _folder_id(at)
    q = (f'from:noreply@costco.com subject:("{SUBJECT_HINT}") '
         f'newer_than:2d -label:{LABEL_NAME}')
    res = _req(f"{GMAIL}/messages?q={urllib.parse.quote(q)}&maxResults=25", at)
    ids = [m["id"] for m in res.get("messages", [])]
    processed = []
    for mid in ids:
        full = _req(f"{GMAIL}/messages/{mid}?format=full", at)
        subj, date_hdr = "", ""
        for h in full["payload"].get("headers", []):
            if h["name"] == "Subject":
                subj = h["value"]
            elif h["name"] == "Date":
                date_hdr = h["value"]
        if SUBJECT_HINT not in subj:
            continue
        # date the report is FOR = the email's own Date header (fallback: received time)
        try:
            dt = email.utils.parsedate_to_datetime(date_hdr)
        except Exception:
            dt = datetime.datetime.utcfromtimestamp(int(full["internalDate"]) / 1000)
        datestr = dt.strftime("%Y-%m-%d")
        _forward(at, mid, me, datestr)
        _save_attachments(at, full, folder_id, datestr)
        _req(f"{GMAIL}/messages/{mid}/modify", at, "POST",
             json.dumps({"addLabelIds": [label_id]}).encode(),
             {"Content-Type": "application/json"})
        processed.append(mid)
    msg = f"Processed {len(processed)} Costco message(s): {processed}"
    print(msg)
    return (msg, 200)
