# BidIntel AI — Pipeline Refinements

Three targeted engineering upgrades applied to fix known production failure modes in the analysis pipeline.

---

## Refinement 1 — Layout-Aware PDF Parsing

### Problem

RFPs and compliance documents are dominated by multi-column tables:
evaluation criteria grids, scoring matrices, and submission checklists.
The original extractor (`PyMuPDF` direct text extraction) processes PDFs
in reading order, which interleaves all table rows into a single flat
stream of text. A two-column table like:

| Criterion | Weight |
|-----------|--------|
| Technical approach | 40% |
| Team experience | 30% |
| Price | 30% |

arrives at the LLM as:
> `Criterion Technical approach Team experience Price Weight 40% 30% 30%`

Column relationships are destroyed, making it impossible for the LLM to
associate weights with the correct criteria.

### Root Cause

PyMuPDF's `page.get_text("text")` returns characters sorted by their
bounding-box Y coordinate across the full page width, with no concept
of column boundaries.

### Fix

Replaced the raw text extractor with **`pymupdf4llm`**, a thin wrapper
around PyMuPDF that outputs Markdown. Tables are preserved as GitHub
pipe-table syntax:

```markdown
| Criterion | Weight |
|---|---|
| Technical approach | 40% |
| Team experience | 30% |
| Price | 30% |
```

The RFP chunker was also upgraded: instead of splitting on fixed page
boundaries (which would cut a table header from its rows), it now splits
on **Markdown heading boundaries** (`# `, `## `). Oversized sections are
sub-split on page-break markers. Every table row stays with its column
header in the same chunk.

A fallback to Tesseract OCR is preserved for scanned (image-only) PDFs
that `pymupdf4llm` cannot extract text from.

### Impact

- Compliance matrices arrive at the LLM intact.
- Criterion weights and eligibility thresholds are correctly associated.
- No change to downstream JSON extraction or deduplication logic.

---

## Refinement 2 — Hybrid BM25 + Vector Retrieval

### Problem

The original retriever used only **dense vector search** (cosine
similarity via `all-MiniLM-L6-v2` embeddings stored in ChromaDB).
Semantic similarity works well for conceptual queries ("demonstrate
relevant experience") but silently fails for exact-string requirements:

- Querying `"ISO 27001 certification"` returns chunks about *security
  posture* and *compliance frameworks* — semantically close, but never
  the specific document that contains the exact string `ISO 27001`.
- A bid response that literally states `"We hold ISO 27001 certification"`
  may score as a gap because the retriever returns semantically similar
  but lexically different content.

### Root Cause

Embedding models project text into a continuous semantic space; they have
no special treatment for exact tokens. Short certification names, standard
numbers, and regulatory codes are low-frequency tokens that get washed out
by the surrounding contextual similarity.

### Fix

Introduced **`HybridIndex`** — a dataclass that bundles the existing
`VectorStoreIndex` (ChromaDB) with a plain `corpus: list[str]` for BM25:

```
HybridIndex
├── vector_index  →  ChromaDB (dense embeddings)
└── corpus        →  list[str] (raw chunk text for BM25)
```

At query time the retriever runs both searches and fuses their ranked
results with **Reciprocal Rank Fusion (RRF, k = 60)**:

```
score(doc) = Σ  1 / (k + rank_in_list)
             lists
```

RRF is rank-based, so the incompatible scales of cosine similarity and
BM25 scores never need to be normalised. A document that ranks highly in
either list gets promoted; one that ranks highly in *both* is nearly
guaranteed to appear in the top-k.

The retriever is fully backward-compatible: it accepts a bare
`VectorStoreIndex` and degrades gracefully to vector-only search.

### Impact

- Exact certification names, standard numbers, and clause references are
  reliably retrieved.
- Vector search still handles natural-language criterion queries.
- The external retriever interface `retrieve(query, top_k) → List[str]`
  is unchanged; no call-site changes were required beyond a variable rename.

---

## Refinement 3 — Deterministic Boolean Scoring

### Problem

The LLM was asked to return `matched_signals: List[str]` — free-text
strings echoing which checklist signals it found evidence for. Python
then fuzzy-matched these strings back against the original checklist to
derive `matched` and `gap` sets:

```python
matched_norm = {_normalize_signal(s) for s in llm_matched_signals}
gap_signals  = [s for s in checklist if _normalize_signal(s) not in matched_norm]
```

This introduced two failure modes:
1. **Silent hallucination** — the LLM occasionally rephrased a signal
   slightly, causing it to miss the fuzzy match and be mis-classified as
   a gap even when the signal was evidenced.
2. **Silent omission** — if the LLM omitted a signal from the list
   entirely (token budget, formatting error), there was no way to
   distinguish "not met" from "forgotten".

### Root Cause

`List[str]` forces the LLM to re-generate the signal text, introducing
paraphrase variation. Python then has to reverse-engineer the original
structure from an imprecise echo.

### Fix

Changed the LLM output schema to emit **one explicit boolean per signal**:

```json
{
  "c1": {
    "signals": {
      "Timeline clearly provided": true,
      "Budget breakdown included": false,
      "Team CVs attached": true
    }
  }
}
```

The signal keys are echoed verbatim from the prompt (the LLM is instructed
to use the exact strings). Python derives `matched_signals` and
`gap_signals` by reading the boolean values directly:

```python
matched_signals = [sig for sig, met in signals_map.items() if met]
gap_signals     = [sig for sig, met in signals_map.items() if not met]
# any signal not echoed → gap (catches omissions)
for sig in checklist:
    if sig not in signals_map:
        gap_signals.append(sig)
```

The dead helpers `_normalize_signal()` and `_normalize_matched_signals()`
were removed. WPS arithmetic is unchanged.

### Impact

- `matched` / `gap` derivation is fully deterministic — no string
  normalisation, no fuzzy matching.
- Omitted signals are automatically treated as gaps (conservative, correct).
- LLM instructions are simpler: "return true/false per signal" is clearer
  than "echo the matched signal strings exactly".

---

## Summary Table

| # | Failure mode | Root cause | Fix | New dependency |
|---|---|---|---|---|
| 1 | Table structure destroyed in parsing | PyMuPDF flat text extraction ignores column layout | `pymupdf4llm` → Markdown pipe tables; heading-boundary chunker | `pymupdf4llm >= 0.0.17` |
| 2 | Exact keyword retrieval misses | Dense-only vector search has no exact-token bias | `HybridIndex`: BM25 + vector, fused with RRF (k = 60) | `rank-bm25 >= 0.2.2` |
| 3 | Fuzzy signal matching causes mis-scoring | LLM re-generates signal text; Python fuzzy-matches back | LLM emits `dict[str, bool]`; Python reads booleans directly | — |
