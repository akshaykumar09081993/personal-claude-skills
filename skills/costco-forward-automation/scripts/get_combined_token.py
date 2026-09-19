#!/usr/bin/env python3
"""One-time: get a refresh token with gmail.modify + drive.file for the Costco Cloud Function."""
import json, os, sys, urllib.parse, urllib.request, webbrowser, http.server, threading, hashlib, base64, secrets

KEYS = json.load(open(os.path.expanduser('~/.gmail-mcp/gcp-oauth.keys.json')))['installed']
PORT = 8971
REDIRECT = f'http://localhost:{PORT}/'
SCOPES = 'https://www.googleapis.com/auth/gmail.modify https://www.googleapis.com/auth/drive.file'

verifier = base64.urlsafe_b64encode(secrets.token_bytes(40)).rstrip(b'=').decode()
challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()

auth_url = KEYS['auth_uri'] + '?' + urllib.parse.urlencode({
    'client_id': KEYS['client_id'], 'redirect_uri': REDIRECT, 'response_type': 'code',
    'scope': SCOPES, 'access_type': 'offline', 'prompt': 'consent',
    'code_challenge': challenge, 'code_challenge_method': 'S256'})

code_box = {}
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        q = urllib.parse.urlparse(self.path).query
        code_box.update(urllib.parse.parse_qs(q))
        self.send_response(200); self.send_header('Content-Type','text/html'); self.end_headers()
        self.wfile.write(b"<h2>Done. You can close this tab and return to the chat.</h2>")
    def log_message(self, *a): pass

srv = http.server.HTTPServer(('localhost', PORT), H)
print("Opening browser for Google consent (Gmail + Drive)...")
webbrowser.open(auth_url)
print("If it doesn't open, visit:\n" + auth_url)
srv.handle_request()  # wait for one redirect

code = code_box.get('code', [None])[0]
if not code:
    print("ERROR: no authorization code received", code_box); sys.exit(1)
data = urllib.parse.urlencode({
    'client_id': KEYS['client_id'], 'client_secret': KEYS['client_secret'],
    'code': code, 'code_verifier': verifier, 'grant_type': 'authorization_code',
    'redirect_uri': REDIRECT}).encode()
tok = json.load(urllib.request.urlopen(urllib.request.Request(KEYS['token_uri'], data=data)))
if 'refresh_token' not in tok:
    print("ERROR: no refresh_token returned:", {k:('...' if k in('access_token','id_token') else v) for k,v in tok.items()}); sys.exit(1)
out = os.path.expanduser('~/.gmail-mcp/automation-token.json')
json.dump({'client_id': KEYS['client_id'], 'client_secret': KEYS['client_secret'],
           'refresh_token': tok['refresh_token'], 'token_uri': KEYS['token_uri'],
           'scope': SCOPES}, open(out,'w'))
os.chmod(out, 0o600)
print("SUCCESS: saved refresh token to", out)
