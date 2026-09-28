"""RAG 检索增强模块：Embedding、条款切分、向量存储与入库。"""

from app.rag.chunking import split_into_articles
from app.rag.embeddings import (
    ApiEmbeddingProvider,
    EmbeddingError,
    LocalEmbeddingProvider,
    embed_texts_with_fallback,
    get_embedding_provider,
)
from app.rag.ingestion import ingest_regulation_text, parse_upload_to_text
from app.rag.retrieval import (
    LocalVectorStore,
    PgVectorStore,
    get_vector_store,
    index_chunks,
    rebuild_local_store_from_db,
)

__all__ = [
    "ApiEmbeddingProvider",
    "EmbeddingError",
    "LocalEmbeddingProvider",
    "LocalVectorStore",
    "PgVectorStore",
    "embed_texts_with_fallback",
    "get_embedding_provider",
    "get_vector_store",
    "index_chunks",
    "ingest_regulation_text",
    "parse_upload_to_text",
    "rebuild_local_store_from_db",
    "split_into_articles",
]
