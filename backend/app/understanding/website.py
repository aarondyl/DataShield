"""Bounded public HTML analysis. Connections pin validated IPs; redirects are checked before fetching."""
from collections import deque
from html.parser import HTMLParser
import http.client
import ipaddress
import re
import socket
import ssl
import time
from urllib.parse import urljoin, urlsplit, urlunsplit, unquote
from uuid import uuid4
from .rules import Collector, FEATURES, DATA, VENDORS, CATEGORIES, TARGETS, MARKETS, CAPABILITIES, SECRET, safe_lines
from .schemas import WebsiteAnalysisResult, PublicDocument, TargetUser, MarketClue, Evidence

MAX_BYTES = 512_000
DOCUMENTS = {
    "privacy_policy": r"privacy[ /_-]?policy|隐私政策",
    "terms": r"terms(?:[ /_-]of)?[ /_-](?:service|use)|服务条款",
    "cookie_policy": r"cookie[ /_-]?policy|Cookie政策",
    "AI_disclosure": r"ai[ /_-]?disclosure|AI披露",
    "data_processing_agreement": r"data[ /_-]?processing[ /_-]?agreement|\bdpa\b",
    "refund_policy": r"refund[ /_-]?policy|退款政策",
    "contact_or_complaint_channel": r"contact(?:[ /_-]?us)?|complaint|联系我们",
    "delete_account_help": r"delete[ /_-]?account|account[ /_-]?deletion|删除账号",
    "data_export_help": r"data[ /_-]?export|export[ /_-]?data|导出数据",
}
IMPORTANT = re.compile(r"pricing|product|features|signup|login|privacy|terms|cookie|disclosure|contact|help|support|refund|export|delete|dpa", re.I)
WEB_FEATURES = dict(FEATURES, signup=FEATURES["user_registration"], cookies=r"\bcookies?\b", contact_form=r"\bcontact[ _-]?form\b|联系表单")


def public_url(url):
    if len(url) > 2048 or any(ord(c) < 33 for c in url) or "\\" in url:
        raise ValueError("Invalid public URL")
    p = urlsplit(url)
    if p.scheme not in ("http", "https") or not p.hostname or p.username or p.password or p.query:
        raise ValueError("Only HTTP(S) without credentials or queries is allowed")
    if p.port not in (None, 80 if p.scheme == "http" else 443):
        raise ValueError("Nonstandard port")
    if SECRET.search(unquote(p.path)) or re.search(r"[A-Za-z0-9_-]{48,}", unquote(p.path)):
        raise ValueError("Sensitive URL path")
    host = p.hostname.encode("idna").decode("ascii").lower()
    if SECRET.search(host) or re.search(r"[A-Za-z0-9_-]{48,}", host):
        raise ValueError("Sensitive hostname")
    if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
        raise ValueError("Non-public host")
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None and (not literal.is_global or literal.is_multicast or literal.is_reserved
            or (isinstance(literal, ipaddress.IPv6Address) and literal.ipv4_mapped)):
        raise ValueError("Non-public IP")
    authority = f"[{host}]" if ":" in host else host
    return urlunsplit((p.scheme, authority, p.path or "/", "", ""))


def public_addresses(host, port):
    addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    if not addresses:
        raise ValueError("No public address")
    for _, _, _, _, address in addresses:
        ip = ipaddress.ip_address(address[0])
        if not ip.is_global or ip.is_multicast or ip.is_reserved or (isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped):
            raise ValueError("Non-public destination")
    return addresses


def fetch_page(url, deadline):
    """No proxies, cookies, automatic redirects or second DNS lookup at connection time."""
    parsed = urlsplit(public_url(url))
    port = 443 if parsed.scheme == "https" else 80
    family, socktype, proto, _, address = public_addresses(parsed.hostname, port)[0]
    remaining = min(8, deadline - time.monotonic())
    if remaining <= 0:
        raise TimeoutError("Crawl deadline")
    sock = socket.socket(family, socktype, proto)
    connection = http.client.HTTPConnection(parsed.hostname, port, timeout=remaining)
    try:
        sock.settimeout(remaining)
        sock.connect(address)
        if parsed.scheme == "https":
            sock = ssl.create_default_context().wrap_socket(sock, server_hostname=parsed.hostname)
        connection.sock = sock
        connection.request("GET", parsed.path, headers={"User-Agent": "DataShield-ProductUnderstanding/1.0",
            "Accept": "text/html", "Accept-Encoding": "identity", "Connection": "close"})
        response = connection.getresponse()
        if response.status in (301, 302, 303, 307, 308):
            return response.status, response.getheader("Location", ""), ""
        if response.status != 200 or "text/html" not in response.getheader("Content-Type", "").lower():
            raise ValueError("Not a public HTML page")
        if response.getheader("Content-Encoding", "identity") != "identity":
            raise ValueError("Compressed response")
        length = response.getheader("Content-Length")
        if length and int(length) > MAX_BYTES:
            raise ValueError("Page too large")
        body = bytearray()
        while True:
            remaining = min(8, deadline - time.monotonic())
            if remaining <= 0:
                raise TimeoutError("Crawl deadline")
            sock.settimeout(remaining)
            chunk = response.read1(min(16384, MAX_BYTES + 1 - len(body)))
            if not chunk:
                break
            body.extend(chunk)
            if len(body) > MAX_BYTES:
                raise ValueError("Page too large")
        return 200, "", body.decode("utf-8", errors="replace")
    finally:
        connection.close()
        sock.close()


class Parser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text, self.headings, self.links, self.scripts, self.interactions = [], [], [], [], []
        self.stack = []
        self.anchor = None
        self.heading = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        hidden = (any(h for _, h in self.stack) or tag in ("script", "style", "template", "noscript")
            or "hidden" in attrs or attrs.get("aria-hidden") == "true"
            or bool(re.search(r"display\s*:\s*none|visibility\s*:\s*hidden", attrs.get("style", ""), re.I)))
        if tag == "script" and attrs.get("src"):
            self.scripts.append(urlsplit(attrs["src"]).hostname or "")
        if tag not in ("input", "img", "br", "hr", "meta", "link", "source", "area", "embed", "wbr"):
            self.stack.append((tag, hidden))
        if hidden:
            return
        if tag == "a" and attrs.get("href"):
            self.anchor = [attrs["href"], []]
        if tag in ("title", "h1", "h2"):
            self.heading = True
        if tag == "input" and attrs.get("type", "").lower() in ("file", "search", "email", "tel"):
            self.interactions.append(attrs["type"].lower())

    def handle_endtag(self, tag):
        if tag == "a" and self.anchor:
            self.links.append((self.anchor[0], " ".join(self.anchor[1])))
            self.anchor = None
        if tag in ("title", "h1", "h2"):
            self.heading = False
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                break

    def handle_data(self, data):
        if any(h for _, h in self.stack):
            return
        clean = " ".join(line for _, line, _ in safe_lines(data))
        if clean:
            self.text.append(clean)
            if self.heading:
                self.headings.append(clean)
            if self.anchor:
                self.anchor[1].append(clean)


def analyze_website(request, fetch=fetch_page):
    start = public_url(request.url)
    origin = urlsplit(start).netloc
    queue = deque([(start, 0, 0)])
    seen, analyzed = set(), []
    c = Collector()
    documents = {}
    deadline = time.monotonic() + 60
    limited, requests = False, 0
    limitations = ["公开声明与静态 HTML 无法验证后端行为；置信度为启发式估计。",
        "市场线索不能判定法域或法律适用性。",
        "仅抓取公开的同源页面；不执行 JavaScript、登录与表单。"]
    while queue and len(analyzed) < request.max_pages and requests < request.max_pages * 3:
        if time.monotonic() >= deadline:
            limited = True
            break
        url, depth, redirects = queue.popleft()
        if url in seen:
            continue
        seen.add(url)
        requests += 1
        try:
            url = public_url(url)
            status, location, body = fetch(url, deadline)
            if status in (301, 302, 303, 307, 308):
                target = public_url(urljoin(url, location))
                if urlsplit(target).netloc != origin or redirects >= 3 or target in seen or (urlsplit(url).scheme == "https" and urlsplit(target).scheme != "https"):
                    raise ValueError("Redirect not permitted")
                queue.appendleft((target, depth, redirects + 1))
                continue
            if status != 200:
                raise ValueError("Page unavailable")
            page = Parser()
            page.feed(body)
            page.close()
        except (OSError, ValueError, http.client.HTTPException):
            limited = True
            continue
        analyzed.append(url)
        source = {"type": "WEB_PAGE", "url": url}
        text = " ".join(page.text)
        for group, rules in (("features", WEB_FEATURES), ("data_types", DATA), ("vendors", VENDORS),
                ("capabilities", CAPABILITIES), ("category", CATEGORIES), ("target_users", TARGETS), ("market_clues", MARKETS)):
            c.scan(group, rules, text, source, .65, "PARTIAL")
        c.scan("vendors", VENDORS, " ".join(page.scripts), {"type": "PUBLIC_REFERENCE", "url": url}, .85)
        for interaction in page.interactions:
            if interaction in ("file", "search"):
                c.add("features", "file_upload" if interaction == "file" else "search", source, .9)
            if interaction in ("file", "email", "tel"):
                c.add("data_types", {"file": "uploaded_files", "email": "email", "tel": "phone"}[interaction], source, .8, "PARTIAL")
        for name, pattern in DOCUMENTS.items():
            if re.search(pattern, " ".join(page.headings), re.I):
                eid = f"document_{len(c.evidence)}"
                c.evidence.append(Evidence(evidence_id=eid, type="WEB_PAGE", url=url,
                    reason=f"Retrieved page heading identifies {name}; document adequacy is not assessed."))
                documents[name] = PublicDocument(present=True, status="PRESENT", url=url, confidence=.9, evidence_ids=[eid])
        for href, label in page.links[:500]:
            try:
                target = public_url(urljoin(url, href))
            except ValueError:
                continue
            if urlsplit(target).netloc != origin or target in seen:
                continue
            target_path = urlsplit(target).path
            if re.search(r"logout|signout|unsubscribe|delete|remove|checkout", target_path, re.I) and not re.search(r"/(?:help|docs|support|guides|faq)/", target_path, re.I):
                continue
            if IMPORTANT.search(target + " " + label):
                if depth >= request.max_depth or len(queue) >= 100:
                    limited = True
                else:
                    queue.append((target, depth + 1, 0))
    if not analyzed:
        raise ValueError("No public pages could be analyzed")
    limited |= bool(queue)
    if limited:
        limitations.append("部分页面不可用或超出抓取范围；未发现的项保持 UNKNOWN。")
    c.description(request.product_description)
    c.evidence.append(Evidence(evidence_id="scope", type="SCAN_SCOPE", url=start,
        reason=f"已分析 {len(analyzed)} 个公开页面；页面数上限 {request.max_pages}，深度上限 {request.max_depth}。未检测的结论仅限这些页面。"))
    for name in DOCUMENTS:
        documents.setdefault(name, PublicDocument(status="UNKNOWN" if limited else "NOT_DETECTED", confidence=0 if limited else .5, evidence_ids=["scope"]))
    category_facts = c.facts.get("category", {})
    candidates = [name for name in category_facts if name != "AI Tool"]
    category = candidates[0] if len(candidates) == 1 else "UNKNOWN" if len(candidates) > 1 else next(iter(category_facts), "UNKNOWN")
    return WebsiteAnalysisResult(website_id=uuid4().hex, url=start, product_category=category, product_category_fact=category_facts.get(category),
        target_users=[TargetUser(type=f.name, confidence=f.confidence, evidence_ids=f.evidence_ids) for f in c.facts.get("target_users", {}).values()],
        market_clues=[MarketClue(jurisdiction=f.name, confidence=f.confidence, evidence_ids=f.evidence_ids) for f in c.facts.get("market_clues", {}).values()],
        features=c.complete("features", WEB_FEATURES, not limited), data_types=list(c.facts.get("data_types", {}).values()), vendors=list(c.facts.get("vendors", {}).values()),
        capabilities={f.name: f for f in c.complete("capabilities", CAPABILITIES, not limited)}, public_documents=documents,
        pages_analyzed=analyzed, evidence=c.evidence, confidence=.65 if not limited else .4, coverage_complete=not limited, limitations=limitations)
