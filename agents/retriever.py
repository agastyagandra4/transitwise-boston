import json
from sentence_transformers import SentenceTransformer

_model = None


def get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def embed(text):
    return get_model().encode(text, normalize_embeddings=True).tolist()


def search_policies(conn, question, k=4):
    vec = json.dumps(embed(question))
    rows = conn.cursor().execute("""
        SELECT source, chunk,
               VECTOR_COSINE_SIMILARITY(embedding, PARSE_JSON(%s)::ARRAY::VECTOR(FLOAT, 384)) AS score
        FROM TRANSITWISE_DB.RAG.POLICY_CHUNKS
        ORDER BY score DESC
        LIMIT %s
    """, (vec, k)).fetchall()
    return [{"source": s, "chunk": c, "score": round(sc, 3)} for s, c, sc in rows]