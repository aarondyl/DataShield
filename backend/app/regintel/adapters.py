"""Source Adapter：统一的官方来源抓取接口。

任务书要求不为每个网站写互相不兼容的爬虫，而是统一实现：
``discover → fetch → parse_metadata → extract_content``。

MVP 提供两个实现：
- :class:`LocalFileAdapter`：从本地快照文件抓取（``file://`` 或相对 backend 根目录的路径），
  用于离线开发与演示（人工修改快照文件即可模拟官网更新）；
- :class:`HttpTextAdapter`：通过 HTTP 抓取网页/PDF 文本（真实在线抓取路径）。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
import time
from typing import TYPE_CHECKING

from app.regintel.normalization import normalize_text

if TYPE_CHECKING:
    from app.models import RegulatorySource

#: backend 根目录（app/regintel/adapters.py → backend/）
BACKEND_ROOT = Path(__file__).resolve().parents[2]


@dataclass
class RawDocument:
    """一次抓取得到的原始文档。"""

    content: str = ""
    raw_bytes: bytes | None = None
    origin_url: str = ""
    content_type: str = "text/plain"
    retrieved_at: datetime = field(default_factory=lambda: datetime.now(UTC).replace(tzinfo=None))
    metadata: dict = field(default_factory=dict)


class SourceAdapter(ABC):
    """统一的来源适配器接口（每个官方来源一个适配器实例）。"""

    def __init__(self, source: RegulatorySource) -> None:
        self.source = source

    def discover(self) -> list[str]:
        """发现该来源下的候选文档地址。MVP 单文档来源直接返回 [fetch_url]。"""
        return [self.source.fetch_url]

    @abstractmethod
    def fetch(self, document: str | None = None) -> RawDocument:
        """抓取文档原始内容。"""

    def parse_metadata(self, raw: RawDocument) -> dict:
        """从原始内容提取发布时间等元数据。MVP 依赖种子配置，返回空 dict。"""
        return {}

    def extract_content(self, raw: RawDocument) -> str:
        """提取正文并规范化。"""
        return normalize_text(raw.content)


class LocalFileAdapter(SourceAdapter):
    """本地快照文件适配器（离线演示路径）。"""

    def fetch(self, document: str | None = None) -> RawDocument:
        url = document or self.source.fetch_url
        path = url.removeprefix("file://")
        file_path = Path(path)
        if not file_path.is_absolute():
            file_path = BACKEND_ROOT / path
        if not file_path.exists():
            raise FileNotFoundError(f"来源快照不存在：{file_path}")
        raw_bytes = file_path.read_bytes()
        content = raw_bytes.decode("utf-8")
        return RawDocument(content=content, raw_bytes=raw_bytes, origin_url=str(file_path), content_type="text/plain")


class HttpTextAdapter(SourceAdapter):
    """HTTP 抓取适配器（html / pdf 来源的在线抓取路径）。"""

    MAX_DOCUMENT_BYTES = 20 * 1024 * 1024

    def fetch(self, document: str | None = None) -> RawDocument:
        import httpx

        url = document or self.source.fetch_url
        resp = None
        for attempt in range(3):
            try:
                candidate = httpx.get(
                    url,
                    timeout=20,
                    follow_redirects=True,
                    headers={"User-Agent": "DataShield-RegIntel/1.0 (+https://datashield.ltd)"},
                )
                if candidate.status_code == 429 or candidate.status_code >= 500:
                    candidate.raise_for_status()
                candidate.raise_for_status()
                resp = candidate
                break
            except httpx.HTTPError:
                if attempt == 2:
                    raise
                time.sleep(0.5 * (2**attempt))
        if resp is None:  # pragma: no cover - loop either returns or raises
            raise RuntimeError("法规来源抓取未能完成")
        if len(resp.content) > self.MAX_DOCUMENT_BYTES:
            raise ValueError(f"法规来源响应超过 {self.MAX_DOCUMENT_BYTES // (1024 * 1024)} MiB 上限")
        content_type = resp.headers.get("content-type", "")
        if "pdf" in content_type or url.lower().endswith(".pdf"):
            import io

            from pypdf import PdfReader

            text = "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(resp.content)).pages)
            return RawDocument(content=text, raw_bytes=resp.content, origin_url=url, content_type="application/pdf")
        return RawDocument(content=resp.text, raw_bytes=resp.content, origin_url=url, content_type="text/html")

    def extract_content(self, raw: RawDocument) -> str:
        text = raw.content
        if raw.content_type == "text/html":
            from html.parser import HTMLParser

            class _TextExtractor(HTMLParser):
                _BLOCKS = {"article", "br", "div", "h1", "h2", "h3", "h4", "li", "p", "section", "tr"}
                _IGNORED = {"script", "style", "noscript", "nav", "footer"}

                def __init__(self) -> None:
                    super().__init__(convert_charrefs=True)
                    self.parts: list[str] = []
                    self.ignored_depth = 0

                def handle_starttag(self, tag: str, attrs) -> None:
                    if tag in self._IGNORED:
                        self.ignored_depth += 1
                    elif self.ignored_depth == 0 and tag in self._BLOCKS:
                        self.parts.append("\n")

                def handle_endtag(self, tag: str) -> None:
                    if tag in self._IGNORED and self.ignored_depth:
                        self.ignored_depth -= 1
                    elif self.ignored_depth == 0 and tag in self._BLOCKS:
                        self.parts.append("\n")

                def handle_data(self, data: str) -> None:
                    if self.ignored_depth == 0:
                        self.parts.append(data.replace("\u00a0", " ").replace("\u202f", " "))

            parser = _TextExtractor()
            parser.feed(text)
            parser.close()
            text = "".join(parser.parts)
        return normalize_text(text)


def get_adapter(source: RegulatorySource) -> SourceAdapter:
    """按 source_type 返回对应适配器。"""
    if source.source_type == "local_file":
        return LocalFileAdapter(source)
    if source.source_type in ("html", "pdf", "index_page"):
        return HttpTextAdapter(source)
    raise ValueError(f"暂不支持的来源类型：{source.source_type}")
