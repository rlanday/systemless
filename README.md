Nanosaur correctness screenshots for Systemless PRs #4213, #4214, #4215 and #4217.

These are unedited software-rendered captures from the original game in the combined validation builds, at matching scripted checkpoints. They illustrate the reported symptoms and corrections; the standalone PR branches are validated separately by their regression tests and full library suites.

- camera-before.png / camera-after.png: gameplay checkpoint before and after the camera-matrix correction. Distant terrain and objects return. The later shadow and terrain-seam corrections are not included.
- ownership-before.png / ownership-after.png: menu checkpoint before and after file-group ownership correction. The trophy at left and door at right return.

PR #4215: minimap-before/after-rest.png and minimap-before/after-moving.png show the same stationary and forward-movement checkpoints. The minimap keeps its position and size after the camera-state correction. The after build also includes the separate face-normal culling fix, which accounts for terrain coverage differences.

PR #4217: terrain-seam-before.png / terrain-seam-after.png are unedited software-rendered captures at completed QD3D scene 8002 from matching original-game scripted runs. Look for the bright dotted diagonal crack at the left edge of the ground (x=120–156, y=119–128). All 15 previously diagnosed background pixels are covered by terrain afterward.

The before capture is from combined validation source dd1e893d (integer-rounded triangle coverage). The after capture is from a8859d4f, including fractional coverage, exact clip-plane intersections, and the separate shadow-depth correction in #4218. The softer shadows come from #4218. These captures illustrate the combined validation builds; they are not screenshots of the standalone PR branch.
