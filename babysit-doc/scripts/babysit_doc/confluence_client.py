import base64, json, urllib.parse, urllib.request, urllib.error


class ClientError(Exception):
    pass


class AuthError(ClientError):
    pass


class ApiError(ClientError):
    def __init__(self, status, msg):
        super().__init__(f"HTTP {status}: {msg}")
        self.status = status


class ConfluenceClient:
    def __init__(self, cfg, opener=urllib.request.urlopen):
        self._base = cfg.base_url
        self.base_url = cfg.base_url
        self._opener = opener
        token = base64.b64encode(f"{cfg.email}:{cfg.token}".encode()).decode()
        self._auth = f"Basic {token}"

    def _send(self, method, path, params=None, body=None):
        url = self._base + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Authorization", self._auth)
        req.add_header("Accept", "application/json")
        if data is not None:
            req.add_header("Content-Type", "application/json")
        try:
            resp = self._opener(req, timeout=30)
            raw = resp.read()
            return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                raise AuthError("Confluence rejected the credentials (check email/token/permissions)")
            raise ApiError(e.code, e.reason)

    def get(self, path, params=None):
        return self._send("GET", path, params=params)

    def post(self, path, body):
        return self._send("POST", path, body=body)
