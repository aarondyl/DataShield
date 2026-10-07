"""全局法规智能层（Global Regulatory Intelligence）。

职责：法规爬取与自动更新、法规结构化、版本管理、变化检测、
Requirement Extraction、Chunking、Embedding、pgvector 向量索引、
Legal Search API 与 Regulation Change Event。

模块只回答「外部监管世界发生了什么」，不触碰任何用户私有数据。

核心原则：
- Version, never overwrite（新版本绝不覆盖旧版本）；
- 能用确定性程序完成的事情不交给 LLM；
- Embedding 是索引，不是数据库；
- 向量索引就绪之前不发布 regulation.change.ready。
"""
