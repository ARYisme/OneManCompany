"""web_fetch — 安全的網頁讀取工具（ARY fork 自訂，talent-brought asset tool）。

Provides one LangChain @tool:
- web_fetch(url, max_chars=20000)

Backend order:
1. crawl4ai (POST {CRAWL4AI_BASE_URL}/md, returns markdown, renders JS) —
   only when a token is available (env CRAWL4AI_API_TOKEN or the file named by
   CRAWL4AI_API_TOKEN_FILE). The token is never logged or returned.
2. Fallback: a standard-library HTTP(S) GET fetcher with HTML→text extraction.

Safety (applies to BOTH backends; see docs/ary/web-tools.md):
- http/https only, ports 80/443 only, no userinfo in URL.
- Hostname must resolve ONLY to public (global) IPs. Private, loopback,
  link-local, CGNAT/Tailscale (100.64.0.0/10), Tailscale IPv6 (fd7a:115c:a1e0::/48),
  ULA, multicast and reserved ranges are refused, as are single-label,
  .local/.lan/.internal/.home.arpa/.ts.net hostnames.
- The stdlib fetcher connects to the already-validated IP (no DNS rebinding
  between check and connect) and re-validates every redirect hop (max 5).
- Before a URL is handed to crawl4ai, redirects are pre-resolved with the safe
  fetcher and the FINAL url is validated; crawl4ai itself is the only internal
  destination this tool ever contacts.
- No cookies, no credentials, no proxies, GET only, ~20 s timeout,
  2 MB body cap, text/HTML/JSON/XML content types only.

Only Python stdlib + langchain_core (already in the image).
"""

from __future__ import annotations

import html
import ipaddress
import json
import os
import re
import socket
import ssl
import http.client
import time
import zlib
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit, urlunsplit

try:  # langchain_core exists inside OMC; allow import for offline tests
    from langchain_core.tools import tool
except Exception:  # pragma: no cover
    def tool(fn):  # type: ignore
        return fn

try:
    from loguru import logger
except Exception:  # pragma: no cover
    import logging
    logger = logging.getLogger("web_fetch")

# ---------------------------------------------------------------------------
# Limits / config
# ---------------------------------------------------------------------------
USER_AGENT = (
    "Mozilla/5.0 (compatible; OMC-MarketResearcher/1.0; "
    "+https://github.com/ARYisme/OneManCompany) web_fetch"
)
TIMEOUT_SECONDS = float(os.environ.get("WEB_FETCH_TIMEOUT", "20"))
MAX_BODY_BYTES = 2 * 1024 * 1024          # 2 MB
MAX_REDIRECTS = 5
DEFAULT_MAX_CHARS = 20000
HARD_MAX_CHARS = 60000
ALLOWED_PORTS = {80, 443}
ALLOWED_CONTENT_TYPES = (
    "text/", "application/xhtml+xml", "application/json", "application/xml",
    "application/rss+xml", "application/atom+xml", "application/ld+json",
)
CRAWL4AI_BASE_URL = os.environ.get("CRAWL4AI_BASE_URL", "http://192.168.11.20:11235").rstrip("/")
CRAWL4AI_TIMEOUT = float(os.environ.get("CRAWL4AI_TIMEOUT", "25"))

_BLOCKED_SUFFIXES = (".local", ".lan", ".internal", ".intranet", ".home.arpa",
                     ".localdomain", ".ts.net", ".localhost", ".corp", ".home")
_EXTRA_BLOCKED_NETS = [
    ipaddress.ip_network("100.64.0.0/10"),       # CGNAT / Tailscale IPv4
    ipaddress.ip_network("fd7a:115c:a1e0::/48"),  # Tailscale IPv6
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("198.18.0.0/15"),
]


class FetchBlocked(Exception):
    """Raised when a URL or address is refused by the safety policy."""


# ---------------------------------------------------------------------------
# SSRF guard
# ---------------------------------------------------------------------------
def _ip_is_public(ip_str: str) -> bool:
    ip = ipaddress.ip_address(ip_str.split("%", 1)[0])
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    if not ip.is_global or ip.is_multicast or ip.is_reserved or ip.is_loopback \
            or ip.is_link_local or ip.is_private or ip.is_unspecified:
        return False
    return not any(ip in net for net in _EXTRA_BLOCKED_NETS if net.version == ip.version)


def validate_url(url: str) -> tuple[str, str, int, list[str]]:
    """Validate *url*; return (scheme, host, port, [public ips]). Raise FetchBlocked."""
    if not isinstance(url, str) or len(url) > 2048:
        raise FetchBlocked("URL missing or too long")
    parts = urlsplit(url.strip())
    scheme = (parts.scheme or "").lower()
    if scheme not in ("http", "https"):
        raise FetchBlocked(f"scheme '{scheme}' not allowed (http/https only)")
    if parts.username or parts.password or "@" in (parts.netloc or ""):
        raise FetchBlocked("credentials in URL are not allowed")
    host = (parts.hostname or "").rstrip(".").lower()
    if not host:
        raise FetchBlocked("URL has no hostname")
    try:
        port = parts.port or (443 if scheme == "https" else 80)
    except ValueError:
        raise FetchBlocked("invalid port")
    if port not in ALLOWED_PORTS:
        raise FetchBlocked(f"port {port} not allowed (80/443 only)")
    is_literal = True
    try:
        ipaddress.ip_address(host)
    except ValueError:
        is_literal = False
    if not is_literal:
        if "." not in host or host == "localhost" or host.endswith(_BLOCKED_SUFFIXES):
            raise FetchBlocked(f"hostname '{host}' looks internal")
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise FetchBlocked(f"DNS lookup failed for '{host}': {exc}")
    ips = sorted({i[4][0] for i in infos}, key=lambda x: (":" in x, x))  # IPv4 first
    if not ips:
        raise FetchBlocked(f"no address for '{host}'")
    bad = [ip for ip in ips if not _ip_is_public(ip)]
    if bad:
        raise FetchBlocked(f"'{host}' resolves to non-public address(es) {bad} — blocked")
    return scheme, host, port, ips


# ---------------------------------------------------------------------------
# Pinned-IP connections (no DNS rebinding between check and connect)
# ---------------------------------------------------------------------------
class _PinnedHTTPConnection(http.client.HTTPConnection):
    def __init__(self, host, port, ip, timeout):
        super().__init__(host, port, timeout=timeout)
        self._ip = ip

    def connect(self):
        self.sock = socket.create_connection((self._ip, self.port), self.timeout)


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host, port, ip, timeout):
        ctx = ssl.create_default_context()
        super().__init__(host, port, timeout=timeout, context=ctx)
        self._ip = ip
        self._ctx = ctx

    def connect(self):
        raw = socket.create_connection((self._ip, self.port), self.timeout)
        self.sock = self._ctx.wrap_socket(raw, server_hostname=self.host)


def _read_capped(resp, cap: int) -> tuple[bytes, bool]:
    chunks, total = [], 0
    while True:
        chunk = resp.read(min(65536, cap + 1 - total))
        if not chunk:
            return b"".join(chunks), False
        chunks.append(chunk)
        total += len(chunk)
        if total > cap:
            return b"".join(chunks)[:cap], True


def _safe_get(url: str, deadline: float, body_cap: int = MAX_BODY_BYTES) -> dict:
    """GET with redirect re-validation. Returns dict(final_url,status,ctype,body,truncated)."""
    current = url
    for hop in range(MAX_REDIRECTS + 1):
        scheme, host, port, ips = validate_url(current)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("timeout")
        parts = urlsplit(current)
        path = urlunsplit(("", "", parts.path or "/", parts.query, ""))
        cls = _PinnedHTTPSConnection if scheme == "https" else _PinnedHTTPConnection
        conn = cls(host, port, ips[0], timeout=min(remaining, TIMEOUT_SECONDS))
        try:
            conn.request("GET", path, headers={
                "Host": host if port in (80, 443) else f"{host}:{port}",
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,text/*;q=0.8",
                "Accept-Language": "en-AU,en;q=0.9,zh-TW;q=0.8",
                "Accept-Encoding": "gzip, deflate",
                "Connection": "close",
            })
            resp = conn.getresponse()
            if resp.status in (301, 302, 303, 307, 308):
                loc = resp.getheader("Location")
                if not loc:
                    raise FetchBlocked(f"redirect {resp.status} without Location")
                current = urljoin(current, loc)
                continue
            ctype = (resp.getheader("Content-Type") or "").lower()
            if ctype and not ctype.startswith(ALLOWED_CONTENT_TYPES):
                return {"final_url": current, "status": resp.status, "ctype": ctype,
                        "body": b"", "truncated": False, "refused_type": True}
            body, truncated = _read_capped(resp, body_cap)
            enc = (resp.getheader("Content-Encoding") or "").lower()
            if enc in ("gzip", "deflate"):
                try:  # bounded decompression (zip-bomb safe): never more than body_cap
                    d = zlib.decompressobj(16 + zlib.MAX_WBITS if enc == "gzip" else zlib.MAX_WBITS)
                    out = d.decompress(body, body_cap)
                    if d.unconsumed_tail:
                        truncated = True
                    body = out
                except Exception:
                    body = b""
            return {"final_url": current, "status": resp.status, "ctype": ctype,
                    "body": body, "truncated": truncated, "refused_type": False}
        finally:
            conn.close()
    raise FetchBlocked(f"too many redirects (>{MAX_REDIRECTS})")


# ---------------------------------------------------------------------------
# HTML → text
# ---------------------------------------------------------------------------
class _TextExtractor(HTMLParser):
    _SKIP = {"script", "style", "noscript", "svg", "template", "iframe", "canvas", "head"}
    _BLOCK = {"p", "div", "section", "article", "li", "ul", "ol", "tr", "table", "br",
              "h1", "h2", "h3", "h4", "h5", "h6", "header", "footer", "nav", "main",
              "aside", "blockquote", "pre", "dd", "dt", "figcaption", "hr"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.title = ""
        self._skip_depth = 0
        self._in_title = False
        self._svg_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag == "svg":
            self._svg_depth += 1
        if tag == "title" and not self._svg_depth and not self.title:
            self._in_title = True
        if tag in self._SKIP:
            self._skip_depth += 1
        elif tag in self._BLOCK:
            self.parts.append("\n")
        if tag in ("h1", "h2", "h3") and not self._skip_depth:
            self.parts.append("#" * int(tag[1]) + " ")
        if tag == "li" and not self._skip_depth:
            self.parts.append("- ")

    def handle_endtag(self, tag):
        if tag == "svg" and self._svg_depth:
            self._svg_depth -= 1
        if tag == "title":
            self._in_title = False
        if tag in self._SKIP and self._skip_depth:
            self._skip_depth -= 1
        elif tag in self._BLOCK:
            self.parts.append("\n")
        elif tag in ("td", "th"):
            self.parts.append(" | ")

    def handle_data(self, data):
        if self._in_title:
            self.title += data
            return
        if self._svg_depth:
            return
        if not self._skip_depth:
            self.parts.append(data)


def _decode(body: bytes, ctype: str) -> str:
    m = re.search(r"charset=([\w\-]+)", ctype or "")
    charset = m.group(1) if m else None
    if not charset:
        m2 = re.search(rb"<meta[^>]+charset=[\"']?([\w\-]+)", body[:4096], re.I)
        charset = m2.group(1).decode("ascii", "ignore") if m2 else "utf-8"
    try:
        return body.decode(charset, errors="replace")
    except LookupError:
        return body.decode("utf-8", errors="replace")


def html_to_text(raw_html: str) -> tuple[str, str]:
    p = _TextExtractor()
    try:
        p.feed(raw_html)
        p.close()
    except Exception:
        pass
    text = "".join(p.parts)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return html.unescape(p.title).strip(), text.strip()


# ---------------------------------------------------------------------------
# crawl4ai backend
# ---------------------------------------------------------------------------
def _crawl4ai_token() -> str:
    tok = os.environ.get("CRAWL4AI_API_TOKEN", "").strip()
    if not tok:
        path = os.environ.get("CRAWL4AI_API_TOKEN_FILE", "").strip()
        if path and os.path.isfile(path):
            try:
                with open(path, encoding="utf-8") as f:
                    tok = f.read().strip()
            except OSError:
                tok = ""
    return tok


def _crawl4ai_md(url: str, deadline: float) -> str:
    """Call crawl4ai /md for an ALREADY VALIDATED public url. Returns markdown."""
    token = _crawl4ai_token()
    if not token:
        raise RuntimeError("crawl4ai token not configured")
    base = urlsplit(CRAWL4AI_BASE_URL)
    if base.scheme not in ("http", "https") or not base.hostname:
        raise RuntimeError("CRAWL4AI_BASE_URL invalid")
    remaining = CRAWL4AI_TIMEOUT
    cls = http.client.HTTPSConnection if base.scheme == "https" else http.client.HTTPConnection
    conn = cls(base.hostname, base.port or (443 if base.scheme == "https" else 80), timeout=remaining)
    try:
        payload = json.dumps({"url": url, "f": "fit", "c": "0"})
        conn.request("POST", (base.path.rstrip("/") or "") + "/md", body=payload, headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        })
        resp = conn.getresponse()
        body, _ = _read_capped(resp, MAX_BODY_BYTES)
        if resp.status != 200:
            raise RuntimeError(f"crawl4ai HTTP {resp.status}")
        data = json.loads(body.decode("utf-8", errors="replace"))
    finally:
        conn.close()
    if isinstance(data, dict):
        if data.get("success") is False:
            raise RuntimeError(f"crawl4ai failed: {str(data.get('error') or '')[:200]}")
        for k in ("markdown", "fit_markdown", "raw_markdown", "content"):
            v = data.get(k)
            if isinstance(v, str) and v.strip():
                return v
    raise RuntimeError("crawl4ai returned no markdown")


# ---------------------------------------------------------------------------
# Public entry
# ---------------------------------------------------------------------------
def fetch_url(url: str, max_chars: int = DEFAULT_MAX_CHARS, use_crawl4ai: bool = True) -> dict:
    max_chars = max(500, min(int(max_chars or DEFAULT_MAX_CHARS), HARD_MAX_CHARS))
    fetched_at = time.strftime("%Y-%m-%d %H:%M:%S %Z")
    deadline = time.monotonic() + TIMEOUT_SECONDS
    try:
        # Safe stdlib GET first: validates every hop and gives the final URL.
        res = _safe_get(url, deadline)
    except FetchBlocked as exc:
        logger.info("[web_fetch] blocked url={} reason={}", url[:120], exc)
        return {"status": "blocked", "url": url, "message": str(exc)}
    except Exception as exc:
        res = None
        stdlib_error = f"{type(exc).__name__}: {exc}"
    else:
        stdlib_error = ""

    final_url = res["final_url"] if res else url
    if res and res.get("refused_type"):
        return {"status": "error", "url": final_url,
                "message": f"content type '{res['ctype']}' not allowed (text/HTML/JSON/XML only; no file downloads)"}

    backend, title, text, note = "", "", "", ""
    if use_crawl4ai and _crawl4ai_token():
        try:
            validate_url(final_url)  # re-check the final target before handing it over
            text = _crawl4ai_md(final_url, deadline)
            backend = "crawl4ai"
        except FetchBlocked as exc:
            return {"status": "blocked", "url": final_url, "message": str(exc)}
        except Exception as exc:
            note = f"crawl4ai unavailable ({type(exc).__name__}: {str(exc)[:160]}); used stdlib fallback"
    elif use_crawl4ai:
        note = "crawl4ai token not configured; used stdlib fallback (no JavaScript rendering)"

    if not backend:
        if res is None:
            return {"status": "error", "url": url, "message": f"fetch failed: {stdlib_error}"}
        raw = _decode(res["body"], res["ctype"])
        if "html" in res["ctype"] or raw.lstrip()[:200].lower().startswith(("<!doctype html", "<html")):
            title, text = html_to_text(raw)
        else:
            text = raw.strip()
        backend = "stdlib"

    if not title:
        m = re.search(r"^#\s+(.+)$", text, re.M)
        title = m.group(1).strip() if m else ""
    truncated = len(text) > max_chars or bool(res and res.get("truncated"))
    text = text[:max_chars]
    http_status = res["status"] if res else None
    out = {
        "status": "ok" if text.strip() else "empty",
        "url": url,
        "final_url": final_url,
        "http_status": http_status,
        "backend": backend,
        "title": title[:300],
        "fetched_at": fetched_at,
        "truncated": truncated,
        "content": text,
        "note": note,
        "citation_hint": f"來源：{final_url}（擷取時間 {fetched_at}）",
    }
    if http_status and http_status >= 400:
        out["status"] = "http_error"
        out["message"] = (f"HTTP {http_status} — the site may block automated access "
                          "(e.g. Coles/Woolworths bot protection). Do not invent the data; "
                          "report it as unavailable or use web_search snippets with their source.")
    logger.info("[web_fetch] url={} backend={} status={} chars={}", final_url[:120], backend,
                http_status, len(text))
    return out


@tool
def web_fetch(url: str, max_chars: int = DEFAULT_MAX_CHARS) -> dict:
    """Open ONE public web page (http/https) and return its readable text/markdown.

    Use this after web_search (or when you already know the URL) to read the
    actual page: competitor sites, retailer product pages (Coles, Woolworths),
    ABS statistics, news, our own sites (uzena.com.au, gwifruits.com).

    Rules:
    - Public internet only. Private/LAN/Tailscale/localhost addresses are refused.
    - GET only, ~20 s timeout, 2 MB page cap, text/HTML/JSON/XML only (no file downloads).
    - If status is "http_error"/"blocked"/"error", say the page could not be read; NEVER invent numbers.
    - Always cite the returned final_url and fetched_at for every fact you use.

    Args:
        url: Full http(s) URL of the page.
        max_chars: Max characters of content to return (default 20000, max 60000).
    """
    return fetch_url(url, max_chars=max_chars)
