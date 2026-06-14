# AI Collaboration Log

This is a cleaned, assignment-focused log of how I used Codex while working on the Bhume boundary
take-home. I used AI as a research and coding assistant: to summarize the assignment, inspect the
starter kit, pressure-test strategy, implement a reproducible baseline method, debug environment
issues, and package the submission. I made the key submission choices: focusing on Malatavadi,
optimizing for restraint/calibration, keeping v1 translation-only, and submitting a conservative
method rather than hand-edited geometries.

The raw Codex Desktop session is stored locally at:

```text
C:\Users\phani\.codex\sessions\2026\06\11\rollout-2026-06-11T15-35-20-019eb624-a6cc-7071-a3db-393c7c55530a.jsonl
```

I did not commit the raw JSONL because it contains large amounts of app/tool metadata unrelated to
the take-home. This Markdown file keeps the relevant prompts, decisions, outputs, and commands.

## 1. Understanding the Assignment

**My prompt:** "open and inspect the assignment and tell me what it is"

**How I used AI:** I asked Codex to inspect the hiring site and summarize the actual task before I
started writing code. This helped me avoid guessing from the LinkedIn post.

**AI-assisted findings I used:**

- The problem is geospatial boundary correction: official cadastral plot outlines can be shifted
  relative to real fields visible in satellite imagery.
- Output is `predictions.geojson`.
- Each attempted plot should be either:
  - `corrected`, with a predicted boundary and confidence;
  - `flagged`, keeping the original geometry because the method is not confident.
- Evaluation includes IoU, centroid error, improvement over official position, confidence
  calibration, and restraint.
- Submission requires a GitHub repo, predictions, AI transcripts, and a 5-minute walkthrough video.

**Decision I took from this:** The problem is not "move every plot." The safer framing is "move only
when evidence is strong, otherwise flag."

## 2. Deadline and Scope

**My prompt:** "deadline to submit?"

**How I used AI:** I used Codex to check the submit page and deadline wording.

**Result:** The page later showed a review-batch note: next read Wednesday morning, June 17 IST,
with anything submitted by Tuesday evening, June 16 counted for that batch.

**My prompt:** "they gave two different locations . do we need to do for both?"

**How I used AI:** I asked Codex to interpret the scope.

**Result:** The task allows one village or both. I chose **Malatavadi only** because I already had
that data locally and wanted to put effort into a clear, calibrated method rather than a shallow
two-village attempt.

## 3. Data Inspection and Strategy

**My prompt:** "save these files and explain the strategy"

**How I used AI:** I asked Codex to move the downloaded data into the workspace and inspect the
GeoJSON enough to guide the approach.

**Files saved locally:**

```text
data/raw/input.geojson
data/raw/imagery.tif
data/raw/boundaries.tif
```

**Data summary from inspection:**

```text
features: 2508
village: Malatavadi
bounds lon/lat: [74.320161749, 15.976840411, 74.351155249, 16.000904975]
median map area: 872.45 sqm
area ratio median: 1.002
near ratio 0.9-1.1: 1009 plots
far ratio <0.7 or >1.3: 532 plots
```

**Strategy I adopted:**

- Malatavadi has small, crowded parcels, so confidence and abstention matter.
- Area ratio is useful as a risk signal: if map area and recorded area strongly disagree, placement
  correction may not be the right fix.
- A translation-only first version is reasonable because many errors look like local shifts.
- Use `boundaries.tif` as a rough edge hint, but not as truth.
- Use satellite image gradients as a second signal.
- Penalize large shifts because they can jump to a neighboring field.
- Flag uncertain plots instead of forcing weak corrections.

## 4. Starter Kit Inspection

**My prompt:** "this is the starter kit they gave . inspect"

**How I used AI:** I asked Codex to unpack the starter kit and identify the relevant helper APIs.

**Starter-kit files I used:**

- `CONTRACT.md` for the exact output schema.
- `quickstart.py` for the expected load/predict/score loop.
- `bhume/io.py` for `load()` and `write_predictions()`.
- `bhume/geo.py` for CRS/raster helper functions.
- `bhume/score.py` for local scoring against public example truths.
- `bhume/baseline.py` as a reference baseline, not the final method.

**Decision I made:** Build on the starter-kit helpers instead of reimplementing GeoJSON/GeoTIFF
plumbing. That keeps the work focused on the actual judgment problem.

## 5. Planning the Method

**My prompt:** "plan it"

**How I used AI:** I asked Codex to turn the strategy into an implementation plan, then selected
the important tradeoffs.

**Choices I locked:**

- Scope: Malatavadi only.
- Target: Silver/Gold style attempt.
- Method: translation-only v1.
- Output: all plots get either `corrected` or `flagged`.
- Confidence: only for corrected plots, based on signal strength, margin, shift size, and area
  sanity.
- Priority: calibrated restraint over broad coverage.

## 6. Implementation Assistance

**My prompt:** "PLEASE IMPLEMENT THIS PLAN"

**How I used AI:** I used Codex as a coding assistant to create the reproducible implementation,
wire it into the starter kit, and generate the predictions. This was not hand-edited geometry; the
output comes from code in `solve.py`.

**Files produced with AI assistance:**

- `solve.py`
- updated `README.md`
- `.gitignore`
- `transcripts/README.md`
- `data/12429_malatavadi_chandgad_kolhapur/predictions.geojson`

**Core algorithm in `solve.py`:**

- Load the Malatavadi bundle with `bhume.load()`.
- Convert plot geometries into the imagery CRS so shifts are measured in metres.
- Sample points along each official polygon boundary.
- Normalize two raster signals:
  - boundary-hint intensity from `boundaries.tif`;
  - image-edge strength from `imagery.tif`.
- Search candidate translations up to 20 metres.
- Score each candidate by edge alignment.
- Penalize larger shifts.
- Use area-ratio sanity as a risk factor.
- Accept a correction only when the best shifted outline clearly beats the original.
- Otherwise flag the plot and keep its official geometry.

## 7. Testing, Tuning, and What I Learned

**How I used AI:** Codex helped run the solver, inspect score output, and identify why one version
was too aggressive.

**Environment setup commands:**

```powershell
python -m pip install --user uv
python -m uv sync
```

Workspace-local uv cache used on Windows:

```powershell
$env:UV_CACHE_DIR = ".uv-cache"
python -m uv run solve.py data/12429_malatavadi_chandgad_kolhapur
```

**First full run:**

```text
coverage: 563 corrected, 1945 flagged
public example score:
median IoU pred=0.785 vs official=0.510
improvement=0.275
```

**Issue found:** One public example was already fairly well placed, but the edge signal tempted a
large wrong shift. That was a useful failure: strong local edge evidence is not enough if the move
is too large in a dense village.

**Tuning decision:** I added a restraint rule: shifts over 14 metres require exceptional evidence.

**Final run:**

```text
coverage: 305 corrected, 2203 flagged

=== 12429_malatavadi_chandgad_kolhapur - scored on 3 example truths ===
coverage:    1 corrected + 2 flagged
accuracy:    median IoU pred=0.785 vs official=0.510
improvement: 0.275
median centroid err=4.091 m
accurate(IoU>=.5)=1.000
```

**Browser validation:** I uploaded `predictions.geojson` to the Bhume Test page for Malatavadi. It
showed the same result:

```text
1 corrected + 2 flagged of 3 truths
median IoU: 0.785 vs official 0.510
improvement: +0.275
accurate @ IoU >= .5: 100%
median centroid error: about 3.9 m
```

**What I learned:** The core challenge is not only image alignment. It is deciding when the evidence
is trustworthy enough to automate and when the plot should be sent to a human.

## 8. Packaging and Submission

**My prompt:** "create a github repo and push clean"

**How I used AI:** I used Codex to initialize a clean Git repo, check ignored files, commit the
submission, help with GitHub CLI authentication, and push to GitHub.

**Repo:**

```text
https://github.com/phanixdev/bhume-boundary-takehome
```

**Commits:**

```text
7d798e2 Add Malatavadi boundary solver submission
5fb6027 Add transcript log and video script
```

## 9. Final Framing

The main framing I plan to use in the video/submission:

> I optimized for calibrated restraint rather than broad coverage. The method only corrects plots
> when boundary evidence clearly improves over the official position; otherwise it flags them. On
> the public Malatavadi examples, the one corrected plot improves IoU from 0.510 to 0.785, while
> uncertain cases are left flagged.

## 10. Reproducibility Commands

```powershell
cd C:\Users\phani\Documents\Bhume\starter-kit\bhume-starter-kit
$env:UV_CACHE_DIR = ".uv-cache"
python -m uv sync
python -m uv run solve.py data/12429_malatavadi_chandgad_kolhapur
```

Expected final output:

```text
wrote data\12429_malatavadi_chandgad_kolhapur\predictions.geojson
coverage: 305 corrected, 2203 flagged
```
