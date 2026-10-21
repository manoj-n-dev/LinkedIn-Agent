## Description

Brief summary of the changes made in this PR.

## Security & Architecture Checklist

- [ ] All handlers respect `@owner_only` authentication.
- [ ] Any LinkedIn action routes strictly through `ExternalActionGate`.
- [ ] No prohibited automation (scraping, browser automation, automated likes/comments).
- [ ] Zero real secrets, tokens, or personal identifiers committed.
- [ ] All tests pass: `python -m pytest -v`.
- [ ] Linter is clean: `python -m ruff check .`.
- [ ] Secret scan passes: `pytest tests/test_secret_hygiene.py`.
