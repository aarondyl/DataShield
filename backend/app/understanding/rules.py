"""Deterministic clues, not assertions of runtime behavior. No source excerpts leave this layer."""
import re
from .schemas import Evidence, Fact, FindingStatus

STACK = {
    "React": r"\breact(?:-dom)?\b", "Next.js": r"\bnext(?:\.js)?\b", "Vue": r"\bvue\b",
    "Node.js": r"\bnode(?:\.js)?\b", "Express": r"\bexpress\b", "FastAPI": r"\bfastapi\b",
    "Django": r"\bdjango\b", "Flask": r"\bflask\b", "Python": r"\bpython\b",
    "TypeScript": r"\btypescript\b", "JavaScript": r"\bjavascript\b",
    "PostgreSQL": r"\b(?:postgresql|postgres|psycopg\w*|asyncpg)\b", "MySQL": r"\b(?:mysql|pymysql)\b",
    "MongoDB": r"\b(?:mongodb|pymongo|mongoose)\b", "Redis": r"\bredis\b",
    "Supabase": r"\bsupabase\b", "Firebase": r"\bfirebase\b", "Docker": r"\bdocker\b",
}
VENDORS = {
    "OpenAI": r"\bopenai\b", "Anthropic": r"\banthropic\b", "Google Gemini": r"\b(?:google-genai|google-generativeai|gemini)\b",
    "Stripe": r"\bstripe\b", "Paddle": r"\b(?:paddle|paddlepaddle)\b", "AWS": r"\b(?:aws-sdk|boto3|amazonaws)\b",
    "Alibaba Cloud": r"\b(?:aliyun|alibabacloud)\b", "Google Cloud": r"\b(?:google-cloud|googleapis)\b",
    "Firebase": r"\bfirebase\b", "Supabase": r"\bsupabase\b", "Auth0": r"\bauth0\b",
    "Clerk": r"\bclerk\b", "Cloudflare": r"\bcloudflare\b", "Vercel": r"\bvercel\b",
    "Sentry": r"\bsentry\b", "Google Analytics": r"\b(?:google-analytics|googletagmanager|google analytics)\b",
    "PostHog": r"\bposthog\b", "Intercom": r"\bintercom\b",
}
FEATURES = {
    "user_registration": r"\b(?:sign[_ -]?up|register[_ -]?user|registration)\b|注册",
    "login": r"\b(?:log[_ -]?in|sign[_ -]?in|authenticate)\b|登录",
    "oauth": r"\boauth\w*\b", "user_profile": r"\b(?:user[_ -]?profile|profile[_ -]?settings)\b|用户资料",
    "payment": r"\b(?:checkout|payment|create[_ -]?payment)\b|支付",
    "subscription": r"\bsubscription\w*\b|订阅", "file_upload": r"\b(?:upload[_ -]?file|file[_ -]?upload|UploadFile)\b|上传文件",
    "AI_generation": r"\b(?:ai[_ -]?generation|generate[_ -]?(?:image|text)|images\.generate|completions\.create)\b|AI生成",
    "AI_chat": r"\b(?:ai[_ -]?chat|chatbot|chat\.completions)\b|智能对话",
    "recommendation": r"\brecommend(?:ation|er|ations)\b|推荐",
    "search": r"\bsearch\b|搜索", "analytics": r"\b(?:analytics|posthog|google-analytics)\b",
    "admin_panel": r"\badmin[_ /-]?(?:panel|dashboard)\b|管理后台",
    "email": r"\b(?:send[_ -]?mail|send[_ -]?email|smtp)\b|发送邮件",
    "notification": r"\bnotification\w*\b|通知",
    "content_creation": r"\b(?:create[_ -]?(?:post|content)|publish[_ -]?post)\b|发布内容",
    "content_storage": r"\b(?:save[_ -]?(?:content|document)|object[_ -]?storage)\b|内容存储",
    "data_export": r"\b(?:export[_ -]?(?:data|account)|data[_ -]?export)\b|导出数据",
    "account_deletion": r"\b(?:delete[_ -]?(?:account|user)|account[_ -]?deletion)\b|删除账号",
}
CAPABILITIES = {k: FEATURES[k] for k in ("account_deletion", "data_export")}
CAPABILITIES.update({
    "cookie_consent": r"\b(?:cookie[_ -]?consent|accept[_ -]?cookies)\b|Cookie同意",
    "privacy_policy": r"\bprivacy[_ -]?policy\b|隐私政策",
    "terms_of_service": r"\bterms[_ -]?(?:of[_ -]?)?(?:service|use)\b|服务条款",
    "AI_disclosure": r"\bai[_ -]?disclosure\b|AI披露",
    "age_gate": r"\b(?:age[_ -]?(?:gate|verification)|verify[_ -]?age)\b|年龄验证",
    "data_retention": r"\b(?:data[_ -]?retention|retention[_ -]?(?:days|policy))\b|数据保留",
    "audit_logging": r"\baudit[_ -]?log\w*\b|审计日志",
    "access_control": r"\b(?:access[_ -]?control|rbac|has[_ -]?permission|require[_ -]?role)\b|访问控制",
    "user_consent": r"\b(?:user[_ -]?consent|consent[_ -]?(?:record|form))\b|用户同意",
    "marketing_opt_out": r"\b(?:unsubscribe|marketing[_ -]?opt[_ -]?out)\b|退订",
    "contact_or_complaint_channel": r"\b(?:contact[_ -]?us|complaint|support[_ -]?email)\b|联系我们",
})
DATA = {
    "email": r"\bemail\b", "username": r"\busername\b", "phone": r"\b(?:phone|telephone)\b",
    "IP_address": r"\b(?:ip[_ -]?address|client\.host|remote_addr)\b", "location": r"\b(?:geolocation|latitude|longitude)\b",
    "payment_metadata": r"\b(?:payment[_ -]?id|billing|invoice)\b", "user_generated_content": r"\b(?:user[_ -]?content|comment[_ -]?body|post[_ -]?body)\b",
    "uploaded_files": FEATURES["file_upload"], "images": r"\b(?:image|images|image_url)\b",
    "documents": r"\b(?:document|documents|pdf)\b", "AI_prompts": r"\b(?:prompt|prompts)\b",
    "AI_outputs": r"\b(?:completion|generated[_ -]?(?:text|image)|ai[_ -]?output)\b",
    "behavior_analytics": r"\b(?:track[_ -]?event|pageview|analytics)\b", "cookies": r"\bcookies?\b",
    "device_information": r"\b(?:user[_ -]?agent|device[_ -]?(?:id|type|info))\b",
}
CATEGORIES = {
    "AI Image Generator": r"\bai image generat\w*\b", "AI Writing Tool": r"\bai writing\b",
    "AI Tool": r"\b(?:ai tool|ai powered|artificial intelligence)\b",
    "B2B SaaS": r"\b(?:b2b saas|software for businesses)\b", "B2C SaaS": r"\bb2c saas\b",
    "Marketplace": r"\bmarketplace\b", "Developer Tool": r"\bdeveloper tool\w*\b",
    "Fintech": r"\bfintech\b", "E-commerce": r"\be-commerce\b",
    "Social Product": r"\bsocial (?:network|platform)\b", "Analytics Platform": r"\banalytics platform\b",
}
TARGETS = {x: rf"\b{x}s?\b" for x in ("consumer", "business", "developer", "enterprise", "minor", "creator", "student")}
MARKETS = {"EU": r"\b(?:European Union|EU market)\b", "US": r"\b(?:United States|US market)\b",
    "China": r"\bChina\b|中国", "Singapore": r"\bSingapore\b|新加坡", "Global": r"\b(?:global|worldwide)\b"}

# Suspicious lines are discarded before extraction; never return raw content or exceptions.
SECRET = re.compile(r"(?i)(?:api[_-]?key|secret|password|passwd|token|credential|authorization|private[_ -]?key)|(?:sk-[A-Za-z0-9]{12,}|gh[pousr]_[A-Za-z0-9]+|AKIA[A-Z0-9]{16}|-----BEGIN .*PRIVATE KEY)")


def safe_lines(text: str):
    in_key = False
    for number, line in enumerate(text.splitlines(), 1):
        if "-----BEGIN" in line:
            in_key = True
        sensitive = in_key or bool(SECRET.search(line))
        if "-----END" in line:
            in_key = False
        yield number, "" if sensitive else line, sensitive


class Collector:
    def __init__(self):
        self.evidence: list[Evidence] = []
        self.facts: dict[str, dict[str, Fact]] = {}

    def add(self, group, name, source, confidence, status=FindingStatus.PRESENT):
        facts = self.facts.setdefault(group, {})
        fact = facts.get(name)
        if fact and len(fact.evidence_ids) >= 3:
            return
        ev = Evidence(evidence_id=f"ev_{len(self.evidence) + 1:04d}", **source,
            reason=f"{name}: {group} clue detected; does not establish runtime behavior.")
        self.evidence.append(ev)
        if fact is None:
            fact = Fact(name=name, status=status, confidence=confidence)
            facts[name] = fact
        if confidence > fact.confidence:
            fact.confidence, fact.status = confidence, status
        fact.evidence_ids.append(ev.evidence_id)

    def scan(self, group, rules, text, source, confidence, status=FindingStatus.PRESENT):
        for name, pattern in rules.items():
            if re.search(pattern, text, re.I):
                self.add(group, name, source, confidence, status)

    def complete(self, group, rules, complete=False):
        found = self.facts.get(group, {})
        return [found.get(name, Fact(name=name, status="NOT_DETECTED" if complete else "UNKNOWN",
                    confidence=0.5 if complete else 0, evidence_ids=["scope"])) for name in rules]

    def description(self, value):
        if value:
            text = "\n".join(line for _, line, _ in safe_lines(value))
            for group, rules in (("features", FEATURES), ("data_types", DATA), ("vendors", VENDORS)):
                self.scan(group, rules, text, {"type": "USER_DESCRIPTION"}, 0.35, FindingStatus.PARTIAL)
