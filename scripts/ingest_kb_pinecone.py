"""Ingest Markdown knowledge-base docs into Pinecone, partitioned by department namespace."""
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from pinecone import Pinecone, ServerlessSpec

KB_ROOT = Path(__file__).resolve().parent.parent / "knowledge_base"
EMBED_MODEL = "text-embedding-3-small"
EMBED_DIM = 1536
CHUNK_SIZE = 600
CHUNK_OVERLAP = 80
BATCH_SIZE = 100

MD_HEADER_SEPARATORS = ["\n## ", "\n### ", "\n#### ", "\n\n", "\n", " ", ""]


def slugify(folder_name: str) -> str:
    return folder_name.replace("_", "-").lower()


def load_env():
    load_dotenv()
    required = ["PINECONE_API_KEY", "PINECONE_INDEX_NAME", "OPENAI_API_KEY"]
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        print(f"ERROR: missing required environment variables: {', '.join(missing)}")
        sys.exit(1)
    return {k: os.getenv(k) for k in required}


def get_index(pc: Pinecone, index_name: str):
    existing = [i.name for i in pc.list_indexes()]
    if index_name not in existing:
        print(f"Index '{index_name}' not found. Creating serverless index (dim={EMBED_DIM})...")
        pc.create_index(
            name=index_name,
            dimension=EMBED_DIM,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1"),
        )
        while not pc.describe_index(index_name).status["ready"]:
            time.sleep(1)
    return pc.Index(index_name)


def chunk_text(text: str, splitter: RecursiveCharacterTextSplitter):
    chunks = splitter.split_text(text)
    return [c.strip() for c in chunks if c.strip()]


def batched(iterable, n):
    for i in range(0, len(iterable), n):
        yield iterable[i : i + n]


def main():
    env = load_env()

    if not KB_ROOT.is_dir():
        print(f"ERROR: knowledge base directory not found at {KB_ROOT}")
        sys.exit(1)

    department_dirs = sorted(p for p in KB_ROOT.iterdir() if p.is_dir())
    if not department_dirs:
        print(f"ERROR: no department subfolders found under {KB_ROOT}")
        sys.exit(1)

    pc = Pinecone(api_key=env["PINECONE_API_KEY"])
    index = get_index(pc, env["PINECONE_INDEX_NAME"])

    embeddings = OpenAIEmbeddings(model=EMBED_MODEL, api_key=env["OPENAI_API_KEY"])
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=MD_HEADER_SEPARATORS,
    )

    total_vectors = 0
    summary = []

    for dept_dir in department_dirs:
        department = dept_dir.name
        namespace = slugify(department)
        md_files = sorted(dept_dir.glob("*.md"))

        print(f"\n=== Department: {department} -> namespace '{namespace}' ===")

        if not md_files:
            print("  No .md files found, skipping.")
            summary.append((department, namespace, 0, 0))
            continue

        vectors = []
        chunk_count = 0

        for md_file in md_files:
            try:
                text = md_file.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                print(f"  WARNING: encoding issue reading {md_file.name}, retrying with latin-1")
                text = md_file.read_text(encoding="latin-1")

            if not text.strip():
                print(f"  WARNING: {md_file.name} is empty, skipping.")
                continue

            chunks = chunk_text(text, splitter)
            if not chunks:
                print(f"  WARNING: {md_file.name} produced no chunks, skipping.")
                continue

            print(f"  {md_file.name}: {len(chunks)} chunks")
            chunk_vectors = embeddings.embed_documents(chunks)

            for i, (chunk, vector) in enumerate(zip(chunks, chunk_vectors)):
                vectors.append(
                    {
                        "id": f"{namespace}::{md_file.stem}::{i}",
                        "values": vector,
                        "metadata": {
                            "text": chunk,
                            "source_file": md_file.name,
                            "department": department,
                        },
                    }
                )
            chunk_count += len(chunks)

        if not vectors:
            print(f"  No vectors generated for '{department}', skipping upsert.")
            summary.append((department, namespace, 0, 0))
            continue

        upserted = 0
        for batch in batched(vectors, BATCH_SIZE):
            index.upsert(vectors=batch, namespace=namespace)
            upserted += len(batch)
            print(f"  Upserted {upserted}/{len(vectors)} vectors into namespace '{namespace}'")

        total_vectors += upserted
        summary.append((department, namespace, chunk_count, upserted))
        print(f"  Done: {chunk_count} chunks / {upserted} vectors confirmed in namespace '{namespace}'.")

    print("\n=== Ingestion Summary ===")
    for department, namespace, chunk_count, upserted in summary:
        print(f"  {department:25s} -> {namespace:25s} chunks={chunk_count:4d}  upserted={upserted:4d}")
    print(f"\nTotal vectors upserted across all namespaces: {total_vectors}")


if __name__ == "__main__":
    main()
