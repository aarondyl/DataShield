"""Bounded public-page fetcher. It follows same-origin HTTP links only and blocks private hosts."""
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse
import ipaddress, socket, re
from urllib.request import Request, urlopen
from uuid import uuid4
from .rules import Collector, FEATURES, DATA, VENDORS, CATEGORIES, TARGETS, MARKETS, CAPABILITIES
from .schemas import WebsiteAnalysisResult, WebsiteRequest, Fact, PublicDocument, TargetUser, MarketClue, Evidence

class Parser(HTMLParser):
    def __init__(self): super().__init__(); self.text=[]; self.links=[]; self.scripts=[]; self.in_script=False
    def handle_starttag(self, tag, attrs):
        d=dict(attrs); href=d.get("href")
        if href: self.links.append(href)
        if tag == "script": self.in_script=True; self.scripts.append(d.get("src", ""))
    def handle_endtag(self, tag):
        if tag == "script": self.in_script=False
    def handle_data(self, data):
        if not self.in_script: self.text.append(data)

def public_url(url):
    parsed=urlparse(url)
    if parsed.scheme not in ("http", "https") or parsed.username or parsed.password or parsed.fragment: raise ValueError("Only public HTTP(S) URLs are allowed")
    host=parsed.hostname
    try: ips=socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme=="https" else 80), type=socket.SOCK_STREAM)
    except OSError: raise ValueError("Website host could not be resolved") from None
    for item in ips:
        ip=ipaddress.ip_address(item[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast: raise ValueError("Private or local website is not allowed")
    return parsed._replace(fragment="").geturl()

def analyze_website(request: WebsiteRequest):
    start=public_url(request.url); origin=urlparse(start).netloc; queue=[(start,0)]; visited=[]; pages={}; c=Collector(); limitations=["Public HTML clues do not prove runtime behavior or service ownership."]
    while queue and len(visited)<request.max_pages:
        url,depth=queue.pop(0)
        if url in visited or depth>request.max_depth: continue
        try:
            req=Request(url, headers={"User-Agent":"DataShield-ProductUnderstanding/1.0"})
            with urlopen(req, timeout=10) as response:
                final=public_url(response.geturl()); body=response.read(512000).decode("utf-8", "ignore")
        except Exception: limitations.append("Some public pages could not be fetched."); continue
        p=Parser(); p.feed(body); text=" ".join(p.text); visited.append(final); pages[final]=(text,p.scripts)
        source={"type":"WEB_PAGE","url":final}; c.scan("features", FEATURES, text, source, .75); c.scan("data_types", DATA, text, source, .6); c.scan("vendors", VENDORS, text+" "+" ".join(p.scripts), source, .8)
        for href in p.links:
            nxt=urljoin(final, href); parsed=urlparse(nxt)
            if parsed.scheme in ("http","https") and parsed.netloc==origin and nxt not in visited and len(queue)+len(visited)<request.max_pages: queue.append((parsed._replace(fragment="").geturl(),depth+1))
    if request.product_description: c.description(request.product_description)
    alltext=" ".join(v[0] for v in pages.values()); c.scan("category", CATEGORIES, alltext, {"type":"PUBLIC_REFERENCE","url":start}, .65, "PARTIAL")
    users=[TargetUser(type=k, confidence=.65, evidence_ids=[]) for k,p in TARGETS.items() if re.search(p,alltext,re.I)]
    markets=[MarketClue(jurisdiction=k, confidence=.6, evidence_ids=[]) for k,p in MARKETS.items() if re.search(p,alltext,re.I)]
    docs={}
    labels={"privacy_policy":r"privacy|隐私", "terms":r"terms|条款", "cookie_policy":r"cookie", "AI_disclosure":r"ai.*disclosure|AI披露", "contact":r"contact|联系我们"}
    for name,pat in labels.items():
        match=next((u for u in pages if re.search(pat,u,re.I) or re.search(pat,pages[u][0],re.I)),None)
        ev=[]
        if match:
            e=f"ev_{len(c.evidence)+1:04d}"; c.evidence.append(Evidence(evidence_id=e,type="WEB_PAGE",url=match,reason=f"Public {name} page/reference detected.")); ev=[e]
        docs[name]=PublicDocument(present=bool(match),status="PRESENT" if match else "NOT_DETECTED",url=match,confidence=.85 if match else .55,evidence_ids=ev)
    category=next(iter(c.facts.get("category",{})),"UNKNOWN")
    c.evidence.append(Evidence(evidence_id="scope",type="SCAN_SCOPE",url=start,reason=f"Analyzed {len(visited)} same-origin public pages, max_depth={request.max_depth}, max_pages={request.max_pages}."))
    return WebsiteAnalysisResult(website_id=uuid4().hex,url=start,product_category=category, product_category_fact=c.facts.get("category",{}).get(category), target_users=users, market_clues=markets, features=list(c.facts.get("features",{}).values()), data_types=list(c.facts.get("data_types",{}).values()), vendors=list(c.facts.get("vendors",{}).values()), capabilities={name: Fact(name=name,status="PRESENT" if doc.present else "NOT_DETECTED",confidence=doc.confidence,evidence_ids=doc.evidence_ids) for name,doc in docs.items()}, public_documents=docs, pages_analyzed=visited, evidence=c.evidence, confidence=.65 if visited else 0, coverage_complete=bool(visited), limitations=limitations)
