# Canonical Monet library

This GitHub repository is the source of truth for the project's complete art resources, provenance, review decisions, content, and scheduling state.

- Pull and inspect the current catalog and posts before adding resources or scheduling anything.
- Preserve all files, including versions awaiting review. Use status changes rather than deleting candidates.
- Register every new image in catalog/artworks.json, artworks.csv, files.sha256 and inventory.json.
- Use repository-relative image paths. Keep credentials, cookies, login QR codes, machine paths, account identity and service logs outside the repository.
- Compare artwork identity and cropped/recoloured versions with all previous groups; identical titles and perceptual hashes alone cannot prove identity.
- Review the source page for rights and museum attribution. Commons category membership is not authoritative provenance.
- Update schedule status only after a confirmed platform response; scheduled success does not mean publication has been verified after its due date.
- Run python3 scripts/verify_library.py before committing and pushing any library change.
- Do not publish to social platforms unless the user has authorized the relevant posting task.
- For publishing continuation, read posts/发布总表.md and publication_ledger.json first. P-prefixed batches are blocked-review proposals, NOT ready posts or platform reservations.
- Never infer publication from a due date. Preserve unknown outcomes and verify the platform before retrying. No library upload record does not rule out uploads made manually elsewhere.
- Before uploading, pull and push a submission_in_progress reservation so another computer cannot independently take the same group. If reservation push fails, do not upload. Never publish concurrently from two computers.
- After changing any schedule or asset review status, refresh the publication ledger with python3 scripts/build_publication_ledger.py; then verify, commit, push and compare the remote SHA. Do not store login credentials on GitHub for portability.
