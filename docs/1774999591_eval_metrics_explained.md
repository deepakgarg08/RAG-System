# Evaluation Metrics Explained — Riverty RAG Contract Review

**Created:** 2026-04-01  
**Feature branch:** `betterment`

This document explains every metric that appears in the evaluation harness output
(`python tests/eval/run_eval.py`). Each section covers what the metric measures,
how it is computed, and what a good or bad value looks like.

---

## Quick Reference Table

| Column in output | Full name | Modes | What it measures |
|-----------------|-----------|-------|-----------------|
| `C-Hit` | Contract Hit | Mode 2 | Did the answer name the right contract? |
| `Kw-Hit` | Keyword Hit | Mode 1, 2, 3 | Did the answer contain the expected clause keywords? |
| `AbsKw` | Absent Keyword Pass | Mode 1 | Did the answer correctly NOT mention forbidden phrases? |
| `Cmp-Hit` | Comparison Hit | Mode 3 | Did the answer make the right comparison point? |
| `P@K` | Precision at K | Mode 2 | Of the K retrieved chunks, what fraction were relevant? |
| `R@K` | Recall at K | Mode 2 | Of all relevant chunks, what fraction did the retriever find? |
| `MRR` | Mean Reciprocal Rank | Mode 2 | How high up was the first relevant chunk in the ranked list? |
| `Faith[src]` | Faithfulness | All | Is the answer grounded in the retrieved context? |
| `Lat` | Latency | All | How many seconds did the full query take? |

---

## Binary Hit Metrics

### C-Hit — Contract Hit (Mode 2)

**What it measures:** Whether the RAG system's answer correctly names the contract(s)
that the question is about.

**How it works:**  
The ground truth stores the expected contract filename stems (e.g. `contract_missing_gdpr`).
The evaluator checks if the answer contains:
- the full stem (e.g. "contract_missing_gdpr"), OR
- any meaningful token from it (e.g. "missing", "gdpr") — tokens shorter than 4 characters
  are ignored to skip noise words like "the", "pdf".

```
Expected: ["contract_missing_gdpr"]
Answer:   "The contract_missing_gdpr.pdf does not include..."
Result:   PASS  ✓
```

**Why it matters:** If the RAG system retrieves the wrong document, the answer is
built on irrelevant evidence — even if it sounds plausible. Contract Hit is the
first sanity check: does the system know *which* contract to look at?

**Good value:** PASS (ideally 100% across all questions)  
**Bad value:** FAIL — the system either hallucinated a contract name or retrieved
from the wrong document.

---

### Kw-Hit — Keyword (Clause) Hit (Modes 1, 2, 3)

**What it measures:** Whether the answer contains at least one of the expected
keywords for the clause being tested.

**How it works:**  
The ground truth stores a list of expected keywords for each question
(e.g. `["15 days", "fifteen", "written notice"]`).
The evaluator does a case-insensitive substring search — if any keyword is found
anywhere in the answer, it's a PASS.

```
Expected keywords: ["15 days", "fifteen", "15"]
Answer:   "Either party may terminate with fifteen (15) days written notice."
Result:   PASS  ✓  (matched "fifteen")
```

**Why it matters:** Contract Hit confirms the right document was found;
Keyword Hit confirms the right *clause content* was extracted. A system can
name the right contract but still get the clause content wrong.

**Good value:** PASS  
**Bad value:** FAIL — the model found the right document but described the wrong
clause, or paraphrased it so heavily that none of the expected terms appear.

---

### AbsKw — Absent Keyword Pass (Mode 1 only)

**What it measures:** The *negative* — whether the answer correctly avoids stating
things that should NOT be true.

**How it works:**  
The ground truth stores `expected_absent_keywords` — phrases that must NOT appear
in the answer (e.g. for a contract with NO GDPR clause, "gdpr compliant" should
be absent).  
PASS means the answer correctly avoids all those forbidden phrases.
FAIL means the model hallucinated something that isn't in the document.

```
Question:  "Is this contract GDPR compliant?"
Document:  has no GDPR clause
Expected absent: ["gdpr compliant", "complies with gdpr", "2016/679"]
Answer:    "This contract does not include a GDPR clause."
Result:    PASS  ✓  (none of the forbidden phrases present)

Bad answer: "Yes, this contract is GDPR compliant."
Result:     FAIL  ✗  (contains "gdpr compliant" — hallucination)
```

**Why it matters:** Standard RAG evaluation only checks what the model *did* say.
AbsKw checks what it *didn't* say — important for legal review where falsely
asserting a protection clause exists could be dangerous.

**Good value:** PASS  
**Bad value:** FAIL — the model is hallucinating protections or clauses that don't
exist in the document.

---

### Cmp-Hit — Comparison Hit (Mode 3 only)

**What it measures:** Whether the answer makes the correct comparison between the
uploaded contract and the database contracts.

**How it works:**  
The ground truth stores `expected_comparison_points` — short phrases describing what
the comparison should conclude (e.g. "contract_missing_gdpr is similar", "stronger
than weak termination contracts").  
At least one comparison point must appear in the answer for a PASS.

```
Expected comparison points: [
    "similar to contract_gdpr_strict and contract_unlimited_liability",
    "stronger than weak termination contracts"
]
Answer: "The uploaded contract's termination clause is similar to contract_gdpr_strict..."
Result: PASS  ✓
```

**Why it matters:** Mode 3 is the most sophisticated mode — it must not just retrieve
facts but *reason across documents*. Cmp-Hit checks whether that cross-document
reasoning reaches the right conclusion.

---

## Information Retrieval (IR) Metrics

These three metrics measure the quality of the **retriever**, independently of the
LLM answer. They use the `/api/eval/retrieve` endpoint which returns the raw ranked
chunks before the LLM sees them.

Relevance is defined at the `(source_file, page_number)` level — each contract page
contains exactly one clause, so page = chunk in this dataset.

---

### P@K — Precision at K (Mode 2)

**What it measures:** Of the K chunks returned by the retriever, what fraction are
actually relevant to the question?

**Formula:**
```
Precision@K = (number of relevant chunks in top-K) / K
```

**Example** (K=8, 1 relevant chunk expected):
```
Retrieved 8 chunks, 1 is relevant → P@8 = 1/8 = 0.125
```

**Interpretation:**
- High P@K → the retriever is precise; most of what it fetches is useful
- Low P@K → the retriever fetches a lot of noise alongside the relevant chunk

**Typical values in this system:** 0.12–0.50 (low because K=8 and most questions
have only 1–3 relevant chunks out of 16 total chunks in the DB — precision is
mathematically bounded by `relevant / K`).

**Good value:** As high as possible; for single-relevant-chunk questions, the
theoretical max at K=8 is 0.125 (1/8).

---

### R@K — Recall at K (Mode 2)

**What it measures:** Of all the chunks that *should* be retrieved, what fraction
did the retriever actually find in its top-K results?

**Formula:**
```
Recall@K = (number of relevant chunks in top-K) / (total relevant chunks for this question)
```

**Example** (K=8, 2 relevant chunks expected, both found):
```
Total relevant = 2, both appear in top-8 → R@8 = 2/2 = 1.00
```

**Interpretation:**
- R@K = 1.00 → the retriever found everything it needed (perfect recall)
- R@K = 0.50 → the retriever missed half the relevant evidence
- R@K = 0.00 → the retriever returned nothing useful

**Why this system shows R@K ≈ 1.00:** The contracts are short (4 pages each, 16
chunks total) and the queries are very targeted. The HybridRetriever with K=8
consistently pulls all relevant chunks from a small corpus. In a larger production
corpus this would be harder.

---

### MRR — Mean Reciprocal Rank (Mode 2)

**What it measures:** How high up in the ranked list does the *first* relevant chunk
appear? This is the metric that best reflects what the LLM actually sees — the
model uses top chunks first, so rank 1 is much better than rank 8.

**Formula:**
```
MRR = 1 / rank_of_first_relevant_chunk

If no relevant chunk appears in top-K: MRR = 0
```

**Examples:**
```
First relevant chunk at rank 1 → MRR = 1/1 = 1.00  (perfect)
First relevant chunk at rank 2 → MRR = 1/2 = 0.50
First relevant chunk at rank 7 → MRR = 1/7 = 0.14  (poor)
No relevant chunk in top-K     → MRR = 0.00
```

**Interpretation:**
- MRR = 1.00 → the most relevant chunk is at the very top of the list
- MRR < 0.25 → the relevant evidence is buried below rank 4; the LLM may
  not reach it before its context window is dominated by noise

**Why MRR varies more than Recall:** Recall tells you *if* the chunk was found;
MRR tells you *where*. A retriever can have perfect Recall but poor MRR if it
finds the right chunk at rank 8 every time.

---

## Faithfulness — `Faith[src]`

**What it measures:** Whether every claim in the generated answer is actually
supported by the retrieved context (the chunks used as evidence). It detects
*hallucination* — when the model invents facts not present in the source text.

**Scale:** 0.0 (completely hallucinated) → 1.0 (fully grounded in context)

**Two backends — `[src]` tag tells you which was used:**

#### `[llm]` — GPT-4o-mini LLM Judge

Used when `OPENAI_API_KEY` is set in `.env`.

The evaluator sends the retrieved context and the answer to GPT-4o-mini with a
structured prompt asking it to rate support on a 0–10 scale:
- **10** — every claim is directly supported by the context
- **5** — mostly correct but makes some unsupported extrapolations  
- **0** — claims directly contradict or are absent from the context

The integer is normalised to 0.0–1.0. This is the more accurate backend.

#### `[embed]` — bge-m3 Cosine Similarity Fallback

Used when `OPENAI_API_KEY` is not set (fully offline, no API cost).

The evaluator embeds the context in 500-character windows and embeds the answer,
then computes the mean cosine similarity between each context window and the answer:

```
faithfulness = mean( cosine_sim(context_chunk_i, answer) for each chunk )
```

High similarity → the answer talks about the same things as the context (proxy
for being grounded in it). This is less precise than the LLM judge but always
works offline and still catches obvious hallucination (a completely off-topic
answer will have low cosine similarity to the contract text).

**Interpreting faithfulness scores:**

| Score | Meaning |
|-------|---------|
| 0.85–1.00 | Answer is well-grounded; all claims supported by context |
| 0.65–0.84 | Mostly grounded; minor unsupported details possible |
| 0.40–0.64 | Partial grounding; model is adding information not in context |
| 0.00–0.39 | Heavy hallucination; answer diverges significantly from context |

*Note:* The `[embed]` backend tends to produce higher scores than `[llm]`
because cosine similarity measures semantic overlap, not logical entailment.
Treat `[embed]` scores as a relative signal, not an absolute faithfulness guarantee.

---

## Latency — `Lat`

**What it measures:** Wall-clock time in seconds from the moment the HTTP request
is sent until the last SSE `[DONE]` token is received.

**Includes:**
- Network round-trip (negligible on localhost)
- Retrieval time (HybridRetriever BM25 + dense + reranker + MMR)
- LLM generation time (the dominant factor)

**Aggregate metrics reported in the summary:**

| Metric | Meaning |
|--------|---------|
| `avg_latency_s` | Simple mean across all successful queries in the mode |
| `p95_latency_s` | 95th-percentile — the latency that 95% of queries are faster than |

**Typical values:**
- Mode 1 (single-doc, no retrieval): 1–3s
- Mode 2 (DB query, full retrieval + LLM): 3–12s
- Mode 3 (compare, full retrieval + comparison reasoning): 4–8s

P95 is more useful than average for catching outlier slow queries that would
frustrate real users.

---

## Reading the Summary Block

```
Mode 2 — Database Query (10 questions)
  Contract Hit Rate  : 100.0%   ← fraction of questions where correct contract was named
  Clause Hit Rate    : 100.0%   ← fraction where correct clause content was found
  Mean Precision@K   : 0.237    ← average P@8 across all 10 questions
  Mean Recall@K      : 1.000    ← average R@8 (retriever found all relevant chunks)
  Mean MRR           : 0.839    ← on average, first relevant chunk is at rank ~1.2
  Mean Faithfulness  : 0.74     ← average faithfulness score (shown only if available)
  Avg Latency        : 5.02s
  P95 Latency        : 8.87s
  Errors             : 0        ← questions that failed with an exception
```

---

## The Results JSON

Each run saves a timestamped file `tests/eval/eval_results_{timestamp}.json`.
Key fields per question result:

```json
{
  "id": "M2Q01",
  "mode": 2,
  "question": "Which contract is missing a GDPR compliance clause?",
  "contract_hit": true,
  "clause_hit": true,
  "precision_at_k": 0.125,
  "recall_at_k": 1.0,
  "mrr": 0.143,
  "faithfulness": 0.68,
  "faithfulness_source": "llm",
  "latency_s": 4.6,
  "answer_preview": "The contract_missing_gdpr.pdf does not include..."
}
```

`faithfulness_source` is `"llm"` or `"embed"` — tells you which backend produced
the faithfulness score so you can weight it appropriately when comparing runs.
