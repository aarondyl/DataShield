"""本地哈希 Embedding 测试：维度、归一化、确定性、中英文可用。"""

import math

from app.rag.embeddings import LocalEmbeddingProvider, embed_texts_with_fallback

DIM = 384


class TestLocalEmbedding:
    """LocalEmbeddingProvider 行为。"""

    def setup_method(self):
        self.provider = LocalEmbeddingProvider()

    def test_dimension(self):
        vec = self.provider.embed(["健康数据处理"])[0]
        assert len(vec) == DIM

    def test_l2_normalized(self):
        vec = self.provider.embed(["GDPR 第九条 特殊类别个人数据"])[0]
        norm = math.sqrt(sum(x * x for x in vec))
        assert abs(norm - 1.0) < 1e-6

    def test_deterministic(self):
        text = "个人信息跨境提供须通过安全评估"
        assert self.provider.embed([text])[0] == self.provider.embed([text])[0]

    def test_different_texts_differ(self):
        v1 = self.provider.embed(["健康数据"])[0]
        v2 = self.provider.embed(["跨境传输"])[0]
        assert v1 != v2

    def test_mixed_language_and_empty(self):
        # 中英文混合可用且归一化
        vec = self.provider.embed(["GDPR Article 9 健康数据 health data"])[0]
        assert len(vec) == DIM
        # 空文本返回零向量，不抛异常
        assert self.provider.embed([""])[0] == [0.0] * DIM

    def test_batch(self):
        vecs = self.provider.embed(["文本一", "文本二", "文本三"])
        assert len(vecs) == 3
        assert all(len(v) == DIM for v in vecs)


class TestFallback:
    """embed_texts_with_fallback：local 配置下直接可用。"""

    def test_fallback_returns_vectors(self):
        vecs = embed_texts_with_fallback(["测试文本"])
        assert len(vecs) == 1
        assert len(vecs[0]) == DIM
