# Changelog

## 0.15.1

- Added a dedicated 65–105 px natural landing phase that preserves personal route geometry.
- Progressively lowers the correction speed from 2400 px/s to 900 px/s near the endpoint.
- Rectangle targets now choose a varied safe aim circle instead of collapsing to the exact centre.
- Keeps deterministic seeds, personal click bias, overshoots, click timing and target padding intact.
- Prevents double smoothing from hiding real approach corrections in the personal profile.
- Added focused regression coverage for landing speed, timing, target safety and endpoint variation.

## 0.15.0

- Added installable Python package metadata and a stable RuneScape Two mouse-engine entry point.
- Added a runtime provider that exports every generated movement sample and exact mouse-down/up timing as one executable event timeline.
- Reuses the complete personal continuous generator, including reaction time, click delay, hold duration, route cloud, speed limits, overshoot and corrections.
- Added rectangle targets with configurable safe click padding.
- Added explicit and environment-based personal profile discovery without publishing private recordings or heatmaps.
- Added focused runtime-provider and deterministic-plan regression tests.

## 0.14.2

- Added a rotating segmented ring around the live cursor in the Random Mouse Test.
- Added a fading cyan trail that follows the last part of each generated movement.
- Keeps visual rendering on the Tk main thread so route timing, limiter behavior and cursor execution stay unaffected.
- Resets the trail for each new movement while preserving the visible target and HUD.
- Synchronized package, VERSION and Turbo Repo Hub metadata.

## 0.14.0

- Added a standalone transparent Windows desktop test with 10 randomized targets.
- Shows one numbered click circle at a time over the real desktop while preserving the underlying screen.
- Executes the personal v0.13.2 movement generator and dynamic no-jump limiter outside Aim Lab.
- Uses native Windows cursor and click APIs without adding a new dependency.
- Supports immediate Escape cancellation and saves every completed movement to `data/live_tests`.
- Added a one-click `Start Random Mouse Test.bat` launcher.
- Scales between the physical screen and the 1920 × 1080 personal-model coordinate space.
- Synchronized package, VERSION and Turbo Repo Hub metadata.

## 0.13.2

- Added a hard human reaction-time floor for generated target acquisition.
- Replaced probabilistic per-trial miss trimming with an exact batch-level miss ceiling of the lower of the personal rate and 10%.
- Shortened generated miss recovery and capped its timing tail.
- Tightened raw segment speed limiting to 11,000 px/s.
- Added a second measured-speed limiter using the exact same smoothed `derive_trial` metric exposed in exported JSON.
- Dynamically stretches the active timeline and click timing when the measured route would otherwise exceed the cap; coordinates are never skipped or teleported.
- Added regression tests for reaction time, exact batch miss count, raw segment speed and exported measured peak speed.
- Synchronized VERSION and Turbo Repo Hub metadata.

## 0.13.1

- Reduced route-cloud width when the selected personal template already contains strong lateral curvature.
- Replaced symmetric leaf-shaped cloud warping with asymmetric early/late deviation profiles.
- Fades added cloud variation near the target so arrival and click behavior stay compact.
- Caps generated miss frequency at the real global profile rate with a conservative 12% ceiling.
- Rebuilds shortened click-delay phases as smooth settling routes instead of truncating and jumping to the click point.
- Reworked speed limiting into dynamic path retiming: when a segment needs more time, all downstream timing and the click move later without skipping coordinates.
- Added regression coverage proving every generated segment remains inside the final speed ceiling.
- Synchronized package, VERSION and Turbo Repo Hub metadata.

## 0.13.0

- Added a continuous route-cloud layer so repeated runs no longer group around a few discrete template lanes.
- Adds smooth per-run lateral variation with fixed start and click endpoints.
- Compacts generated miss recovery into one direct correction instead of a long multi-phase loop.
- Bounds extreme local peak speeds by stretching impossible sample intervals rather than flattening the route.
- Calibrates non-miss click delay away from near-zero and extreme long tails.
- Added regression tests for route-band diversity, click-delay bounds, peak speed and click endpoints.
- Routed production A/B and Heatmap generation through the new quality layer.
- Synchronized package, VERSION and Turbo Repo Hub metadata.

## 0.12.0

- Fixed double-counted click delay on generated route templates.
- Added context-weighted timing, overshoot, correction and miss behavior by distance, target size and direction.
- Added personal positive-overshoot distributions so larger real overshoots can remain rare instead of being capped near target radius.
- Added route-template quality scoring and weighted template selection.
- Rejects structurally implausible template shapes before generation.
- Compresses repeated and near-stationary samples that previously produced artificial freezes.
- Added irregular generated sample intervals instead of fixed route timing steps.
- Added approach-correction metrics to global and contextual personal profiles.
- Reworked approach-correction detection to ignore low-speed microjitter and unreliable near-180-degree flips.
- Added model-quality regression tests for click delay, template rejection and approach corrections.
- Synchronized package, VERSION and Turbo Repo Hub metadata.

## 0.11.0

- Added a dedicated Heatmap page.
- Repeats the newest completed Aim Lab target playlist with the personal generator.
- Added a 10–500 run slider with 100 runs as the default.
- Exports every generated trial into one `heatmap_runs.json` file.
- Added per-target route overlays and a direct button to open the export folder.

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
