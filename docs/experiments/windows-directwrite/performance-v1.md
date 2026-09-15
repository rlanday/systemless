# Initial Windows font performance measurements (v1)

These measure the first Rust DirectWrite candidate, before the metadata/cache optimizations preserved in this branch. They are diagnostic results, not the final PR acceptance numbers.

Windows native release build, same binary with the font experiment disabled/enabled. Battery power was explicitly approved by the user; Balanced power mode, battery saver off throughout, 50% down to 44% during the replay matrix. The older cleartype-prototype and sc2k-fixed game windows remained open. No compilation, tests, sampling, or per-frame trace logging ran during the timing matrix.

Each size was tested in both orders (A/B then B/A), 1,100 deterministic guest frames per run. Every compared instruction/tick row, three guest-frame snapshots, and the final 9 MiB RAM snapshot matched. Total frame work is measured directly, not assembled from independent phase medians. This replay excludes GUI surface acquisition/submission, host audio mixing, frame pacing, and physical scanout. A separate GUI run includes surface and audio work.

| Scenario | Existing rendering, run medians (ms) | Native text, run medians (ms) |
| --- | ---: | ---: |
| new_city, 800×600 | 6.24–6.40 | 14.52–16.91 |
| city, 800×600 | 8.48–10.08 | 17.67–20.24 |
| newspaper, 800×600 | 6.99–8.99 | 24.80–32.45 |
| new_city, 1104×828 | 32.50–34.45 | 40.09–40.75 |
| city, 1104×828 | 33.45–34.08 | 42.76–44.75 |
| newspaper, 1104×828 | 32.14–32.37 | 52.14–56.39 |

The GUI city-view medians were 10.98→17.84 ms at 800×600 and 37.44→48.93 ms at 1104×828. Those are initial samples with differing live guest work; use the identical replay for controlled guest comparisons.

Retained text composition and cached-glyph sampling account for substantial overhead. A separate untimed diagnostic recorded 413 glyph renders over 1,205 overlay calls and zero cache clears, so cache thrashing is not the cause. That diagnostic overlapped compilation and its wall/CPU timings are excluded.

Later metadata invalidation fast paths and single-lookup glyph sampling passed the integration pixel checks. Their performance has not been remeasured; this report is not a measurement of the final archived source. An actual master-only baseline is still needed to account for any changes outside the opt-in switch. Monitor/settings invalidation remains required before enabling native text by default.
