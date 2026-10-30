"""LOCAL MOCK of the PayPal sandbox endpoints we use. This is NOT PayPal.

Serves OAuth, Transaction Search (paged) and verify-webhook-signature on
loopback so the full HTTP code path of the client can be exercised offline.
Results from this mock must always be labelled 'MOCK' in reports.
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse
from typing import Any, Dict, List

from .synthetic import response_page

MOCK_TOKEN = "mock-token-not-a-secret"


def start_mock(details: List[Dict[str, Any]], *, valid_signature: str = "GOOD", fail_first: int = 0):
    state = {"calls": [], "fail_left": fail_first}

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):  # silence
            pass

        def _send(self, code, obj):
            raw = json.dumps(obj).encode()
            self.send_response(code); self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw)

        def do_POST(self):
            n = int(self.headers.get("Content-Length", 0)); body = self.rfile.read(n)
            state["calls"].append(("POST", self.path))
            if self.path == "/v1/oauth2/token":
                if not self.headers.get("Authorization", "").startswith("Basic "):
                    return self._send(401, {"error": "invalid_client"})
                return self._send(200, {"access_token": MOCK_TOKEN, "expires_in": 300, "token_type": "Bearer"})
            if self.path == "/v1/notifications/verify-webhook-signature":
                req = json.loads(body)
                ok = req.get("transmission_sig") == valid_signature
                return self._send(200, {"verification_status": "SUCCESS" if ok else "FAILURE"})
            self._send(404, {"name": "NOT_FOUND", "message": "mock"})

        def do_GET(self):
            u = urlparse(self.path); state["calls"].append(("GET", u.path))
            if self.headers.get("Authorization") != f"Bearer {MOCK_TOKEN}":
                return self._send(401, {"name": "AUTHENTICATION_FAILURE", "message": "bad token"})
            if u.path == "/v1/reporting/transactions":
                if state["fail_left"] > 0:
                    state["fail_left"] -= 1
                    return self._send(503, {"name": "SERVICE_UNAVAILABLE", "message": "mock outage"})
                q = parse_qs(u.query)
                return self._send(200, response_page(details, int(q.get("page", ["1"])[0]),
                                                     int(q.get("page_size", ["100"])[0])))
            self._send(404, {"name": "NOT_FOUND", "message": "mock"})

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_port}", state
