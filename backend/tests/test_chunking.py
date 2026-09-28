"""条款切分测试：中文条款切分、英文条款切分、长条款二级切分。"""

from app.rag.chunking import MAX_ARTICLE_LEN, split_into_articles


class TestChineseArticles:
    """中文「第X条」切分。"""

    def test_basic_split(self):
        text = (
            "第一条 目的\n为了规范个人信息处理活动，保护个人信息权益，制定本法。\n\n"
            "第二条 适用范围\n在中华人民共和国境内处理自然人个人信息的活动，适用本法。\n\n"
            "第三条 定义\n本法所称个人信息，是以电子或者其他方式记录的与已识别自然人有关的各种信息。"
        )
        articles = split_into_articles(text)
        assert len(articles) == 3
        assert [a["article_number"] for a in articles] == ["第一条", "第二条", "第三条"]
        assert articles[0]["title"] == "目的"
        # content 携带条款号与标题，保证片段自带上下文
        assert articles[1]["content"].startswith("第二条 适用范围")
        assert "适用本法" in articles[1]["content"]

    def test_arabic_numeral_articles(self):
        text = "第9条 特殊类别\n原则上禁止处理健康数据。\n第10条 另述\n其他规定。"
        articles = split_into_articles(text)
        assert [a["article_number"] for a in articles] == ["第9条", "第10条"]

    def test_no_article_structure_returns_empty(self):
        assert split_into_articles("这是一段没有任何条款结构的说明文字。") == []
        assert split_into_articles("") == []


class TestEnglishArticles:
    """英文 "Article N" 切分。"""

    def test_article_split(self):
        text = (
            "Article 4 Definitions\n"
            "Personal data means any information relating to an identified or identifiable natural person.\n\n"
            "Article 9 Processing of special categories of personal data\n"
            "Processing of personal data revealing racial or ethnic origin shall be prohibited."
        )
        articles = split_into_articles(text)
        assert len(articles) == 2
        assert articles[0]["article_number"] == "Article 4"
        assert articles[1]["article_number"] == "Article 9"
        assert "special categories" in articles[1]["title"]


class TestLongArticleSplit:
    """超长条款二级切分。"""

    def test_long_article_split_into_parts(self):
        # 构造一条远超 800 字的条款（多段落）
        paragraphs = "\n".join(f"第{i}款 内容。" + "条例要求处理者落实安全措施。" * 10 for i in range(20))
        text = f"第五条 安全义务\n{paragraphs}"
        articles = split_into_articles(text)

        assert len(articles) >= 2, "超长条款应被二级切分为多个片段"
        # 全部片段共享同一个条款号（证据引用不受影响）
        assert {a["article_number"] for a in articles} == {"第五条"}
        # 每个片段都不超过长度上限
        assert all(len(a["content"]) <= MAX_ARTICLE_LEN for a in articles)
        # 拼接后信息不丢失（去重空格差异前的片段总长度应接近原文）
        total = sum(len(a["content"]) for a in articles)
        assert total >= len(text) - 20  # 允许少量分隔符差异

    def test_short_article_not_split(self):
        text = "第六条 合法性\n处理应具备合法性基础。"
        articles = split_into_articles(text)
        assert len(articles) == 1
        assert len(articles[0]["content"]) <= MAX_ARTICLE_LEN
