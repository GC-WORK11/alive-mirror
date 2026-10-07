#!/usr/bin/env python3
"""Syntax-check every inline <script> block in server/*.html.

Why this exists — f9ea5ae P0 (Oct 7): a plain-words copy pass left a bare
' inside a single-quoted JS string ('the map's reach'). The apostrophe
terminated the literal early, the rest of the line became garbage tokens,
and the entire 54KB inline script failed to parse → landing dead on prod
for hours. Brace-count checks (test_landing_serve.py) cannot see this:
the braces still balanced.

What it does:
- Extracts inline <script> blocks with a real HTML parser, not regex.
  '<script>' inside <!-- --> comments is prose, not code (e.g.
  admin.html's boot-strip comment) — the earlier regex extraction fell
  into that trap and parsed comment text as a script start.
- Writes each block to a temp file padded so node's reported line number
  equals the line number inside the HTML file, then runs `node --check`.
- Without node, falls back to a string-aware scanner (unterminated
  strings, newline inside a ' or " literal, unbalanced delimiters
  outside strings/comments). Weaker — it is a tripwire, not a parser.
- Warns on '<script' inside HTML comments (advisory only).

Usage:
    python scripts/check_inline_scripts.py            # scans server/*.html
    python scripts/check_inline_scripts.py FILES...   # scans given files
    python scripts/check_inline_scripts.py --strict   # warnings fail too

Exit 0 = clean; exit 1 = a syntax bomb (or, with --strict, a warning).
Stdlib only.
"""
import argparse
import glob
import os
import re
import shutil
import subprocess
import sys
import tempfile
from html.parser import HTMLParser

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class ScriptExtractor(HTMLParser):
    """Collect inline <script> bodies + '<script' inside comments.

    HTMLParser puts script content through handle_data verbatim (CDATA
    mode), so string contents like '</scr' + 'ipt>' tricks land exactly
    as the browser sees them — the script ends at the first literal
    '</script', same as a real parser.
    """

    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.scripts = []          # [(start_line, attrs, body)]
        self.comment_warnings = []  # [(line, snippet)]
        self._open = None          # [line, attrs, [chunks]]

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "script":
            self._open = [self.getpos()[0], dict(attrs), []]

    def handle_endtag(self, tag):
        if tag.lower() == "script" and self._open is not None:
            line, attrs, chunks = self._open
            self.scripts.append((line, attrs, "".join(chunks)))
            self._open = None

    def handle_data(self, data):
        if self._open is not None:
            self._open[2].append(data)

    def handle_comment(self, data):
        if "<script" in data.lower():
            snippet = data.strip().splitlines()[0][:72]
            self.comment_warnings.append((self.getpos()[0], snippet))


def _scan_fallback(body, start_line):
    """String-aware tripwire for boxes without node. Not a JS parser —
    it catches the bomb classes that survive brace-counting: strings left
    open at a newline or EOF, unterminated comments/templates, and
    unbalanced (){}[] outside strings/comments. Regex literals are only
    heuristically spotted (a '/' after =(:,[!&|?{}; opens one), so a '
    inside an exotic regex could false-positive — the report says which
    checker ran."""
    errors = []
    state = None            # None | "'" | '"' | '`' | '//' | '/*'
    stack = []              # (char, line) of open delimiters
    prev_significant = ""   # last non-space char outside strings/comments
    line = start_line + 1   # body begins on the line after <script>
    i, n = 0, len(body)
    pair = {")": "(", "]": "[", "}": "{"}
    while i < n:
        c = body[i]
        nxt = body[i + 1] if i + 1 < n else ""
        if c == "\n":
            line += 1
            if state in ("'", '"'):
                errors.append(
                    f"line {line}: unterminated {state}-quoted string "
                    "(newline inside literal — classic bare-apostrophe bomb)"
                )
                state = None
            elif state == "//":
                state = None
            i += 1
            continue
        if state == "//":
            i += 1
            continue
        if state == "/*":
            if c == "*" and nxt == "/":
                state = None
                i += 2
            else:
                i += 1
            continue
        if state in ("'", '"', "`"):
            if c == "\\":
                i += 2
                continue
            if c == state:
                state = None
            i += 1
            continue
        # state is None — normal code
        if c == "/" and nxt == "/":
            state = "//"
            i += 2
            continue
        if c == "/" and nxt == "*":
            state = "/*"
            i += 2
            continue
        if c in "'\"`":
            state = c
            i += 1
            continue
        if c == "/" and (prev_significant in "=(:,[!&|?{};"
                         or not prev_significant):
            # likely a regex literal — skip to its closing unescaped /
            j = i + 1
            in_class = False
            closed = False
            while j < n:
                d = body[j]
                if d == "\\":
                    j += 2
                    continue
                if d == "[":
                    in_class = True
                elif d == "]":
                    in_class = False
                elif d == "/" and not in_class:
                    closed = True
                    break
                elif d == "\n":
                    break
                j += 1
            if closed:
                i = j + 1
                prev_significant = "/"
                continue
            i += 1
            prev_significant = c
            continue
        if c in "([{":
            stack.append((c, line))
        elif c in ")]}":
            if not stack or stack[-1][0] != pair[c]:
                errors.append(f"line {line}: unmatched {c!r}")
            else:
                stack.pop()
        if not c.isspace():
            prev_significant = c
        i += 1
    if state in ("'", '"', "`"):
        errors.append(f"line {line}: unterminated {state}-quoted string at EOF")
    if state == "/*":
        errors.append(f"line {line}: unterminated /* comment at EOF")
    for ch, ln in stack:
        errors.append(f"line {ln}: unclosed {ch!r}")
    return errors


def _node_check(body, start_line, display, tmpdir):
    """node --check on the body, padded so error lines == HTML lines.
    On failure, retry as ESM (.mjs) in case a future block uses
    import/export; report whichever run fails."""
    padded = "\n" * start_line + body
    for ext, label in ((".js", "script"), (".mjs", "module")):
        path = os.path.join(tmpdir, display.replace("/", "_") + ext)
        with open(path, "w") as fh:
            fh.write(padded)
        r = subprocess.run(["node", "--check", path],
                           capture_output=True, text=True)
        if r.returncode == 0:
            return []
        err = (r.stderr or r.stdout).strip()
        # a genuine syntax error repeats on both parses — only a
        # module-vs-script difference changes the verdict, so any
        # second failure means: report the FIRST (script-mode) error.
        if ext == ".mjs":
            return [err_first]
        err_first = err.replace(path, display)
    return [err_first]


def check_file(path, node, tmpdir):
    """Returns (errors, warnings, n_blocks) for one HTML file."""
    parser = ScriptExtractor()
    with open(path, "r", encoding="utf-8") as fh:
        parser.feed(fh.read())
    parser.close()
    errors, warnings = [], []
    for line, snippet in parser.comment_warnings:
        warnings.append(f"{path}:{line}: '<script' inside HTML comment "
                        f"(prose — NOT extracted): {snippet!r}")
    for start_line, attrs, body in parser.scripts:
        if attrs.get("src"):
            continue  # external scripts are fetched, not inline
        if not body.strip():
            warnings.append(f"{path}:{start_line}: empty inline <script> block")
            continue
        if node:
            errors.extend(_node_check(body, start_line, path, tmpdir))
        else:
            errors.extend(f"{path}:{e} [fallback-scan]"
                          for e in _scan_fallback(body, start_line))
    return errors, warnings, len(parser.scripts)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("files", nargs="*",
                    help="HTML files to check (default: server/*.html)")
    ap.add_argument("--strict", action="store_true",
                    help="treat warnings (comment mentions, empty blocks) as failures")
    ap.add_argument("--allow-no-node", action="store_true",
                    help="accept the weaker fallback scan silently")
    args = ap.parse_args(argv)

    files = args.files or sorted(
        glob.glob(os.path.join(REPO_ROOT, "server", "*.html")))
    if not files:
        print("check_inline_scripts: no HTML files found", file=sys.stderr)
        return 1

    node = shutil.which("node") is not None
    if not node:
        print("check_inline_scripts: node not found — using the weaker "
              "string-aware fallback scan", file=sys.stderr)
        if not args.allow_no_node:
            print("(pass --allow-no-node to accept this)", file=sys.stderr)
            return 1

    all_errors, all_warnings, total = [], [], 0
    with tempfile.TemporaryDirectory() as tmpdir:
        for path in files:
            errors, warnings, n = check_file(path, node, tmpdir)
            all_errors.extend(errors)
            all_warnings.extend(warnings)
            total += n

    for w in all_warnings:
        print(f"WARN  {w}")
    for e in all_errors:
        print(f"ERROR {e}")

    checker = "node --check" if node else "fallback scan"
    if all_errors or (args.strict and all_warnings):
        print(f"check_inline_scripts: FAIL — {len(all_errors)} error(s), "
              f"{len(all_warnings)} warning(s) across {total} inline "
              f"script block(s) in {len(files)} file(s) [{checker}]")
        return 1
    print(f"check_inline_scripts: OK — {total} inline script block(s) in "
          f"{len(files)} file(s) parse clean [{checker}]"
          + (f", {len(all_warnings)} warning(s)" if all_warnings else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
