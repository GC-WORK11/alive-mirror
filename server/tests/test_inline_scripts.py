"""Gate: every inline <script> in server/*.html must parse as JS.

f9ea5ae P0 — a bare ' inside a single-quoted literal ('the map's reach')
made the whole 54KB landing script a syntax error: page dead on prod for
hours while brace-count checks stayed green. This test runs the real
node --check path (CI runners ship node; the repo box does too) plus the
stdlib fallback scanner, and proves the checker itself catches the bug
class on a planted fixture.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHECKER = ROOT / "scripts" / "check_inline_scripts.py"
HTML_GLOB = ROOT / "server"


def _run(*args):
    return subprocess.run(
        [sys.executable, str(CHECKER), *args],
        capture_output=True, text=True, timeout=120)


def test_inline_scripts_parse_clean():
    r = _run()
    assert r.returncode == 0, f"{r.stdout}\n{r.stderr}"
    # sanity: the checker actually saw the four pages' blocks
    assert "4 inline script block(s)" in r.stdout


def test_checker_catches_bare_apostrophe_bomb(tmp_path):
    """The exact f9ea5ae failure shape must fail the gate."""
    bad = tmp_path / "bad.html"
    bad.write_text(
        "<html><body>\n<script>\n"
        "const x = 'the map\\'s reach is fine escaped';\n"
        "const y = 'but the map's reach is not';\n"  # noqa: bare ' = the bomb
        "</script>\n</body></html>\n")
    r = _run(str(bad))
    assert r.returncode == 1
    assert "SyntaxError" in r.stdout or "unterminated" in r.stdout


def test_checker_flags_script_inside_comment(tmp_path):
    """'<script' inside <!-- --> is prose — warned, never extracted
    (the earlier regex trap parsed comment text as a script)."""
    bad = tmp_path / "commented.html"
    bad.write_text(
        "<html><body>\n"
        "<!-- the gate at the head of <script> removes this node -->\n"
        "<script>const ok = 1;</script>\n"
        "</body></html>\n")
    r = _run(str(bad), "--strict")
    assert r.returncode == 1
    assert "inside HTML comment" in r.stdout
    # and without --strict it still passes (comment is advisory)
    assert _run(str(bad)).returncode == 0
