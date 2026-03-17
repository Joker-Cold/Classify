#!/usr/bin/env python3
"""
Extract Claude.ai chat from MHTML to Markdown.
Parses the saved MHTML page, identifies user / assistant messages by
data-testid="user-message" and class="font-claude-response", then
outputs a clean Markdown conversation file.

Usage:
    python mhtml_to_md.py data/chat.mhtml
    python mhtml_to_md.py data/chat.mhtml -o output/chat.md
"""
import argparse
import email
import quopri
import re
import sys
from html.parser import HTMLParser
from pathlib import Path


# ── Quoted-printable + MHTML decode ────────────────────────────────────

def _extract_html_from_mhtml(mhtml_path: str) -> str:
    """Extract the main HTML part from an MHTML file."""
    raw = Path(mhtml_path).read_bytes()
    msg = email.message_from_bytes(raw)

    # Walk MIME parts, find the text/html one
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            if ct == "text/html":
                payload = part.get_payload(decode=True)
                if payload:
                    return payload.decode("utf-8", errors="replace")
        # Fallback: decode entire body as quoted-printable
        payload = msg.get_payload(decode=True)
        if payload:
            return payload.decode("utf-8", errors="replace")
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            return payload.decode("utf-8", errors="replace")

    # Last resort: brute-force QP decode
    text = raw.decode("utf-8", errors="replace")
    return quopri.decodestring(text.encode()).decode("utf-8", errors="replace")


# ── HTML → structured messages ─────────────────────────────────────────

class _ChatExtractor(HTMLParser):
    """State-machine HTML parser that extracts user/assistant messages."""

    def __init__(self):
        super().__init__()
        self.messages = []       # [(role, text)]
        self._role = None        # "user" | "assistant" | None
        self._depth = 0          # nesting depth inside a message block
        self._buf = []           # text accumulator
        self._tag_stack = []     # track block-level tags for markdown
        self._in_code = False
        self._code_lang = ""
        self._skip = False       # skip non-content tags (button, svg, etc.)
        self._skip_depth = 0

    # ── helpers ────────────────────────────────────────────────
    def _attr(self, attrs, key):
        for k, v in attrs:
            if k == key:
                return v or ""
        return None

    def _has_class(self, attrs, cls):
        classes = self._attr(attrs, "class") or ""
        return cls in classes.split()

    def _flush(self):
        if self._role and self._buf:
            text = "".join(self._buf).strip()
            if text:
                self.messages.append((self._role, text))
        self._buf = []
        self._role = None
        self._depth = 0

    # ── parser callbacks ──────────────────────────────────────
    def handle_starttag(self, tag, attrs):
        # Skip non-content elements
        if tag in ("button", "svg", "path", "style", "script", "iframe", "img"):
            self._skip = True
            self._skip_depth = 1
            return
        if self._skip:
            self._skip_depth += 1
            return

        # Detect user message start
        if self._attr(attrs, "data-testid") == "user-message":
            self._flush()
            self._role = "user"
            self._depth = 1
            self._buf = []
            return

        # Detect assistant message start
        if self._has_class(attrs, "font-claude-response"):
            self._flush()
            self._role = "assistant"
            self._depth = 1
            self._buf = []
            return

        if self._role:
            self._depth += 1

            # Markdown formatting
            if tag == "p":
                if self._buf and not self._buf[-1].endswith("\n\n"):
                    self._buf.append("\n\n")
            elif tag in ("h1", "h2", "h3", "h4"):
                level = int(tag[1])
                self._buf.append("\n\n" + "#" * level + " ")
            elif tag == "li":
                self._buf.append("\n- ")
            elif tag == "tr":
                self._buf.append("\n|")
            elif tag in ("td", "th"):
                self._buf.append(" ")
            elif tag == "br":
                self._buf.append("\n")
            elif tag == "hr":
                self._buf.append("\n\n---\n\n")
            elif tag == "strong" or tag == "b":
                self._buf.append("**")
            elif tag == "em" or tag == "i":
                self._buf.append("*")
            elif tag == "code":
                # Check if inside a <pre>
                if self._tag_stack and self._tag_stack[-1] == "pre":
                    # Code block language from class
                    lang = ""
                    cls = self._attr(attrs, "class") or ""
                    m = re.search(r"language-(\w+)", cls)
                    if m:
                        lang = m.group(1)
                    self._buf.append(f"\n```{lang}\n")
                    self._in_code = True
                else:
                    self._buf.append("`")
            elif tag == "pre":
                pass  # handled by code inside it
            elif tag == "ol":
                self._buf.append("\n")
            elif tag == "ul":
                self._buf.append("\n")

            self._tag_stack.append(tag)

    def handle_endtag(self, tag):
        if self._skip:
            self._skip_depth -= 1
            if self._skip_depth <= 0:
                self._skip = False
            return

        if self._role:
            self._depth -= 1

            if self._tag_stack and self._tag_stack[-1] == tag:
                self._tag_stack.pop()

            if tag in ("strong", "b"):
                self._buf.append("**")
            elif tag in ("em", "i"):
                self._buf.append("*")
            elif tag == "code":
                if self._in_code:
                    self._buf.append("\n```\n")
                    self._in_code = False
                else:
                    self._buf.append("`")
            elif tag in ("td", "th"):
                self._buf.append(" |")
            elif tag == "thead":
                # Insert markdown table separator after header
                self._buf.append("\n|")
                # We don't know column count, will fix in post-processing
                self._buf.append(" --- |")

            if self._depth <= 0:
                self._flush()

    def handle_data(self, data):
        if self._skip:
            return
        if self._role:
            self._buf.append(data)


def _postprocess(text: str) -> str:
    """Clean up extracted text."""
    # Fix table separators: ensure correct column count
    lines = text.split("\n")
    result = []
    for i, line in enumerate(lines):
        if line.strip().startswith("|") and " --- |" in line and i > 0:
            # Count columns from previous header line
            prev = result[-1] if result else ""
            cols = prev.count("|") - 1
            if cols > 0:
                line = "|" + " --- |" * cols
        result.append(line)
    text = "\n".join(result)

    # Collapse excessive blank lines
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    # Remove trailing spaces
    text = re.sub(r" +\n", "\n", text)
    return text.strip()


# ── Main ───────────────────────────────────────────────────────────────

def extract_chat(mhtml_path: str, output_path: str) -> Path:
    """Extract chat from MHTML and write as Markdown."""
    print(f"  Decoding MHTML...")
    html = _extract_html_from_mhtml(mhtml_path)
    print(f"  HTML size: {len(html):,} chars")

    print(f"  Parsing messages...")
    parser = _ChatExtractor()
    parser.feed(html)
    parser._flush()  # flush last message

    messages = parser.messages
    print(f"  Found {len(messages)} messages ({sum(1 for r,_ in messages if r=='user')} user, {sum(1 for r,_ in messages if r=='assistant')} assistant)")

    # Build markdown
    title = Path(mhtml_path).stem.replace(" - Claude", "")
    md_lines = [f"# {title}\n"]

    for role, text in messages:
        text = _postprocess(text)
        if role == "user":
            md_lines.append(f"\n## User\n\n{text}\n")
        else:
            md_lines.append(f"\n## Assistant\n\n{text}\n")

    md = "\n".join(md_lines)

    out = Path(output_path)
    out.write_text(md, encoding="utf-8")
    print(f"  OK  {out.name}  ({len(md):,} chars)")
    return out


def main():
    p = argparse.ArgumentParser(description="Extract Claude.ai chat from MHTML to Markdown")
    p.add_argument("input", help="Input MHTML file")
    p.add_argument("-o", "--output", default=None,
                   help="Output Markdown file (default: output/<stem>.md)")
    args = p.parse_args()

    inp = Path(args.input).resolve()
    if not inp.exists():
        print(f"ERROR: File not found: {inp}")
        sys.exit(1)

    if args.output:
        out = Path(args.output).resolve()
    else:
        out = inp.parent.parent / "output" / f"{inp.stem.replace(' - Claude', '')}.md"

    print("=" * 60)
    print("MHTML -> Markdown Chat Extraction")
    print("=" * 60)
    print(f"Input : {inp.name}")
    print(f"Output: {out}")
    print()

    extract_chat(str(inp), str(out))

    print()
    print(f"Done. Output: {out}")
    print("=" * 60)


if __name__ == "__main__":
    main()
