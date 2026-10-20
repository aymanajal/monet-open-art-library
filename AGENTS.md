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
