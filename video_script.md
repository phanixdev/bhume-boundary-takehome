# 5-Minute Video Script

Use this while screen-recording. Good screens to show: the Bhume Test page, the GitHub repo README,
`solve.py`, and `predictions.geojson`.

## 0:00-0:30 - Intro

Hi, I am walking through my Bhume boundary take-home submission.

The problem is that the official cadastral plot outlines are not always where the real fields are
on satellite imagery. My submission focuses on Malatavadi, Kolhapur. I chose one village because I
wanted to prioritize a clear, reproducible method and calibrated restraint rather than trying to
cover both villages weakly.

## 0:30-1:15 - What I Built

The repo contains a runnable Python method in `solve.py`. It reads the village bundle:
`input.geojson`, `imagery.tif`, and `boundaries.tif`, and writes a contract-shaped
`predictions.geojson`.

For each plot, the output is either `corrected`, meaning I predict a better boundary, or `flagged`,
meaning I looked at it but did not trust the evidence enough to move it. Flagged plots keep the
official geometry.

## 1:15-2:15 - Method

The first version is deliberately translation-only. I keep the official plot shape unchanged and
try small shifts around the current position, up to about 20 metres.

For every candidate shift, I sample points along the polygon boundary and score how well those
points line up with two signals:

1. the rough field-boundary raster from `boundaries.tif`;
2. image-edge strength computed from the satellite image in `imagery.tif`.

I also penalize larger shifts, because a big move is more likely to jump to the wrong nearby field,
especially in Malatavadi where parcels are small and crowded.

## 2:15-3:00 - Confidence and Restraint

The important part is not just moving polygons; it is knowing when not to move them.

I use the map-area versus recorded-area ratio as a risk signal. If the drawn polygon and the land
record disagree strongly, the problem may be stale records or wrong geometry, not just placement.
Those cases are usually flagged.

Confidence is based on the edge signal strength, the improvement margin over the original position,
the shift size, and the area-ratio sanity. Low-confidence cases are not emitted as weak corrections;
they are flagged. That is intentional because the assignment scores calibration and restraint.

## 3:00-3:45 - Results

On the full Malatavadi bundle, the method produced:

- 305 corrected plots;
- 2203 flagged plots.

On the public Malatavadi Test page, which has only three example truths, the method corrected one
plot and flagged two. For the corrected example, the median IoU improves from 0.510 for the
official boundary to 0.785 for my prediction. The centroid error is about 3.9 metres, and the
corrected example clears IoU 0.5.

I do not treat this tiny public sample as a final grade. I use it as a directional check that the
method can improve a plot when it chooses to move one.

## 3:45-4:30 - What Broke / What I Learned

An earlier version corrected many more plots, but one public example was over-shifted into the
wrong field. That taught me that strong local boundary evidence can still be misleading when the
shift is large. I added a restraint rule: large shifts require exceptional evidence. That reduced
coverage but made the submission more honest.

The main lesson was that this is not just an image-alignment problem. It is a judgment problem:
which signal to trust, when area records are a warning, and when to send a plot to a human instead
of pretending the algorithm knows.

## 4:30-5:00 - Next Steps

If I had more time, I would add three things:

1. rotation and light reshaping, because some plots are not fixed by translation alone;
2. neighborhood consistency, so adjacent plots move coherently rather than independently;
3. cross-village validation on Vadnerbhairav to test whether the confidence logic generalizes.

For this submission, I optimized for a small, readable, reproducible method with calibrated
restraint. The repo includes the code, predictions, README, and AI development transcript.
