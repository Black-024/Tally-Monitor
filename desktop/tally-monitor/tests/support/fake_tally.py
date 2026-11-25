"""Servidor local que imita lo mínimo de Tally. Valida la lógica del cliente, NO el comportamiento real de Tally."""
import json
import threading
from urllib.parse import parse_qs, urlparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class FakeTally:
    def __init__(self):
        self.users: dict[str, str | None] = {}   # api key -> id de usuario (None: la respuesta no trae id)
        self.queue: list[tuple[int, dict]] = []  # respuestas forzadas (status, cabeceras), en orden
        self.requests: list[dict] = []
        self.forms: dict[str, dict] = {}         # form_id -> {"summary","detail","questions","submissions"(más nuevo primero)}
        self.rate_headers: dict[str, str] = {}
        outer = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):  # silencio
                pass

            def _handle(self):
                outer.requests.append({"method": self.command, "path": self.path,
                                       "headers": {k.lower(): v for k, v in self.headers.items()}})
                if self.command != "GET":
                    return self._send(405, {}, b"{}")
                ua = self.headers.get("User-Agent", "")
                if ua.startswith("Python-urllib"):
                    return self._send(403, {}, b'{"message":"blocked"}')
                if outer.queue:
                    status, headers = outer.queue.pop(0)
                    return self._send(status, headers, b'{"message":"forced"}')
                auth = self.headers.get("Authorization", "")
                key = auth[7:] if auth.startswith("Bearer ") else ""
                u = urlparse(self.path)
                if key in outer.users and u.path == "/forms":
                    return self._forms_list(parse_qs(u.query))
                if key in outer.users and u.path.startswith("/forms/"):
                    return self._form_route(u.path.split("/")[2:], parse_qs(u.query))
                if self.path == "/users/me" and key in outer.users:
                    uid = outer.users[key]
                    body = {"email": "persona@example.com", "firstName": "Ana"}
                    if uid is not None:
                        body["id"] = uid
                    return self._send(200, {}, json.dumps(body).encode())
                return self._send(401, {}, b'{"message":"Unauthorized"}')

            def _json(self, obj):
                self._send(200, dict(outer.rate_headers), json.dumps(obj).encode())

            def _forms_list(self, q):
                items = [f["summary"] for f in outer.forms.values()]
                self._json({"page": 1, "limit": 50, "total": len(items), "hasMore": False, "items": items})

            def _form_route(self, parts, q):
                f = outer.forms.get(parts[0])
                if f is None:
                    return self._send(404, {}, b'{"message":"not found"}')
                if len(parts) == 1:
                    return self._json(f["detail"])
                if parts[1] == "questions":
                    return self._json(f["questions"])
                if parts[1] == "submissions":
                    subs = list(f["submissions"])
                    start = (q.get("startDate") or [None])[0]
                    if start:
                        subs = [s for s in subs if s["submittedAt"] >= start]       # inclusivo, como Tally
                    flt = (q.get("filter") or ["all"])[0]
                    if flt == "completed":
                        subs = [s for s in subs if s["isCompleted"]]
                    limit = int((q.get("limit") or ["50"])[0])
                    page = int((q.get("page") or ["1"])[0])
                    if limit > 500:
                        return self._send(400, {}, b'{"message":"limit"}')
                    chunk = subs[(page - 1) * limit: page * limit]
                    allsubs = f["submissions"]
                    return self._json({"page": page, "limit": limit, "hasMore": page * limit < len(subs),
                                       "totalNumberOfSubmissionsPerFilter": {
                                           "all": len(allsubs),
                                           "completed": sum(1 for s in allsubs if s["isCompleted"]),
                                           "partial": sum(1 for s in allsubs if not s["isCompleted"])},
                                       "questions": f["questions"]["questions"], "submissions": chunk})
                self._send(404, {}, b"{}")

            def _send(self, status, headers, body):
                self.send_response(status)
                for k, v in headers.items():
                    self.send_header(k, v)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            do_GET = do_POST = do_PUT = do_DELETE = do_PATCH = _handle

        self._srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self._srv.server_address[1]}"
        self._t = threading.Thread(target=self._srv.serve_forever, daemon=True)

    def start(self):
        self._t.start()
        return self

    def stop(self):
        self._srv.shutdown()
        self._srv.server_close()
