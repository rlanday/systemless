---
name: commit-authorship-cla
description: Systemless PR commits must be authored by Ryan (rlanday@gmail.com); the CLA bot rejects commits authored as Claude
metadata:
  node_type: memory
  type: feedback
  originSessionId: 9b3958db-52bb-4ed6-93f4-7f250fbc2210
  modified: 2026-09-26T09:05:20.949Z
---

Every commit in a benletchford/systemless PR must have Ryan Landay <rlanday@gmail.com> as git author; Claude may appear only in the `Co-Authored-By:` trailer.

**Why:** PR #2886 failed the CLA-assistant check ("claude" not signed) because one commit's author was Opus 5.5 <noreply@anthropic.com>. Co-author trailers pass the check; authorship does not.

**How to apply:** before pushing, run `git log --format='%an <%ae>' origin/master..HEAD`; fix any non-Ryan author with `git rebase origin/master --exec 'git commit --amend --no-edit --reset-author'` (user.name/email set to Ryan). PRs are pushed to the fork rlanday/systemless over HTTPS with the gh credential helper, then opened with `gh pr create --head rlanday:<branch>`. See [[systemless-pr-publishing]].
