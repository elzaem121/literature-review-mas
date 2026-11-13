# Comprehension Report — Stage 6

**Target:** `docs/plan_v2.md` — FeatureRange 1-200, DetailedRange 201-294
**Reviewer:** `egm-comprehension` (completed). It read the plan alone, with no context files.

## What this proposes

The plan rebuilds a research assistant for Master's and PhD students as a chat application. A user asks about a research topic. A router decides whether to answer from the conversation so far, answer from a stored library of papers, start a new search, or ask the user to clarify. A new search runs a pipeline: find open-access papers in OpenAlex, screen them against the review's criteria, retrieve passages, extract a set of fields, and store the results. The pipeline has two bounded retry loops: one searches again when too few papers pass screening, and one extracts again for fields that came back empty. The outputs are cited answers, an evidence table where every cell links to its source passage and page, exports (CSV/Excel, BibTeX), a screening log, and a research summary.

Everything is stored in one Postgres database with pgvector, which also holds the LangGraph conversation checkpoints. Paper data is shared across users; reviews, screenings and chats are private to each user. All model access goes through one factory, `get_llm(role)`, which picks a model per role (local Ollama by default, the Groq free tier for summaries and for the judge model). An LLM-as-judge evaluation harness measures each component. The system deploys to a local Kubernetes cluster. Work happens in phases 0 to 5, each ending with a working system and a git tag, with evaluation starting at Phase 2. The budget is free tools only and the hardware is a 16 GB MacBook Air.

## How the existing system works, per this document

The current system (v1) takes a research question and criteria, runs for about 5 minutes, and returns a table of extracted data per paper. It is a fixed, straight-line LangGraph pipeline: search, then screening, then PDF processing with RAG, then extraction. FastAPI runs the jobs in the background and Streamlit polls for results. Vectors live in an in-memory FAISS index and the model is a 7B code model on Ollama. Nothing persists: every run starts from zero and a restart loses job state. RAG is basic, there is no automated evaluation, there are almost no tests, and there is no CI.

## Findings

**1. Major: the set of extracted fields is never stated** (lines 8, 32, 41, 89-91, 125, 135)
The evidence table is a core output, and extraction plus Loop 2 are built around "fields." Yet the document never says which fields are extracted, how many there are, or where they are defined. Line 41 makes custom fields per review a non-goal, so there must be a fixed set, and the product is meant to work in any domain (line 10). A new reader cannot tell what columns the evidence table has or what a "field" is in Loop 2. Either list the fields or link to where they are defined.

**2. Major: the difference between `empty` and `not_reported` is undefined** (lines 89-91, 125)
Loop 2 runs only on `empty` fields, so this distinction decides when the loop runs. The document doesn't say how the extractor chooses `not_reported` ("the paper does not contain this") rather than `empty` ("we failed to find it") on the first pass. It also leaves open whether "empty" means a failed extraction or a value the model judged to be absent. Without this, the loop's trigger can't be understood.

**3. Major: the router has four routes, but the architecture shows three targets** (lines 28, 51-53, 76, 79)
The router can return `context | library | new_topic | clarify`. The diagram shows only Context, Library QA and Pipeline. The reader has to guess that `new_topic` maps to Pipeline. `clarify` has no node and no described behaviour: does it trigger `interrupt()`, or just reply with a question? Line 79 also describes the `library` route falling back to a search suggestion, but doesn't say which route handles the user's "yes."

**4. Major: the lifecycle of a "review" and how it relates to conversations and the library is unclear** (lines 115-125, 64)
`reviews` holds a question and criteria, `conversations` links a thread to a review, and `extractions` are shared and carry no `review_id`. The document never says:
- when a review is created (on `new_topic`?) or where its criteria come from in a chat flow;
- whether one conversation can span several reviews;
- how `GET /reviews/{id}/table` builds a per-review evidence table from shared extractions (presumably the papers this review's screening included, but that is not stated);
- how "Library QA" chooses between the user's own reviews and the shared library.

The privacy model in line 115 depends on these answers.

**5. Major: the path a paper takes from OpenAlex to stored chunks is not described** (lines 17, 53, 101, 123-124, 129)
v1 had an explicit "PDF processing" step. The v2 pipeline (search, screening, retrieval, extraction, store) has no download or chunking step, even though line 129 says each paper is downloaded and chunked once. The reader can't tell:
- what screening reads (title and abstract? The `papers` table has no abstract column);
- when the PDF is fetched relative to screening;
- what happens when an open-access paper has no usable `pdf_url`.

**6. Major: the judge-strength rule conflicts with the model configuration** (lines 147-148, 174, 181)
Line 181 says the judge model must be stronger than the system model. But summaries are produced by `groq llama-3.3-70b` and judged by the same `groq llama-3.3-70b` (line 174 evaluates summaries for faithfulness). Either the rule has an exception that isn't stated, or the configuration contradicts it.

**7. Major: "EGM cycle" and "drift report" are undefined** (line 286; also "drift-free" on line 262)
EGM is a project-specific acronym with no definition or link. "Drift report" and "drift-free" assume the reader knows that process. Working rule 3 can't be followed without this. A related point: rule 4's "agent session" means an AI coding-assistant session, but readers can easily mistake it for the system's own LangGraph agents. One sentence would clear up both.

**8. Major: key inputs to Phase 2 are only named, not described** (lines 208, 223-227)
"Gold dataset v0," "three test topics" and "the baseline" are named but not described. The reader doesn't know what the gold dataset labels (relevant papers? screening decisions? expected extracted values?) or what the three topics are. Pointing to `docs/eval_notes.md`, which is marked as a draft, is acceptable as a link. But the plan should say in one line what the dataset contains, because Phase 2's exit criterion (line 238) depends on it.

**9. Nit: overlapping version labels** (lines 2, 14, 39, 205-260)
"v1" means the old codebase, "v2" means this plan and branch, and the tags v0.1 to v1.0 are milestones within v2. "Non-goals (until v1.0)" appears right after "Current state (v1)," which reads as a contradiction until you reach section 10. Add one sentence on the version scheme near the top.

**10. Nit: "CAG" is not expanded** (line 158)
The bullets below it explain the idea well enough, but the acronym itself (presumably cache-augmented generation) is never spelled out.

**11. Nit: the full-paper-versus-chunks strategy reads as both decided and untested** (lines 163, 235, 280)
Section 7.1 states "full paper if it fits, chunks otherwise" as the design. Phase 2 lists it as an experiment still to run, and the Risks table says "measure before adopting." Mark it as provisional in 7.1.

**12. Nit: phrasing in the Phase 2 benchmark item is unclear** (line 226)
"No tool calling" could mean the benchmark skips tool calling, or that the system doesn't use tool calling at all.

**13. Nit: the reason for running only a CI subset is unclear** (line 187)
"CI runs a small subset on every merge (free-tier limits)": the reader has to infer that the parenthetical explains why only a subset runs.

**14. Nit: minor unexplained references**
- "PRISMA-style" (line 34) has no link. Most target users will know it, but other readers may not.
- "Fork repository" (line 206) doesn't say what is forked from what.
- The router's "threshold" (line 79) has no value or source. That is acceptable at plan level, but it should say "to be set in the Phase 3 design."

## Overall

Neither range has a Blocker; I could paraphrase every section. The FeatureRange explains the system's shape well: layers, model roles, persistence and evaluation approach. Its gaps are in how the parts connect: what gets extracted (1, 2), how routes map to graph nodes (3), how reviews, conversations and the shared library relate (4), how a paper moves from search to chunks (5), and the judge-model contradiction (6). The DetailedRange is clear apart from the undefined process terms (7) and the Phase 2 evaluation inputs that are only named (8).
