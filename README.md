# BidIntel RFP Analyzer

BidIntel is a Streamlit app and module set for:
- Parsing RFP PDFs into structured fields
- Building a local company knowledge base with LlamaIndex + ChromaDB
- Retrieving evidence chunks for criteria scoring
- Detecting risky "poison pill" clauses
- Calculating WPS across conservative/expected/optimistic scenarios

## Project Structure

`bidintel/ingestion`
- `rfp_parser.py`: RFP extraction with `pdfplumber` + Groq LLM JSON extraction
- `kb_loader.py`: builds a local Chroma-backed `VectorStoreIndex`

`bidintel/rag`
- `retriever.py`: loads persisted index and returns top-k relevant chunks

`bidintel/scoring`
- `criterion_scorer.py`: matches checklist signals and computes deterministic criterion score
- `poison_pill.py`: page-level risky clause detection with keyword + semantic fallback
- `wps_calculator.py`: deterministic WPS and verdict computation

`bidintel/dashboard`
- `app.py`: Streamlit UI to run the full pipeline

## Requirements

Install dependencies:

```bash
pip install -r requirements.txt
```

## Environment Variables

Set at least one embedding provider key and Groq key for LLM tasks:

- `GROQ_API_KEY` (required for parser/scorer/poison-pill semantic checks)
- `OPENAI_API_KEY` (optional, preferred for embeddings via `text-embedding-3-small`)

Embedding fallback:
- If `OPENAI_API_KEY` is available, OpenAI embeddings are used.
- If not, a Groq-based fallback embedding generator is used.

## Run Dashboard

From repo root:

```bash
streamlit run bidintel/dashboard/app.py
```

Then:
1. Upload an RFP PDF
2. Upload company brain files (`.pdf` and/or `.txt`)
3. Submit to execute full pipeline

## Notes

- All LLM calls are constrained to JSON-only outputs and parsed/validated in code.
- Scoring remains deterministic in Python; LLM only identifies evidence matches.
