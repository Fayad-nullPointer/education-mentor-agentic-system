import json

from langchain_core.tools import tool
from qdrant_client import QdrantClient, models
from sentence_transformers import SentenceTransformer

from app.core.config import get_settings

try:
    from fastembed import SparseTextEmbedding
    _sparse_model = SparseTextEmbedding(model_name="Qdrant/bm25")
    _hybrid = True
except Exception:
    _sparse_model = None
    _hybrid = False

settings = get_settings()
_dense_model = SentenceTransformer(settings.embedding_model)
_client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)


def _retrieve(query: str, sparse_k: int = 5, top_k: int = 5) -> list:
    dense_k = sparse_k * 2
    dense_vector = _dense_model.encode(query).tolist()

    if _hybrid:
        sparse_embedding = list(_sparse_model.embed([query]))[0]
        sparse_vector = models.SparseVector(
            indices=sparse_embedding.indices.tolist(),
            values=sparse_embedding.values.tolist(),
        )
        results = _client.query_points(
            collection_name=settings.collection_name,
            prefetch=[
                models.Prefetch(query=dense_vector, using="text-dense", limit=dense_k),
                models.Prefetch(query=sparse_vector, using="text-sparse-new", limit=sparse_k),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=top_k,
            with_payload=True,
        )
    else:
        results = _client.query_points(
            collection_name=settings.collection_name,
            query=dense_vector,
            using="text-dense",
            limit=top_k,
            with_payload=True,
        )

    return results.points


def _build_context(points: list) -> str:
    blocks = []
    for i, point in enumerate(points):
        payload = point.payload
        node_data = json.loads(payload.get("_node_content", "{}"))
        text = node_data.get("text", "")
        book = payload.get("book_name", "Unknown")
        page = payload.get("page_label", "?")
        blocks.append(f"[Source {i + 1} | {book}, page {page}]\n{text}")
    return "\n\n---\n\n".join(blocks)


@tool
def rag_search(query: str, top_k: int = 5) -> str:
    """Search a knowledge base of technical books (Statistics, Machine Learning, AI Engineering,
    Search Systems, Computer Science, FastAPI, etc.) using hybrid dense+sparse retrieval.
    Call this with a focused query or sub-query to get relevant document chunks.
    If the user's question is complex, break it into smaller sub-questions and call this
    tool separately for each one (you may call it up to 3 times total).

    Args:
        query: the search query or sub-query to retrieve relevant chunks for
        top_k: number of fused results to return (sparse_k = top_k, dense_k = 2*top_k internally)
    """
    points = _retrieve(query, sparse_k=top_k, top_k=top_k)
    return _build_context(points)
