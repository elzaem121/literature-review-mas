# Phase 2a — explanations

Plain-language notes after each core task.

## Step 1 — Search capture and the data-folder setting

The evaluation needs to freeze what the search agent did, so that a later run can be compared with it. Until now
the search agent only printed two things it knew: the "synthetic abstract" (the text it writes to query OpenAlex
with) and whether the model call failed and it fell back to the raw question. Neither was returned. Now
`run_precise_retrieval_cycle` returns them next to `papers`, as `synthetic_abstract` and `fallback_used`. The graph's
search node still reads only `papers`, so the pipeline behaves exactly as before; the golden transcript test passes
without being regenerated. The reason for `fallback_used` is that a search run which fell back is not a fair
baseline, so the gold-set build will throw such a run away and repeat it.

The code that turns one raw OpenAlex record into the paper dict (title, rebuilt abstract, authors, PDF link, venue)
moved out of the loop into a function, `format_openalex_work`, with the same body. Later, the gold-set build will
use it for papers that did not come from the search (the old link list, deeper search results), so the abstract a
human or Claude labels is character for character what the screener will receive. A test pins its output for a
fixture work, and another one covers a work with missing fields.

One new setting, `EVAL_DATA_DIR`, names the local folder for the bulky or full-text eval data (PDFs, page text,
raw run outputs, labeling work files) that must not enter this public repository. It is optional: the normal app
never reads it, and `.env.example` documents it. The eval commands that need it will fail with a clear message
when it is missing; those commands arrive in later steps.

## Step 2 — Harness core

This step builds the part of the evaluation that only does arithmetic on saved files: it reads the gold labels and
the saved outputs of a run and turns them into numbers. It never calls a model and never imports anything from
`src/`, so the same scoring code can judge the Phase 1 system now and a changed pipeline in Phase 2b. Nothing in
`src/` changed in this step.

**The pieces.** `records.py` defines the shapes of everything a run produces (a screening decision, a retrieved
chunk, an extracted field, the run's timings and provenance). Every pipeline version will be wrapped by an adapter
that returns exactly these shapes, and scoring reads only these shapes. `topics.py` loads a topic config (the
question and its yes/no checks) and does two jobs from that one file: it writes the criteria the screener receives,
and it writes the prompt Claude labels with, so the two cannot drift apart. It also holds the one rule that turns
check answers into a decision (any `no` excludes, all `yes` includes, anything else is uncertain), and
`decided_by`, which says whether changing one check's answer could change a paper's decision. The escalation rule
will use that later to find the papers a disputed check matters for. `text.py` holds the small text helpers:
whitespace normalization, title normalization for finding duplicate studies, and `joined_runs`, which glues
neighbouring retrieved chunks back together so a quote that falls across a chunk boundary still counts as
retrieved. The chunker cuts at fixed offsets without overlap, so chunks are joined with nothing in between.

**Gold validation.** `gold.py` loads the gold files and checks them: set sizes and the include/uncertain mix, that
every decision follows from its check answers, that every pool paper is labeled, that no study appears twice, that
the first ten search results are the ones marked as the search set (a dropped duplicate is found again through its
alias), and, when the data folder is given, that every extraction quote is on its page and every page file belongs
to the PDF the gold file names by hash. It returns a list of plain-language problems instead of crashing at the
first one, so a labeling session sees everything that is wrong at once.

**Scoring.** `score()` takes the folder of one run and the gold directory and returns the whole results structure.
Screening is scored on the first pass over the screening set only: the gold-by-model table, include and exclude
recall, hard include/exclude errors, failed calls, and what the model said about gold-uncertain papers. A model
`uncertain` or a failed call counts as a missed include. The second pass is used only to count flipped decisions.
Search precision@10 counts gold includes among the ten frozen results, and a second copy of the same study counts
as not relevant. Retrieval recall asks whether the gold quote is in the chunks retrieved for that field (top five,
neighbours joined). Extraction status asks whether the model reported the field as found. The latency budget is
built exactly as the design says, with the search time taken as the mean of the topics' snapshot runs. A run marked
incomplete is refused, and a run that lacks a record for a gold paper stops with an error naming the paper rather
than being scored as a miss.

**Tests.** The tests use a small made-up gold set in `tests/fixtures/eval/`: two topics with two checks each, small
set sizes passed to the validator, the page text of the two fixture PDFs, and a recorded complete run and a recorded
incomplete one. Every expected number in the scoring tests was worked out by hand from the fixture files, including
the awkward cases (a duplicate in the top results, a quote split over two chunks, a failed call, a hard error).
Mutating the code (a different recall cutoff, a space between joined chunks, a changed decision rule) makes the
tests fail.
