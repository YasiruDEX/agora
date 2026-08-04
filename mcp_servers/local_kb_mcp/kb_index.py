"""Local RAG index over the department knowledge base (Markdown under knowledge_base/).

Replaces the old Pinecone-backed pipeline (scripts/ingest_kb_pinecone.py +
mcp_servers/pinecone_kb_mcp): there is no external vector DB here. Chunks are
embedded with OpenAI and kept in a plain JSON cache file on disk
(kb_index_cache.json, next to this module), keyed by a hash of each source
file's content so unchanged files are never re-embedded. At query time the
whole namespace's vectors are loaded into memory and scored with a pure-Python
cosine similarity -- the knowledge base is a few dozen chunks per namespace,
nowhere near large enough to need a real vector database.
"""
import hashlib
import json
import math
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
KB_ROOT = REPO_ROOT / "knowledge_base"
CACHE_PATH = Path(__file__).resolve().parent / "kb_index_cache.json"

EMBED_MODEL = "text-embedding-3-small"
CHUNK_SIZE = 600
CHUNK_OVERLAP = 80
MD_SEPARATORS = ["\n## ", "\n### ", "\n#### ", "\n\n", "\n", " ", ""]


def slugify(folder_name: str) -> str:
    return folder_name.replace("_", "-").lower()


def _merge_splits(splits: list[str], separator: str) -> list[str]:
    """Greedily pack consecutive splits into chunks up to CHUNK_SIZE, re-joined
    with `separator`, carrying CHUNK_OVERLAP characters of trailing context
    from one chunk into the start of the next."""
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    def _flush():
        if current:
            chunks.append(separator.join(current))

    for piece in splits:
        piece_len = len(piece)
        added_len = piece_len + (len(separator) if current else 0)
        if current and current_len + added_len > CHUNK_SIZE:
            _flush()
            # Carry trailing pieces worth ~CHUNK_OVERLAP chars into the next chunk.
            overlap: list[str] = []
            overlap_len = 0
            for prev in reversed(current):
                prev_len = len(prev) + (len(separator) if overlap else 0)
                if overlap and overlap_len + prev_len > CHUNK_OVERLAP:
                    break
                overlap.insert(0, prev)
                overlap_len += prev_len
            current = overlap
            current_len = overlap_len
            added_len = piece_len + (len(separator) if current else 0)
        current.append(piece)
        current_len += added_len

    _flush()
    return chunks


def _recursive_split(text: str, separators: list[str]) -> list[str]:
    if not text:
        return []
    if len(text) <= CHUNK_SIZE:
        return [text]

    sep, rest = separators[0], separators[1:]
    pieces = list(text) if sep == "" else text.split(sep)

    good: list[str] = []
    out: list[str] = []
    for piece in pieces:
        if len(piece) < CHUNK_SIZE:
            good.append(piece)
            continue
        if good:
            out.extend(_merge_splits(good, sep))
            good = []
        out.extend(_recursive_split(piece, rest) if rest else [piece])
    if good:
        out.extend(_merge_splits(good, sep))
    return out


def chunk_text(text: str) -> list[str]:
    chunks = _recursive_split(text, MD_SEPARATORS)
    return [c.strip() for c in chunks if c.strip()]


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _load_cache() -> dict:
    if not CACHE_PATH.exists():
        return {}
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_cache(cache: dict) -> None:
    CACHE_PATH.write_text(json.dumps(cache), encoding="utf-8")


def build_index(openai_client, force: bool = False, log=lambda msg: None) -> dict:
    """(Re)build the local KB index, embedding only files whose content hash
    changed since the last build (unless force=True). Returns the full index
    dict, keyed by namespace, and also persists it to CACHE_PATH.

    Index shape: {namespace: {source_file: {hash, chunks: [{id, text, embedding, department}]}}}
    """
    if not KB_ROOT.is_dir():
        raise FileNotFoundError(f"Knowledge base directory not found at {KB_ROOT}")

    cache = {} if force else _load_cache()
    department_dirs = sorted(p for p in KB_ROOT.iterdir() if p.is_dir())

    for dept_dir in department_dirs:
        department = dept_dir.name
        namespace = slugify(department)
        namespace_cache = cache.setdefault(namespace, {})
        seen_files = set()

        for md_file in sorted(dept_dir.glob("*.md")):
            seen_files.add(md_file.name)
            try:
                text = md_file.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                text = md_file.read_text(encoding="latin-1")
            if not text.strip():
                continue

            file_hash = _content_hash(text)
            existing = namespace_cache.get(md_file.name)
            if existing and existing.get("hash") == file_hash:
                continue  # unchanged, embeddings already cached

            chunks = chunk_text(text)
            if not chunks:
                continue

            log(f"  Embedding {namespace}/{md_file.name}: {len(chunks)} chunk(s)")
            response = openai_client.embeddings.create(model=EMBED_MODEL, input=chunks)
            embeddings = [d.embedding for d in response.data]

            namespace_cache[md_file.name] = {
                "hash": file_hash,
                "chunks": [
                    {
                        "id": f"{namespace}::{md_file.stem}::{i}",
                        "text": chunk,
                        "source_file": md_file.name,
                        "department": department,
                        "embedding": embedding,
                    }
                    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings))
                ],
            }

        # Drop cache entries for files that were deleted from the KB.
        for stale in set(namespace_cache) - seen_files:
            del namespace_cache[stale]

    _save_cache(cache)
    return cache


def load_index() -> dict:
    cache = _load_cache()
    if not cache:
        raise RuntimeError(
            f"No local KB index found at {CACHE_PATH}. Run scripts/build_kb_index.py first "
            "(or let the MCP server build it on startup)."
        )
    return cache


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def search(index: dict, openai_client, namespace: str, query: str, top_k: int = 5) -> list[dict]:
    """Embed `query` and return the top_k highest-cosine-similarity chunks in
    `namespace`, each as {score, source_file, department, text}."""
    namespace_cache = index.get(namespace, {})
    all_chunks = [chunk for entry in namespace_cache.values() for chunk in entry["chunks"]]
    if not all_chunks:
        return []

    query_embedding = openai_client.embeddings.create(model=EMBED_MODEL, input=query).data[0].embedding

    scored = [
        {
            "score": _cosine_similarity(query_embedding, chunk["embedding"]),
            "source_file": chunk["source_file"],
            "department": chunk["department"],
            "text": chunk["text"],
        }
        for chunk in all_chunks
    ]
    scored.sort(key=lambda c: c["score"], reverse=True)
    return scored[:top_k]
