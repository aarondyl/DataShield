"""Embedding Provider 抽象。

- ``local``：字符 n-gram（unigram + bigram）哈希到 N 维（默认 384）并做 L2 归一化。
  完全离线、确定性，中英文文本均可用；适合本机开发与测试。
- ``api``：OpenAI 兼容 embeddings 接口，dimensions 取 EMBEDDING_DIM（默认 384）。
  任何失败抛 :class:`EmbeddingError`，由调用方（入库/检索流程）降级到 local。
"""

from __future__ import annotations

import hashlib
import math
from abc import ABC, abstractmethod
from functools import lru_cache

from app.core.config import get_settings


class EmbeddingError(Exception):
    """Embedding 调用失败（无 Key、网络错误等）时抛出，由调用方降级处理。"""


class BaseEmbeddingProvider(ABC):
    """Embedding 提供者接口。"""

    #: provider 标识
    provider_name: str = "base"

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """批量计算文本向量，返回与输入等长的向量列表。"""


class LocalEmbeddingProvider(BaseEmbeddingProvider):
    """本地哈希向量：字符 unigram/bigram 哈希到固定维度 + 符号扰动 + L2 归一化。"""

    provider_name = "local"

    def __init__(self, dim: int | None = None) -> None:
        self.dim = dim or get_settings().embedding_dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        """对单条文本生成归一化哈希向量（确定性：同输入必得同输出）。"""
        vec = [0.0] * self.dim
        t = (text or "").strip()
        if not t:
            return vec
        # unigram 保证单字/短文本也有信号；bigram 捕获局部词序（中文分词无关，英文亦可用）
        tokens = [t[i : i + 1] for i in range(len(t))] + [t[i : i + 2] for i in range(len(t) - 1)]
        for token in tokens:
            digest = hashlib.md5(token.encode("utf-8")).digest()
            bucket = int.from_bytes(digest[:8], "little")
            idx = bucket % self.dim
            # 用哈希最高位决定符号，降低不同 token 碰撞后的正向叠加偏置
            sign = 1.0 if digest[15] & 0x80 else -1.0
            weight = 1.0 if len(token) == 2 else 0.5
            vec[idx] += sign * weight
        norm = math.sqrt(sum(x * x for x in vec))
        if norm == 0.0:
            return vec
        return [x / norm for x in vec]


class ApiEmbeddingProvider(BaseEmbeddingProvider):
    """OpenAI 兼容 embeddings 接口客户端。"""

    provider_name = "api"

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.llm_api_key:
            raise EmbeddingError("未配置 LLM_API_KEY，无法使用 api embedding provider")
        from openai import OpenAI

        self._client = OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)
        self._model = settings.embedding_model
        self._dim = settings.embedding_dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            resp = self._client.embeddings.create(
                model=self._model,
                input=texts,
                dimensions=self._dim,
            )
        except Exception as exc:
            raise EmbeddingError(f"embedding 接口调用失败：{exc}") from exc
        return [list(item.embedding) for item in resp.data]


@lru_cache
def get_embedding_provider() -> BaseEmbeddingProvider:
    """按 EMBEDDING_PROVIDER 配置返回 provider 单例。

    api provider 缺 Key 时构造即抛 EmbeddingError（lru_cache 不缓存异常），
    调用方应使用 :func:`embed_texts_with_fallback` 获得自动降级能力。
    """
    settings = get_settings()
    if settings.embedding_provider == "api":
        return ApiEmbeddingProvider()
    return LocalEmbeddingProvider()


def embed_texts_with_fallback(texts: list[str]) -> list[list[float]]:
    """带降级的批量向量化：api 失败时自动回退 local，保证流程不中断。"""
    provider = get_embedding_provider()
    try:
        return provider.embed(texts)
    except EmbeddingError:
        if isinstance(provider, LocalEmbeddingProvider):
            raise
        return LocalEmbeddingProvider().embed(texts)
