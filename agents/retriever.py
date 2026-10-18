import json
import re
from sentence_transformers import SentenceTransformer

_model = None


def get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def embed(text):
    return get_model().encode(text, normalize_embeddings=True).tolist()


def extract_keywords(text):
    """Find exact facility IDs like 'Elevator 869' or 'Escalator 415'."""
    return sorted(set(m.title() for m in re.findall(r"(?:elevator|escalator)\s+\d+", text, flags=re.I)))


def search_policies(conn, question, k=4, keyword_boost=0.2):
    vec = json.dumps(embed(question))
    keywords = extract_keywords(question)

    boost_sql = " + ".join(["CASE WHEN chunk ILIKE %s THEN %s ELSE 0 END"] * len(keywords)) or "0"
    params = [vec]
    for kw in keywords:
        params += [f"%{kw}%", keyword_boost]
    params.append(k)

    rows = conn.cursor().execute(f"""
        SELECT source, chunk,
               VECTOR_COSINE_SIMILARITY(embedding, PARSE_JSON(%s)::ARRAY::VECTOR(FLOAT, 384)) AS vscore,
               {boost_sql} AS kboost
        FROM TRANSITWISE_DB.RAG.POLICY_CHUNKS
        ORDER BY vscore + kboost DESC
        LIMIT %s
    """, params).fetchall()

    return [{"source": s, "chunk": c,
             "score": round(float(v) + float(b), 3),
             "vector_score": round(float(v), 3),
             "keyword_boost": round(float(b), 3)}
            for s, c, v, b in rows]