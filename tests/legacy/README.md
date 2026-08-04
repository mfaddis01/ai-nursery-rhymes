# Legacy tests — not collected

`test_local_claude_server.py` covers a local HTTP Claude server that no longer
exists. It was salvaged from the abandoned `feature/local-claude-server` branch
before that branch was deleted, and imports `local_claude_server`, which is not
in this repo.

It is kept out of `tests/` because an uncollectable file aborts the whole run,
and the autonomy layer gates on a green suite — one orphan file would block
every autonomous run permanently.

Its intent lives on in `tests/test_rhyme_manager.py`, which covers the same
failure paths against the `claude -p` subprocess that replaced the server.
Delete this directory once you are sure nothing here is worth porting.
