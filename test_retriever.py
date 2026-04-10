from pathlib import Path

from bidintel.rag.retriever import retrieve


def _infer_source_file(chunk: str) -> str:
    text = (chunk or "").lower()
    if "candidate profile: senior consultant" in text or "ayesha rahman" in text:
        return "sample_cv.txt"
    if "selected completed projects" in text or "merchant discount rate (mdr) study" in text:
        return "past_projects.txt"
    if "corporate credentials and compliance documents" in text or "iso 9001" in text:
        return "certifications.txt"
    return "unknown"


def main() -> int:
    queries = [
        "past experience with payment systems",
        "team qualifications and certifications",
        "company registration and ISO certifications",
    ]

    output_sections = []
    for query in queries:
        chunks = retrieve(query, top_k=3)
        source_files = []
        for chunk in chunks:
            source = _infer_source_file(chunk)
            if source not in source_files:
                source_files.append(source)

        section_lines = [
            f'QUERY: "{query}"',
            f"SOURCE FILE: {', '.join(source_files) if source_files else 'unknown'}",
        ]
        for idx in range(3):
            chunk_text = chunks[idx] if idx < len(chunks) else ""
            section_lines.append(f"CHUNK {idx + 1}: {chunk_text}")
        output_sections.append("\n".join(section_lines))

    full_output = "\n\n---\n\n".join(output_sections)
    print(full_output)

    output_path = Path("bidintel/data/outputs/retriever_output.txt")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(full_output, encoding="utf-8")
    print(f"\nSaved retrieval output to: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
