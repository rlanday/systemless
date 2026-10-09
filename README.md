Nanosaur correctness screenshots for Systemless PRs #4213 and #4214.

These are unedited software-rendered captures from the original game in the combined validation builds, at matching scripted checkpoints. They illustrate the reported symptoms and corrections; the standalone PR branches are validated separately by their regression tests and full library suites.

- camera-before.png / camera-after.png: gameplay checkpoint before and after the camera-matrix correction. Distant terrain and objects return. The later shadow and terrain-seam corrections are not included.
- ownership-before.png / ownership-after.png: menu checkpoint before and after file-group ownership correction. The trophy at left and door at right return.

PR #4215: minimap-before/after-rest.png and minimap-before/after-moving.png show the same stationary and forward-movement checkpoints. The minimap keeps its position and size after the camera-state correction. The after build also includes the separate face-normal culling fix, which accounts for terrain coverage differences.
