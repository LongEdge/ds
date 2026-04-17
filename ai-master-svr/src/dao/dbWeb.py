import requests
import subprocess
from functools import wraps
from flask import request, Response
from src.utils.SysLogger import CSysLogger

logger = CSysLogger('dbWeb')
USERNAME = "<REDACTED_USERNAME>"
PASSWORD = "<REDACTED_PASSWORD>"


def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return Response(
                'Authentication required', 401,
                {'WWW-Authenticate': 'Basic realm="Login Required"'}
            )
        return f(*args, **kwargs)
    return decorated


def check_auth(username, password):
    return username == USERNAME and password == PASSWORD


class CDb:
    def __init__(self, app, sqlite_port):
        self.app = app
        self.sqlite_port = sqlite_port
        self.start_sqlite_web()
        self.init_db_web()

    def start_sqlite_web(self):
        subprocess.Popen([
            "sqlite_web",
            "test.db",
            "--host", "127.0.0.1",
            "--port", "{}".format(self.sqlite_port),
            "--url-prefix", "/sqlite"
        ])
        logger.info("sqlite_web started at 127.0.0.1:{}".format(self.sqlite_port))

    def init_db_web(self):
        @self.app.route("/sqlite/", defaults={"path": ""}, methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
        @self.app.route("/sqlite/<path:path>", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
        @require_auth
        def proxy(path):
            SQLITE_WEB = f"http://127.0.0.1:{self.sqlite_port}"
            if path.startswith("api"):
                return "your api"

            normalized_path = "/".join(filter(None, path.split("/")))
            url = f"{SQLITE_WEB}/sqlite/{normalized_path}/" if normalized_path else f"{SQLITE_WEB}/sqlite/"

            headers = {k: v for k, v in request.headers if k.lower() != "host"}
            data = request.get_data()
            params = request.args

            try:
                resp = requests.request(
                    method=request.method,
                    url=url,
                    headers=headers,
                    params=params,
                    data=data,
                    cookies=request.cookies,
                    allow_redirects=False,
                    timeout=10
                )
            except requests.RequestException as e:
                return f"Error connecting to sqlite_web: {e}", 500

            excluded = ["content-encoding", "content-length", "transfer-encoding", "connection"]
            response_headers = []

            for k, v in resp.headers.items():
                if k.lower() in excluded:
                    continue
                if k.lower() == "location" and v.startswith("/") and not v.startswith("/sqlite"):
                    v = f"/sqlite{v}"
                response_headers.append((k, v))

            return Response(resp.content, resp.status_code, response_headers)
