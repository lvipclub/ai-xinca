#!/usr/bin/env python3
"""One-shot OAuth callback server for Shopify custom app installation.
Captures the authorization code and exchanges it for a permanent access token.

Usage: Run this, then open the install URL in browser.
Token saved to: /home/hermerr/workspace/ai-xinca/.env.shopify
"""
import http.server
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

# ---------- CONFIG ----------
CLIENT_ID = os.environ.get("SHOPIFY_CLIENT_ID", "91e089829842ddff8af412f2320df2df")
CLIENT_SECRET = os.environ.get("SHOPIFY_CLIENT_SECRET", "your-secret-here")
SHOP = "shop.xinca.com"
PORT = 9877
CALLBACK_PATH = "/callback"
ENV_FILE = Path("/home/hermerr/workspace/ai-xinca/.env.shopify")

# ---------- INSTALL URL ----------
SCOPES = "unauthenticated_read_product_listings,unauthenticated_read_product_tags"
REDIRECT_URI = f"http://localhost:{PORT}{CALLBACK_PATH}"

INSTALL_URL = (
    f"https://{SHOP}/admin/oauth/authorize"
    f"?client_id={CLIENT_ID}"
    f"&scope={SCOPES}"
    f"&redirect_uri={urllib.parse.quote(REDIRECT_URI, safe='')}"
)

# ---------- CALLBACK HANDLER ----------
class OAuthHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        
        if parsed.path == CALLBACK_PATH:
            query = urllib.parse.parse_qs(parsed.query)
            code = query.get("code", [None])[0]
            shop_param = query.get("shop", [None])[0]
            
            if not code:
                self._respond(400, "ERROR: No authorization code received.")
                return
            
            # Exchange code for permanent access token
            token = self._exchange_code(code, shop_param)
            
            if token:
                self._save_token(token)
                self._respond(200, f"✅ SUCCESS! Token saved to {ENV_FILE}\n\nYou can close this window.")
                print(f"\n✅ Token saved to {ENV_FILE}")
                print(f"   Access token: {token[:20]}...{token[-10:]}")
            else:
                self._respond(500, "ERROR: Failed to exchange code for token.")
        else:
            self._respond(404, "Unknown path. Go to the install URL.")
    
    def _exchange_code(self, code: str, shop_param: str | None) -> str | None:
        """POST to /admin/oauth/access_token to exchange code for permanent token."""
        shop = shop_param or SHOP
        data = urllib.parse.urlencode({
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "code": code,
            "redirect_uri": REDIRECT_URI,  # REQUIRED — must match authorization request exactly
        }).encode()
        
        url = f"https://{shop}/admin/oauth/access_token"
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                body = json.loads(resp.read())
                return body.get("access_token")
        except Exception as e:
            print(f"\n❌ Token exchange failed: {e}")
            try:
                print(f"   Response body: {e.read()}")
            except Exception:
                pass
            return None
    
    def _save_token(self, token: str):
        ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
        # Don't overwrite existing unless this is newer
        content = (
            f"# Shopify Admin API access token for ai-xinca-carousel\n"
            f"# Generated: {__import__('datetime').datetime.now().isoformat()}\n"
            f"SHOPIFY_STORE={SHOP}\n"
            f"SHOPIFY_ACCESS_TOKEN={token}\n"
        )
        ENV_FILE.write_text(content)
        ENV_FILE.chmod(0o600)
    
    def _respond(self, status: int, message: str):
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(message.encode())
    
    def log_message(self, format, *args):
        print(f"  [server] {args[0]}")


if __name__ == "__main__":
    print("=" * 60)
    print("  Shopify OAuth Callback Server")
    print("=" * 60)
    print(f"\n  1. Make sure redirect URL is configured:")
    print(f"     {REDIRECT_URI}")
    print()
    print(f"  2. OPEN THIS URL IN YOUR BROWSER:")
    print(f"     \033[1;36m{INSTALL_URL}\033[0m")
    print()
    print(f"  3. Click 'Install' to authorize the app")
    print(f"  4. The token will be captured automatically")
    print()
    print(f"  Listening on http://localhost:{PORT}{CALLBACK_PATH} ...")
    print()
    
    server = http.server.HTTPServer(("localhost", PORT), OAuthHandler)
    try:
        server.handle_request()  # Serve ONE request then exit
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    
    if ENV_FILE.exists():
        print(f"\nDone. Token saved. Run: source {ENV_FILE}")
    else:
        print("\n❌ No token captured. Did the OAuth flow complete?")
        sys.exit(1)
