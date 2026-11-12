"""Shared helpers: settings, secrets, logging and HTTP. Standard library only."""

import http.client
import json
import logging
import os
import re
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
SETTINGS_FILE = HERE / "research.json"   # themes, budgets, model: edit freely
SECRETS_FILE = HERE / "config.json"      # Telegram token and OpenAlex key: made by setup, keep private
DATA_DIR = HERE / "data"
REPORTS_DIR = HERE / "reports"
LOGS_DIR = HERE / "logs"
USER_AGENT = "Phase0Researcher/1.0 (personal literature review)"

log = logging.getLogger("researcher")


class HTTPError(RuntimeError):
    """The server answered with an error code."""

    def __init__(self, code, detail):
        self.code = code
        self.detail = detail
        super().__init__(f"HTTP {code}: {detail[:300]}")


class Unreachable(RuntimeError):
    """No answer at all: server down, no internet, connection refused."""


class TimedOut(Unreachable):
    """The server took too long to answer."""


def make_ssl_context():
    """Trust the system certificates too. Python from python.org on a Mac otherwise can't verify websites."""
    context = ssl.create_default_context()
    for bundle in ("/etc/ssl/cert.pem", "/etc/ssl/certs/ca-certificates.crt"):
        if os.path.exists(bundle):
            try:
                context.load_verify_locations(bundle)
            except (OSError, ssl.SSLError):
                pass
            break
    return context


SSL_CONTEXT = make_ssl_context()


def http_request(url, data=None, headers=None, timeout=60, max_bytes=None):
    """Make one HTTP request. Returns (body bytes, content type, final url)."""
    request = urllib.request.Request(url, data=data, headers={"User-Agent": USER_AGENT, **(headers or {})})
    host = urllib.parse.urlsplit(url).netloc
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=SSL_CONTEXT) as response:
            if max_bytes:
                body = response.read(max_bytes + 1)
                if len(body) > max_bytes:
                    raise HTTPError(413, f"file larger than {max_bytes // 1_000_000} MB, skipped")
            else:
                body = response.read()
            return body, response.headers.get("Content-Type", ""), response.geturl()
    except urllib.error.HTTPError as error:
        detail = error.read(4000).decode("utf-8", errors="replace")
        try:
            parsed = json.loads(detail)
            if isinstance(parsed, dict):
                pieces = [parsed.get(key) for key in ("description", "error", "message")]
                pieces = [piece if isinstance(piece, str) else json.dumps(piece) for piece in pieces if piece]
                detail = ": ".join(pieces) or detail
        except ValueError:
            pass
        raise HTTPError(error.code, detail) from None
    except TimeoutError:
        raise TimedOut(f"{host} did not answer within {timeout} seconds") from None
    except urllib.error.URLError as error:
        if isinstance(error.reason, TimeoutError):
            raise TimedOut(f"{host} did not answer within {timeout} seconds") from None
        raise Unreachable(f"cannot reach {host} ({error.reason})") from None
    except (http.client.HTTPException, OSError) as error:
        raise Unreachable(f"connection to {host} failed ({error})") from None


def get_json(url, headers=None, timeout=60):
    body, _, _ = http_request(url, headers=headers, timeout=timeout)
    return json.loads(body.decode("utf-8"))


def post_json(url, payload, headers=None, timeout=60):
    data = json.dumps(payload).encode("utf-8")
    body, _, _ = http_request(url, data=data, headers={"Content-Type": "application/json", **(headers or {})},
                              timeout=timeout)
    return json.loads(body.decode("utf-8"))


def load_settings():
    """research.json: what to research and how hard. Missing keys fall back to sensible defaults."""
    if not SETTINGS_FILE.exists():
        sys.exit(f"{SETTINGS_FILE.name} is missing. It should sit next to researcher.py.")
    settings = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    for key in ("about", "themes", "llm", "budgets"):
        if key not in settings:
            sys.exit(f"{SETTINGS_FILE.name} needs a \"{key}\" section.")
    names = [theme["name"] for theme in settings["themes"]]
    if len(set(names)) != len(names):
        sys.exit("Every theme in research.json needs a different name.")
    settings.setdefault("language", "English")
    return settings


def load_secrets():
    if SECRETS_FILE.exists():
        return json.loads(SECRETS_FILE.read_text(encoding="utf-8"))
    return {}


def save_secrets(secrets):
    SECRETS_FILE.write_text(json.dumps(secrets, indent=2) + "\n", encoding="utf-8")
    try:
        os.chmod(SECRETS_FILE, 0o600)  # tokens are secrets: only you can read this file
    except OSError:
        pass


def setup_logging(log_file=None):
    log.setLevel(logging.INFO)
    log.handlers.clear()
    formatter = logging.Formatter("%(asctime)s  %(message)s", "%Y-%m-%d %H:%M:%S")
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    log.addHandler(console)
    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        log.addHandler(file_handler)
    logging.getLogger("pypdf").setLevel(logging.ERROR)  # pypdf is chatty about odd PDFs


def tidy(text):
    """Swap long dashes for commas: Ilia prefers text without them."""
    for dash in (" — ", " – ", "—", " -- "):
        text = text.replace(dash, ", ")
    text = re.sub(r"(?<=[A-Za-z])[-‐‑](?=[A-Za-z])", " ", text)  # "short-lived" -> "short lived"; minus signs stay
    return text.strip()
