#!/usr/bin/env python3
"""a11y_audit.py — static accessibility audit for the ALive-108 mobile shell.

Scans Mobile/**/*.tsx (src + root App.tsx) for:
  1. Pressable/Touchable* without an accessibility label
  2. Interactive elements missing accessibilityRole
  3. Touch targets styled under 44 pt (MIN_TOUCH, src/a11y)
  4. <Text> elements without a font-scaling cap (doc 03: ≤130%)
  5. Live counters missing a liveRegion/announce path (doc 02 §S6)
  6. disabled={} Pressables whose state isn't announced
  7. Hard-coded accessibility labels that bypass the i18n string table
Plus a WCAG contrast audit of the V2T palette (Mobile/src/theme.ts) against
the dark backgrounds — doc 03 claims "all text ≥ 4.5:1".

Usage:  python3 scripts/a11y_audit.py [--mobile-dir Mobile] [--min-severity LOW]
Output: markdown report on stdout (CI-friendly; always exits 0 — advisory).
"""
import argparse
import re
import sys
from pathlib import Path

INTERACTIVE = ("Pressable", "TouchableOpacity", "TouchableHighlight", "TouchableWithoutFeedback")
LABEL_ATTRS = ("accessibilityLabel", "aria-label", "accessibilityLabelledBy")
ROLE_ATTRS = ("accessibilityRole", "aria-role", "role")
MIN_TOUCH = 44
SEV_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "INFO": 3}


def find_matching(s: str, start: int, open_c: str = "{", close_c: str = "}") -> int:
    """Index of the brace matching the one at `start`, or len(s)."""
    depth = 0
    i = start
    while i < len(s):
        ch = s[i]
        if ch == open_c:
            depth += 1
        elif ch == close_c:
            depth -= 1
            if depth == 0:
                return i
        elif ch in "\"'`":
            q = ch
            i += 1
            while i < len(s) and s[i] != q:
                i += 2 if s[i] == "\\" else 1
        i += 1
    return len(s)


def line_of(text: str, idx: int) -> int:
    return text.count("\n", 0, idx) + 1


def parse_styles(text: str) -> dict:
    """Map stylesheet-key → {width,height,minWidth,minHeight,padV,padH,pad,flex,stretch}."""
    styles = {}
    for m in re.finditer(r"StyleSheet\.create\s*\(", text):
        ob = text.index("{", m.end())
        cb = find_matching(text, ob)
        body = text[ob:cb]
        for e in re.finditer(r"(\w+)\s*:\s*\{([^{}]*)\}", body):
            key, props = e.group(1), e.group(2)

            def num(prop):
                mm = re.search(rf"\b{prop}\s*:\s*(\d+(?:\.\d+)?)\b", props)
                return float(mm.group(1)) if mm else None

            styles[key] = dict(
                width=num("width"), height=num("height"),
                minWidth=num("minWidth"), minHeight=num("minHeight"),
                padV=num("paddingVertical"), padH=num("paddingHorizontal"),
                pad=num("padding"),
                flex=num("flex"), stretch=("stretch" in props),
                inline=props,
            )
    return styles


def elem_block(text: str, m: re.Match) -> tuple:
    """Return (attr_text, body_text, self_closed) for a JSX open tag at match."""
    i = m.end()
    depth_angle = 0
    while i < len(text):
        ch = text[i]
        if ch == "{":
            i = find_matching(text, i)
        elif ch == ">":
            self_closed = i > 0 and text[i - 1] == "/"
            attrs = text[m.start():i]
            if self_closed:
                return attrs, "", True
            # find matching close tag (flat approximation: same tag name)
            tag = re.match(r"<\s*(\w+)", m.group(0)).group(1)
            cm = re.search(rf"</{tag}\s*>", text[i:])
            end = i + 1 + (cm.end() if cm else min(1200, len(text) - i - 1))
            return attrs, text[i:end], False
        i += 1
    return text[m.start():], "", True


def audit_file(path: Path, root: Path, min_sev: str) -> list:
    text = path.read_text(encoding="utf-8")
    rel = str(path.relative_to(root))
    findings = []
    styles = parse_styles(text)

    def add(sev, idx, what, fix):
        if SEV_ORDER[sev] <= SEV_ORDER[min_sev]:
            findings.append((sev, f"{rel}:{line_of(text, idx)}", what, fix))

    # ── interactive elements ──────────────────────────────────────────
    tag_re = re.compile(rf"<({'|'.join(INTERACTIVE)}|Switch|Button)\b")
    for m in tag_re.finditer(text):
        tag = m.group(1)
        attrs, body, self_closed = elem_block(text, m)
        has_label = any(f"{a}=" in attrs or f"{a} =" in attrs for a in LABEL_ATTRS)
        has_role = any(re.search(rf"\b{a}\s*=", attrs) for a in ROLE_ATTRS)
        has_hitslop = re.search(r"\bhitSlop\s*=", attrs)
        has_text = ("<Text" in body) or re.search(r"\bt\(\s*[\"']", body or "")
        literal_label = re.search(r"\baccessibilityLabel\s*=\s*[\"']([^\"']+)[\"']", attrs)

        if tag in INTERACTIVE:
            if not has_label:
                sev = "MEDIUM" if has_text else "HIGH"
                why = ("label likely inferred from text child — verify it reads cleanly"
                       if has_text else "icon-only control is silent to screen readers")
                add(sev, m.start(), f"<{tag}> without accessibilityLabel — {why}",
                    "spread {...a11y(label, hint, 'button', opts)} from src/a11y")
            elif literal_label:
                add("MEDIUM", m.start(),
                    f"hard-coded accessibilityLabel=\"{literal_label.group(1)}\" bypasses the i18n string table (doc 02 §6 — Hindi + English)",
                    "use t() string key, e.g. a11y(t('a11yBack', lang), …)")
            if not has_role:
                add("MEDIUM", m.start(), f"<{tag}> missing accessibilityRole",
                    "a11y() emits it; screen readers then announce 'button'")
            if re.search(r"\bdisabled\s*=", attrs) and "accessibilityState" not in attrs:
                add("LOW", m.start(), f"<{tag}> uses disabled={{}} but doesn't announce it",
                    "pass disabled via a11y(…, { disabled }) → accessibilityState")
            # ── size check ────────────────────────────────────────────
            sm = re.search(r"style\s*=\s*", attrs)
            dims = {"width": None, "height": None, "minWidth": None, "minHeight": None,
                    "padV": None, "padH": None, "pad": None, "flex": None, "stretch": False}
            if sm:
                st = attrs[sm.end():]
                for key in re.findall(r"\b\w+\.(\w+)\b", st):
                    if key in styles:
                        for k in dims:
                            if styles[key][k] is not None and dims[k] is None:
                                dims[k] = styles[key][k]
                        dims["stretch"] = dims["stretch"] or styles[key]["stretch"]
                for k, prop in (("width", "width"), ("height", "height")):
                    mm = re.search(rf"\b{prop}\s*:\s*(\d+(?:\.\d+)?)", st)
                    if mm and dims[k] is None:
                        dims[k] = float(mm.group(1))
            w = dims["width"] if dims["width"] is not None else dims["minWidth"]
            h = dims["height"] if dims["height"] is not None else dims["minHeight"]
            if (w is not None and w < MIN_TOUCH) or (h is not None and h < MIN_TOUCH):
                if has_hitslop:
                    add("LOW", m.start(),
                        f"touch target ≈{w or '?'}×{h or '?'} pt — hitSlop extends it; verify ≥{MIN_TOUCH} incl. slop",
                        "prefer ensureTouch(style) so the box itself is ≥44")
                else:
                    add("MEDIUM", m.start(),
                        f"touch target {w or '?'}×{h or '?'} pt < {MIN_TOUCH} pt",
                        "ensureTouch(style) from src/a11y, or hitSlop={slop()}")
            elif w is None and h is None and not dims["flex"] and not dims["stretch"]:
                pv = dims["padV"] or dims["pad"] or 0
                ph = dims["padH"] or dims["pad"] or 0
                if pv or ph:
                    est = 2 * pv + 18
                    if est < MIN_TOUCH or (ph and 2 * ph + 24 < MIN_TOUCH):
                        add("LOW", m.start(),
                            f"padding-only pressable (≈{est:.0f} pt tall) may fall under {MIN_TOUCH} pt",
                            "ensureTouch(style) floors minHeight at 44")
        elif tag == "Switch" and not has_label:
            add("MEDIUM", m.start(), "<Switch> without accessibilityLabel — announced as bare 'switch, on/off'",
                "add accessibilityLabel (the row text next to it isn't associated)")

    # ── <Text>/<TextInput> without a font-scale cap (aggregated) ──────
    bare_text_lines = []
    for m in re.finditer(r"<Text(?:Input)?\b", text):
        attrs, _, _ = elem_block(text, m)
        if "maxFontSizeMultiplier" not in attrs and "allowFontScaling" not in attrs:
            bare_text_lines.append(line_of(text, m.start()))
    if bare_text_lines:
        shown = ",".join(map(str, bare_text_lines[:12])) + ("…" if len(bare_text_lines) > 12 else "")
        add("LOW", 0,
            f"{len(bare_text_lines)} <Text>/<TextInput> without maxFontSizeMultiplier (lines {shown}) — system scale >130% can break layouts (doc 03)",
            "spread {...DYNAMIC_TYPE} from src/a11y on each <Text>")

    # ── live counters ─────────────────────────────────────────────────
    if "accessibilityLiveRegion" not in text and "useA11yAnnounce" not in text:
        for m in re.finditer(r"<Text\b[^>]*>([^<]{0,160}?)</Text>", text, re.S):
            inner = m.group(1)
            if re.search(r"\b(doseUg|navDose)\b", inner) and "receipt." not in inner:
                add("INFO", m.start(),
                    "live counter text (updates ~1 Hz during nav) has no announce path",
                    "wrap in {...liveRegion} + call useA11yAnnounce(text) — src/a11y")
                break
    return findings


def parse_v2t(theme_path: Path) -> dict:
    text = theme_path.read_text(encoding="utf-8")
    m = re.search(r"export const V2T\s*=\s*\{", text)
    if not m:
        return {}
    ob = text.index("{", m.end() - 1)
    body = text[ob:find_matching(text, ob)]
    return dict(re.findall(r"(\w+)\s*:\s*[\"'](#[0-9A-Fa-f]{3,8})[\"']", body))


def _lin(v):
    c = v / 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _lum(hexc):
    r, g, b = int(hexc[1:3], 16), int(hexc[3:5], 16), int(hexc[5:7], 16)
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def ratio(fg, bg):
    l1, l2 = _lum(fg), _lum(bg)
    return (max(l1, l2) + 0.05) / (min(l1, l2) + 0.05)


def contrast_audit(theme_path: Path) -> tuple:
    """(rows, failures): each row (token, hex, on-bg, on-surface, on-surface2, verdict)."""
    toks = parse_v2t(theme_path)
    if not toks:
        return [], []
    # tokens actually used as text/icon-on-surface colours in the codebase
    textish = ("text", "text2", "text3", "accent", "breath1", "breath2", "breath3")
    nontext = ("line", "out1", "out2", "out3", "pinDest") + tuple(k for k in toks if k.startswith("map"))
    bgs = [("bg", toks["bg"]), ("surface", toks["surface"]), ("surface2", toks["surface2"])]
    rows, fails = [], []
    for name, hexc in toks.items():
        if name in ("bg", "surface", "surface2"):
            continue
        rs = [ratio(hexc, b) for _, b in bgs]
        if name in nontext:
            verdict = "n/a — non-text (WCAG non-text floor is 3:1)"
        else:
            worst = min(rs)
            verdict = "PASS" if worst >= 4.5 else f"FAIL ({worst:.2f} < 4.5)"
            if worst < 4.5:
                fails.append((name, hexc, worst))
        rows.append((name, hexc, *[f"{r:.2f}" for r in rs], verdict))
    return rows, fails


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mobile-dir", default="Mobile")
    ap.add_argument("--min-severity", default="INFO", choices=list(SEV_ORDER))
    args = ap.parse_args()

    root = Path(args.mobile_dir).resolve()
    files = sorted(root.glob("src/**/*.tsx")) + sorted(root.glob("*.tsx"))
    findings = []
    for f in files:
        findings += audit_file(f, root, args.min_severity)
    findings.sort(key=lambda x: (SEV_ORDER[x[0]], x[1]))

    counts = {s: sum(1 for f in findings if f[0] == s) for s in SEV_ORDER}
    print(f"## Static findings — {len(findings)} total "
          f"(HIGH {counts['HIGH']} · MEDIUM {counts['MEDIUM']} · LOW {counts['LOW']} · INFO {counts['INFO']})\n")
    print("| Severity | Location | Finding | Suggested fix |")
    print("|---|---|---|---|")
    for sev, loc, what, fix in findings:
        print(f"| {sev} | `{loc}` | {what} | {fix} |")

    print("\n## Contrast audit — V2T tokens × dark backgrounds (WCAG 2.x ratio)\n")
    rows, fails = contrast_audit(root / "src/theme.ts")
    print("| Token | Hex | on `bg` | on `surface` | on `surface2` | Verdict (text needs ≥4.5) |")
    print("|---|---|---|---|---|---|")
    for r in rows:
        print(f"| `{r[0]}` | {r[1]} | {r[2]} | {r[3]} | {r[4]} | {r[5]} |")
    if fails:
        print(f"\n**{len(fails)} token(s) below the 4.5:1 floor the doc claims.**")
    else:
        print("\nAll text tokens meet the doc's 4.5:1 claim.")


if __name__ == "__main__":
    sys.exit(main())
