"""本地向量检索测试：相似度排序 + metadata filter。"""

from app.rag.embeddings import LocalEmbeddingProvider
from app.rag.retrieval import LocalVectorStore

#: 6 个测试条款（覆盖 EU/CN 两个法域、健康/跨境/原则三类主题）
_DOCS = [
    ("GDPR", "EU", "第4条", "个人数据指与已识别或可识别自然人相关的任何信息。", "定义"),
    ("GDPR", "EU", "第5条", "处理个人数据须遵循合法、公平、透明、数据最小化等原则。", "处理原则"),
    ("GDPR", "EU", "第9条", "原则上禁止处理健康数据、生物识别数据等特殊类别个人数据，明示同意等例外除外。", "特殊类别数据"),
    ("GDPR", "EU", "第44条", "向第三国传输个人数据须满足充分性认定或适当保障措施等条件。", "跨境传输"),
    ("个人信息保护法", "CN", "第29条", "处理敏感个人信息（医疗健康、生物识别、行踪轨迹等）须取得个人的单独同意。", "敏感个人信息"),
    ("数据安全法", "CN", "第21条", "国家建立数据分类分级保护制度，对重要数据实行重点保护。", "分类分级"),
]


def _build_store() -> LocalVectorStore:
    provider = LocalEmbeddingProvider()
    embeddings = provider.embed([f"{num} {content}" for _, _, num, content, _ in _DOCS])
    chunks = [
        {
            "chunk_id": i + 1,
            "regulation_id": i + 1,
            "regulation_name": reg,
            "article_number": num,
            "title": "",
            "content": content,
            "source_url": "",
            "jurisdiction": jur,
            "topic": topic,
            "embedding": emb,
        }
        for i, ((reg, jur, num, content, topic), emb) in enumerate(zip(_DOCS, embeddings))
    ]
    store = LocalVectorStore()
    store.add(chunks)
    return store


class TestLocalVectorStore:
    """相似度与过滤行为。"""

    def setup_method(self):
        self.store = _build_store()
        self.provider = LocalEmbeddingProvider()

    def test_relevance_ranking_health_query(self):
        """健康数据相关查询应把 GDPR 第9条 / PIPL 第29条排在前面。"""
        query = self.provider.embed(["智能手表收集健康数据是否合规"])[0]
        hits = self.store.search(query, top_k=3)
        assert len(hits) == 3
        top_articles = {h["article_number"] for h in hits[:2]}
        assert top_articles & {"第9条", "第29条"}, f"前两名应命中健康相关条款，实际：{top_articles}"

    def test_relevance_ranking_cross_border_query(self):
        """跨境传输查询应命中 GDPR 第44条。"""
        query = self.provider.embed(["个人数据跨境传输到第三国的条件"])[0]
        hits = self.store.search(query, top_k=2)
        assert any(h["article_number"] == "第44条" for h in hits)

    def test_metadata_filter_jurisdiction(self):
        """metadata filter：只看 CN 法域时结果全部来自 CN。"""
        query = self.provider.embed(["健康数据 敏感个人信息"])[0]
        hits = self.store.search(query, top_k=5, filters={"jurisdiction": "CN"})
        assert hits, "过滤后应仍有结果"
        assert all(h["jurisdiction"] == "CN" for h in hits)

    def test_metadata_filter_regulation_name(self):
        query = self.provider.embed(["个人数据 处理 原则"])[0]
        hits = self.store.search(query, top_k=5, filters={"regulation_name": "GDPR"})
        assert hits
        assert all(h["regulation_name"] == "GDPR" for h in hits)

    def test_metadata_filter_topic(self):
        query = self.provider.embed(["跨境 传输 第三国"])[0]
        hits = self.store.search(query, top_k=5, filters={"topic": "跨境传输"})
        assert hits
        assert all(h["topic"] == "跨境传输" for h in hits)

    def test_top_k_limit_and_score(self):
        query = self.provider.embed(["个人数据"])[0]
        hits = self.store.search(query, top_k=2)
        assert len(hits) == 2
        # 结果附相似度分数且降序
        assert hits[0]["score"] >= hits[1]["score"]
