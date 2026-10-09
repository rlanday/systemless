Nanosaur correctness screenshots for Systemless PRs #4213 and #4214.

These are unedited software-rendered captures from the original game in the combined validation builds, at matching scripted checkpoints. They illustrate the reported symptoms and corrections; the standalone PR branches are validated separately by their regression tests and full library suites.

- camera-before.png / camera-after.png: gameplay checkpoint before and after the camera-matrix correction. Distant terrain and objects return. The later shadow and terrain-seam corrections are not included.
- ownership-before.png / ownership-after.png: menu checkpoint before and after file-group ownership correction. The trophy at left and door at right return.
