"""Keep the legacy suite out of collection.

test_local_claude_server.py imports a module deleted with the abandoned
feature/local-claude-server branch, so collecting it raises ImportError and
aborts the entire run. The autonomy layer gates on a green suite, so a single
uncollectable file would block every autonomous run permanently.

See README.md in this directory.
"""
collect_ignore_glob = ["test_*.py"]
