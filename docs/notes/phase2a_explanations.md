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
