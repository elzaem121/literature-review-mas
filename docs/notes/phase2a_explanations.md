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

## Step 3 — Phase 1 adapter, run, score, checks and sync

Step 2 could score saved outputs; this step makes the outputs. Nothing in `src/` changed. Everything new is under
`eval/harness/`, plus two Makefile lines of targets and `eval` added to the lint step in CI.

**The adapter.** `adapters/phase1.py` is the only harness file that imports the pipeline. It wraps the Phase 1
code in the four harness calls and returns only harness record types. `search` calls the same function the graph's
search node calls. `screen` calls the graph's own `screening_node` with a state built from the topic, so the
criteria formatting is the node's, and it maps the node's four buckets back to one record per paper, in input order
(it stops if the node returns a different set of papers). `retrieve` does what the document-processing node does,
but in memory: chunk the frozen page text, embed it, store it in an in-memory repository, and run the same
per-field retrieval. The pipeline's retrieval returns only text, so the adapter looks each text up in the chunk
list to find its page and position; when the same text occurs twice it takes the first. `extract` calls the
pipeline's extraction function and reads a status out of v1's free text: an empty value, or one that starts with
"not specified", "not explicitly specified", "not mentioned" or "not stated", or is exactly "no empirical dataset",
is `not_found`; anything else is `found`. A failed extraction call (an OpenAI or Instructor error) is saved as an
error on that paper. Any other exception is a bug and stops the run.

**The run.** `python -m eval.harness.run` (or `make eval-run`) does these things in order. It refuses to start unless
`REPOSITORY_BACKEND=memory`, so it can never touch the paper library. It asks Ollama which models it has and stops
by naming the missing one. It screens the 60 screening-set papers twice and times each pass, then retrieves and
extracts the six extraction-gold papers whatever the screener decided about them. The page text is checked against
the PDF hash in the gold file first. It then asks Ollama again. If that fails, or a failed call's error text says
"connection error", "timed out" or "connection refused", the run is marked `incomplete`: its outputs are saved
with the reason, but it is not scored, because an Ollama outage must not look like a wrong answer. A complete run
is scored at once and writes `eval/results/<run_id>.json`. The outputs go to `<EVAL_DATA_DIR>/outputs/<run_id>/`,
together with a provenance file (models, Ollama digests, prompt versions, chunker, top-k, concurrency, git commit,
snapshot dates). The run ends by reminding you to run `make eval-sync`.

**Scoring on its own, and the error list.** `python -m eval.harness.score <run_id>` re-scores a saved run, so a
corrected gold label needs no model call. It writes the results file again and also `errors.md` next to the saved
outputs, a list of every wrong output: gold includes the model missed (with the count of those it called
`uncertain`, which is backlog #37), gold excludes it did not exclude, top-10 search results that are not gold
includes, gold quotes that were not in the top five chunks (with the pages that were retrieved), and gold `found`
fields the model reported as not found. The test checks that scoring twice gives the identical results file.

**The other commands.** `ollama_check.py` talks to Ollama's own API, not the OpenAI one: it lists the pulled models
and returns their digests for the provenance. `truncation_check.py` picks the extraction-gold paper with the most
retrieved text, sends its real extraction prompt to Ollama, and compares the prompt token count Ollama reports with
the count from the model family's own tokenizer. If Ollama's count is more than 5% lower, it reports truncation.
`sync.py` commits everything in the data folder and pushes it to the private backup repository; the test uses a
local bare repository as the backup.

**The mix exception.** The design says a topic that cannot reach 8–12 gold includes and at most 4 uncertain papers
may record why in the gold file. `validate` now reads an optional `mix_exceptions` entry in
`eval/gold/v0/provenance.json` (topic id to reason). A topic that misses the mix but has a reason gives a warning
that quotes the reason; without one it is still an error. The exception covers only the include and uncertain
counts, not the set size of 20, and an exception for a topic that has no gold, or with an empty reason, is itself an
error. `validate` therefore now returns both lists, errors and warnings, instead of one list.

**Tests.** A dry run on the fixture gold set uses the fake LLM, the fake embedder and a temporary data folder. The
fake screener is scripted per paper and per pass, so every expected number (the gold-by-model table, recalls, hard
errors, the two flips, precision, retrieval recall, field status) is worked out by hand in the test. Other tests
cover the adapter's mapping and status phrases, the Ollama messages, the incomplete-run paths, the error list, the
truncation arithmetic and the sync. Changing the "first chunk wins" rule, the infrastructure-error check or the
set of caught extraction errors makes a test fail.
