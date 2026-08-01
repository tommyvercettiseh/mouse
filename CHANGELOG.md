# Changelog

## 0.10.0

- Replaced the legacy `app_v1.py` wrapper with one clean application entrypoint.
- Split Aim Lab recording and replay into focused UI controllers.
- Removed the Free Record flow, old patch modules and obsolete launch code.
- Added resilient callback and runtime logging in `logs/ai_mouse_lab.log`.
- Records and validates hits at mouse-down rather than mouse release.
- Excludes button-hold and release drift from movement, acceleration and overshoot metrics.
- Normalizes older recordings to mouse-down semantics when they are read.
- Stores actual normalized route shapes and reuses recurring wiggles, bends and correction patterns in generated movement.
- Made generated routes end at the personally sampled click position.
- Added visible final-click and miss markers to A/B replay.
- Added generated miss recovery routes instead of metadata-only misses.
- Added click padding and click-error values to replay statistics.
- Added product-contract, click-route, route-shape and replay-timing regression tests.
- Added Windows and Linux GitHub Actions checks.
- Made the Windows launcher install dependencies only when required.
- Synchronized package, VERSION and Turbo Repo Hub version metadata.
- Added `PRODUCT.md` and `ROADMAP.md`.

## 0.9.4

- Removed Free Record from the visible product flow.
- Kept Aim Lab as the only supported profile-training source.

## 0.9.3

- Added a personal click-placement model by target-size band.
- Preserved click direction, center distance and edge-padding behavior.
- Added regression tests proving generated clicks are not center-forced.

## 0.9.2

- Fixed smoothing of short routes by preserving route endpoints.
- Restored acceptance of valid normal profile trials.

## 0.9.1

- Added sustained braking detection and target-approach speed measurements.
- Added speeds at 2×, 1× and 0.5× target radius.
- Added final-100-ms speed and related regression tests.

## 0.9.0

- Replaced the active historical patch chain with integrated schema, metrics, profile, generator and comparison modules.
- Added one canonical trial schema and legacy-data normalization.
- Added continuous A/B replay and clean Windows entrypoint.

## 0.7.0

- Added contextual personal motion profiles by distance, target size and direction.
- Added recording modes for normal training data and detection tests.
- Added data-quality filtering with transparent rejection reasons.
- Added braking, acceleration, jerk, entry/exit and correction statistics.
- Updated the generator to use the closest sufficiently populated personal context.
- Added regression tests for directional overshoot, fast target crossing, context separation and test-data exclusion.
- Updated Turbo Repo Hub metadata and documentation.

## 0.6.4

- Added live orange/red target feedback when an overshoot is detected.
