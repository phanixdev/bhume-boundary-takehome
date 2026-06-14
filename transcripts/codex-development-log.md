# Codex Development Log

This is the readable AI transcript for the Bhume boundary take-home work. It records the
assignment-relevant prompts, responses, implementation decisions, commands, and validation outputs.

## 1. Assignment Inspection

**User prompt:** "open and inspect the assignment and tell me what it is"

**Codex response/action:** Inspected `https://hiring.bhume.in/`, including the Understand, Task,
Get Started, Test, and Submit pages. Summarized the task as a geospatial boundary-correction
problem: old official cadastral plot boundaries are shifted relative to satellite imagery, and the
solution must return a `predictions.geojson` with `corrected` or `flagged` features.

**Key findings:**

- Inputs: `input.geojson`, `imagery.tif`, optional `boundaries.tif`, and public
  `example_truths.geojson`.
- Output: `predictions.geojson` containing `plot_number`, `status`, `confidence`,
  `method_note`, and geometry.
- Evaluation: IoU, centroid error, improvement over official position, confidence calibration, and
  restraint.
- Submission: one GitHub repo, predictions, transcripts, and a 5-minute walkthrough video.

## 2. Deadline and Scope

**User prompt:** "deadline to submit?"

**Codex response/action:** Reported that the assignment page originally said there were no fake
deadline games, and later verified the submit page showed a review batch note: next read Wednesday
morning, June 17 IST, with anything in by Tuesday evening, June 16 counted for it.

**User prompt:** "they gave two different locations . do we need to do for both?"

**Codex response/action:** Recommended focusing on one village first. The task says candidates may
pick one village or both, so the plan optimized for Malatavadi only, where local files were already
downloaded.

## 3. Data Setup and Strategy

**User prompt:** "save these files and explain the strategy"

**Codex response/action:** Copied the downloaded Malatavadi files into the workspace:

```text
data/raw/input.geojson
data/raw/imagery.tif
data/raw/boundaries.tif
```

Then inspected `input.geojson`.

**Data summary:**

```text
features: 2508
village: Malatavadi
bounds lon/lat: [74.320161749, 15.976840411, 74.351155249, 16.000904975]
median map area: 872.45 sqm
area ratio median: 1.002
near ratio 0.9-1.1: 1009 plots
far ratio <0.7 or >1.3: 532 plots
```

**Strategy proposed:**

- Be conservative because Malatavadi has small, tightly packed parcels.
- Prefer plots where map area and recorded area roughly agree.
- Search small translations around the official boundary.
- Score candidates using `boundaries.tif` and image-edge strength from `imagery.tif`.
- Penalize large shifts and weak evidence.
- Flag uncertain plots instead of forcing low-confidence corrections.

## 4. Starter Kit Inspection

**User prompt:** "this is the starter kit they gave . inspect"

**Codex response/action:** Unpacked and inspected the starter kit.

**Important files:**

- `CONTRACT.md` - exact input/output format.
- `quickstart.py` - worked load/predict/score loop.
- `bhume/io.py` - `load()` and `write_predictions()`.
- `bhume/geo.py` - CRS and raster helpers.
- `bhume/baseline.py` - naive global median shift baseline.
- `bhume/score.py` - local scoring against example truths.

**Conclusion:** The starter kit handles geospatial plumbing but does not solve the alignment task.
The solution should build on `load()`, raster helpers, and `write_predictions()`.

## 5. Plan

**User prompt:** "plan it"

**Codex response/action:** Proposed a Malatavadi-only Silver/Gold plan:

- Create a clean starter-kit project with Malatavadi data.
- Add `solve.py`.
- Search translations within about 20 metres.
- Score boundary-raster intensity and image gradients along polygon outlines.
- Keep geometry shape unchanged for v1.
- Correct only high-signal plots and flag the rest.
- Write README, transcript scaffold, and video outline.

**User selected:** Malatavadi only and Silver/Gold attempt.

## 6. Implementation

**User prompt:** "PLEASE IMPLEMENT THIS PLAN"

**Codex response/action:** Implemented the plan.

**Files added/updated:**

- `solve.py`
- `README.md`
- `transcripts/README.md`
- `.gitignore`
- `data/12429_malatavadi_chandgad_kolhapur/*`

**Core method in `solve.py`:**

- Loads `input.geojson`, `imagery.tif`, and `boundaries.tif`.
- Converts geometries to imagery CRS for metre-based translations.
- Samples points along each polygon boundary.
- Builds two normalized raster signals:
  - rough field-boundary signal from `boundaries.tif`;
  - satellite image gradient from `imagery.tif`.
- Tries candidate translations up to 20 metres.
- Scores candidates as a weighted combination of boundary signal and image-edge signal.
- Penalizes large shifts.
- Uses area-ratio sanity as a risk signal.
- Writes `corrected` only when the best shift clearly beats the original.
- Writes `flagged` with original geometry otherwise.

## 7. Validation and Tuning

**Environment setup:**

```powershell
python -m pip install --user uv
python -m uv sync
```

Because `uv run` had a Windows cache issue inside the sandbox, a workspace-local cache was used:

```powershell
$env:UV_CACHE_DIR = ".uv-cache"
python -m uv run solve.py data/12429_malatavadi_chandgad_kolhapur
```

**First full run result:**

```text
coverage: 563 corrected, 1945 flagged
public example score:
median IoU pred=0.785 vs official=0.510
improvement=0.275
but one public example was over-shifted, hurting calibration
```

**Tuning decision:** Added a restraint rule: shifts over 14 metres require exceptional evidence.
This reduced broad overclaiming.

**Final full run result:**

```text
coverage: 305 corrected, 2203 flagged

=== 12429_malatavadi_chandgad_kolhapur - scored on 3 example truths ===
coverage:    1 corrected + 2 flagged
accuracy:    median IoU pred=0.785 vs official=0.510
improvement: 0.275
median centroid err=4.091 m
accurate(IoU>=.5)=1.000
```

**Browser Test page result:** Confirmed the same Malatavadi public score after uploading
`predictions.geojson`.

## 8. GitHub Publishing

**User prompt:** "create a github repo and push clean"

**Codex response/action:**

- Initialized a clean local Git repo inside the starter-kit project.
- Committed the submission.
- Helped authenticate GitHub CLI as `phanixdev`.
- Created and pushed:

```text
https://github.com/phanixdev/bhume-boundary-takehome
```

**Commit:**

```text
7d798e2 Add Malatavadi boundary solver submission
```

## 9. Final Submission Guidance

**User prompt:** "if it good enough to submit?"

**Codex response/action:** Recommended submitting as a conservative, honest first submission,
with framing focused on restraint and calibration rather than claiming the problem is solved.

**Recommended framing:**

> I optimized for calibrated restraint rather than broad coverage. The method only corrects plots
> when boundary evidence clearly improves over the official position; otherwise it flags them. On
> the public Malatavadi examples, the one corrected plot improves IoU from 0.510 to 0.785, while
> uncertain cases are left flagged.

## 10. Commands Worth Reproducing

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

GitHub repo:

```text
https://github.com/phanixdev/bhume-boundary-takehome
```
