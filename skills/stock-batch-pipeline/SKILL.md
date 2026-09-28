---
name: "stock-batch-pipeline"
description: "Generate→QA→upscale→metadata→stage new AI illustration batches for 123RF and Dreamstime contributor accounts, and submit them for review. Use for any stock-platform batch production."
---

# Stock Batch Pipeline (123RF + Dreamstime + Adobe Stock)

> 2026-09-26: user ordered daily cadence on ALL platforms. Weekly cron
> retired; `stock-batch-daily` runs every morning and now stages Adobe
> batches too (`files/adobe-stock-batch-NN/`), uploaded by
> `adobe-stock-review-watch`.

End-to-end playbook for producing new AI illustration batches and getting them
into review on 123RF and Dreamstime. Code lives in
`~/workspace/stock-batch-pipeline/` (topics, generation, QA, metadata);
per-batch outputs in `batch-NN/`.

## Pipeline stages

1. **Topics** (`topics_batchNN.py`): 15–25 concepts. Style = painterly
   semi-realistic illustration (batch-04 proven; flat vector was the
   quality-rejection magnet). Dedup every title against batch-01..04
   `metadata.csv` titles AND the rejection blacklist
   (`~/workspace/goals/adobe-stock-ai-image-side-income/hidden_files/rejection-analysis.md`):
   no abstract backgrounds, no AI-brain/tech light trails, no autumn forests,
   no home office, no piggy bank/coins, no icon sets, no surreal giant teacup.
   One theme max 2–3 images, compositions clearly different.
2. **Generate** (`gen_flux.py` + `run_batchNN.py`): fal.ai FLUX.1 dev via the
   **SYNC** endpoint `POST https://fal.run/fal-ai/flux/dev` with **top-level**
   fields (no `{"input"}` wrapper — it 422s). Do NOT use the queue API for
   flux/dev: fal truncates the 3-segment id, returns phantom COMPLETED
   (inference_time < 1s, $0) and the request 404s. Retry with backoff (8s×n);
   sync drops under load but failed attempts cost $0.
   Size 1664×1104 (3:2, 1.84MP → billed 2MP → **$0.05/image**).
   **Budget iron rule: stop the run if projected total would exceed $2.**
   Test one image first on any new endpoint/params.
3. **Technical QA** (`qa_tech.py`): full decode check, min 1200×800, aspect
   ratio within 2% of 3:2 (FLUX sometimes returns wrong ratio → center-crop),
   then Lanczos upscale to **3328×2208 (7.35MP)**, sRGB JPEG q95, RGB.
   Final must be ≥6MP (123RF hard floor) and <30MB.
4. **Visual QA** (human/agent eye, every image): no gibberish text, no logos/
   brands, no real people, natural anatomy, no new artifacts after upscale.
   Regenerate failures (one variable at a time).
5. **Metadata** (`metadata.py` → `build()`): writes `metadata.csv`,
   `meta20.json` (123RF fill-script shape), `dreamstime-meta.csv`.
   - Dreamstime IRON RULE: category MUST be `Illustrations & Clipart >
     AI-generated` and description MUST contain AI disclosure
     ("AI-generated illustration of … Created with artificial intelligence."),
     else instant refuse (batch-03 lesson, 2026-09-21).
   - 123RF IRON RULE: select **AI Generated Images** category in portal;
     ≥6MP; no real people/landmarks/brands; no near-duplicates.
   - Description pattern (123RF): `{title}. A painterly digital illustration.`
6. **Stage**: scp finals to Pi outbox:
   - Dreamstime: `/config/ftp-runner/outbox/dreamstime/` (+ `meta` json/csv
     alongside or in the batch dir; browser agent reads from VM path)
   - 123RF: `/config/ftp-runner/outbox/123rf/` and copy `metaNN.json` to
     `/config/123rf-browser/metaNN.json` on the Pi.
   The Pi FTP runner (every 15 min) uploads Dreamstime automatically;
   123RF upload has gone via browser file-input (`upload1.py` pattern).
7. **Submit (browser delegation — generic subagents cannot do this)**:
   - Dreamstime: files land in Unfinished/Uploads → fill title/description/
     keywords/category per `dreamstime-meta.csv` → submit for review.
     Resubmit flow (refused files): re-upload same file + associate from the
     refused item's Resubmit action (FTP cannot resubmit).
     Portal automation (2026-09-24 proven): title `#title`, description
     `#description`, keywords via `jQuery('#keywords').importTags(csv)` (DO
     NOT click old tag remove links — they navigate away). AI checkbox
     `#js-af_ai_contributor` (Generative AI category default). Save via
     `#js-savededits` (click inner button coords). Submit via "Submit
     commercial" text (re-read coords after scroll). Verify in Under review
     tab (JS pager: `input.changepage` + Enter). Scripts:
     `/config/pi-browser/dt_b05_batch*.py` (to be formalized).
   - 123RF: FTP to `AI images` dir → portal: Upload content → AI Images →
     "Upload via FTP" → Upload Queue → "Refresh FTP" → "Proceed" (tick
     agreement) → files appear in Draft → fill title/desc/keywords per
     `metaNN.json` → submit. **FTP alone is NOT enough** — the portal
     "Upload via FTP" claim step is mandatory (2026-09-24 lesson).
     Verify via API: `GET /apicore-contributors/review_images?page=1&limit=100&status=all&content_type=image_ai`
     (returns filename, oldFilename, approval.category). Monitor script:
     `/config/123rf-browser/rf_b05_monitor.py`.
     Verify PENDING count in portal after submit.
   - Verify EVERY file shows in-review/pending in the portal before calling
     it done. Never delete staged files. Never trigger email verification.
     Stay in contributor areas; do not touch tax/KYC.

## Unit tests (iron rule)

New code ships with `test_*.py` + pytest: core logic, boundary conditions,
regression tests. Bug fix = reproduction test first, then fix.
Run: `/tmp/pytest-venv/bin/python -m pytest test_pipeline.py -q`
(venv has pytest+pillow; system python is PEP-668 locked).

## Daily auto-iteration cron

Owner: goal_709d7919ac5f. The cron runs daily (08:00 ET, `stock-batch-daily`),
does stages 1–6 (generate→QA→stage), cost cap $2/day, then reports "staged,
needs browser submission" — the main agent arranges browser delegation on
delivery. Notify the user ONLY on: submit failure, review rejections (with
reasons), or cost/blocker anomalies. A concise daily update is delivered
every run (batch #, files per platform, cost, staging state, key learning).
Review outcomes feed back into the next batch's topic selection
(learnings-first: check 123RF/Dreamstime/Adobe review states before locking
topics). Submission routing: 123RF via `123rf-upload-watch` (2h); Dreamstime
via `dreamstime-review-watch` (10:19, fills metadata + submits Unfinished
files, automated 2026-09-26); Adobe via
`adobe-stock-review-watch` (09:49 upload+submit step, generalized 2026-09-26
to scan `files/adobe-stock-batch-*/`).

## Cost ledger

- 2026-09-24 batch-05: 20 images @ $0.05 = ~$1.00 (+ test $0.025). NOTE:
  exact billed spend unverified — a pre-fix download-truncation bug re-ran
  paid POSTs that the old `cost.json` never recorded. Never quote ~$1.175
  as exact for batch-05. From batch-06 on, `gen_flux` appends EVERY paid
  POST to `batch-NN/src/cost.jsonl` immediately; `ledger_total()` is the
  exact spend and `run_batch.py`'s budget guard reads it.
- FLUX.1 dev: $0.025/MP, rounded UP to nearest MP.

## Pit log (append, don't fork)

- 2026-09-24: download failure used to re-run the paid POST (double-bill).
  Fixed: `generate()` = `request_image_url()` (paid, once) +
  `download_with_retries()` (reuses the returned URL, never re-POSTs).
  Paid calls are ledger-recorded before the download starts, so accounting
  is exact even when a download fails. Regression tests: norepost, ledger
  on failed download, ledger totals.
- 2026-09-24: `run_batch05.py` generalized into `run_batch.py --batch NN`
  (dynamic `topics_batchNN`, `resolve_batch`, ledger-backed Budget). Old
  per-batch drivers stay as historical records; use `run_batch.py` for
  batch-06+.
- 2026-09-24: queue API unusable for `fal-ai/flux/dev` (id truncation →
  phantom COMPLETED). Use sync endpoint, top-level fields.
- 2026-09-24: dedup checker caught b05-01 vs b03-02 (turkey table 0.54) and
  b05-15 vs b04-07 (pine/red/snow 0.50) — reworked both before generating.
  Keep threshold 0.45.
- 2026-09-27 batch-07 daily run (20/20, $1.05/$2.00 ledger-exact, gen all OK
  on first pass): visual QA found corner signatures on 3/20 despite the
  "no signature" prompt suffix (b07-05, b07-14, b07-15 — FLUX 2 Flex adds
  them ~15% of the time). b07-05 and b07-15 cropped to 3026x2008 (6.08MP)
  / 3116x2068 (6.44MP); b07-14 crop would have dropped below 6MP, so
  regenerated with a new seed (+$0.05). Rule confirmed: crop corner margins
  if tiny AND the result stays >=6MP, else regenerate one variable (seed).
- 2026-09-27: dedup corpus fix — `metadata.py` `_load_prior_titles()` now
  includes batch-05 (topics module) and batch-06 staged files, documented
  batch-01..06. The old `test_all_batch05_topics_pass_dedup` assumed b05
  was NOT in the corpus, so it failed against itself; test now excludes b05's
  own titles (priors = batches 1–4). Also caught real collisions pre-gen:
  b07-17 vs b04-02 (christmas gift hands 0.45 → title reworked).
- 2026-09-27: finalize_batch.py does NOT cover the b07-14-class rework:
  re-running it re-upscales src→final and destroys corner crops. For
  post-finalize rework, copy final→stage dirs and rebuild metadata manually
  (see 2026-09-27 run log). Consider extending finalize_batch with a
  --metadata-only mode.
- 2026-09-27: Pi SSH as root — `pihome` alias lives in
  /home/hatch/.ssh/config, which root's ssh does NOT read. Use
  `ssh -F /home/hatch/.ssh/config pihome` (or set HOME=/home/hatch).
- 2026-09-27: stage_to_pi.sh uses bare `ssh pihome` and would fail for a
  root exec the same way; worked around with -F this run.
- 2026-09-28: batch-08 rerun (20/20, $1.00/$2.00 ledger-exact, all 20 OK on
  first pass): visual QA caught tiny gibberish corner marks on 4/20
  (b08-11, b08-13, b08-17, b08-20) — corner-signature rate 20% vs 15% in
  batch-07; FLUX 2 Flex faint bottom-edge marks are now the norm, not the
  exception. All four fixed by cropping 140px off the bottom (3328x2068 =
  6.88MP, still >=6MP) directly on final/ + both stage dirs (never re-run
  finalize_batch after crops — it destroys them). Crop script ran on 3
  copies per file; visually verified the mark was gone on one sample corner
  zoom. Zero regenerations needed this run.
- 2026-09-28: `stage_to_pi.sh 08` bug — `printf "%02d" "08"` treats "08" as
  octal → "invalid octal number", silently producing BID=00 and staging
  nothing. Fixed with `$((10#$B))` (arithmetic-expansion base-10; note
  printf %d itself does NOT accept the 10# prefix). Regression test
  `test_stage_to_pi.py` covers 05/08/09/10 → correct zero-padded BID.
  Lesson: any batch-08+ staging must go through the fixed script; batch
  numbers 08/09 would have silently broken every prior string-only script.
