#!/usr/bin/env python3
"""Maintain README.md: add entries to sections and check the list for problems.

Usage:
  python3 scripts/readme_tool.py check             # format + local image checks
  python3 scripts/readme_tool.py check --online    # also test each URL over HTTP
  python3 scripts/readme_tool.py add "Front-End Development" "### Design" \"https://example.com" "Name" "Short description"
  python3 scripts/readme_tool.py sections          # list sections and their headings

Standard library only.
"""

import argparse
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

README = Path(__file__).resolve().parent.parent / "README.md"

ENTRY_RE = re.compile(r"^- \[(?P<name>[^\]]+)\]\((?P<url>[^)\s]+)\)(?P<desc>.*)$")
LINK_RE = re.compile(r"\[[^\]]*\]\((?P<target>[^)\s]+)\)")
HEADING_RE = re.compile(r"^(?P<level>#{1,6})\s+(?P<title>.+?)\s*$")


def read_lines():
    return README.read_text(encoding="utf-8").splitlines()


def find_section(lines, section):
    """Return (start, end) line indexes of a '## ' section by title."""
    start = None
    for i, line in enumerate(lines):
        m = HEADING_RE.match(line)
        if (
            m
            and m.group("level") == "##"
            and m.group("title").lower() == section.lower()
        ):
            start = i
            break
    if start is None:
        sys.exit(f"Section not found: {section!r}")
    end = len(lines)
    for j in range(start + 1, len(lines)):
        m = HEADING_RE.match(lines[j])
        if m and m.group("level") in ("#", "##"):
            end = j
            break
    return start, end


def check(online):
    lines = read_lines()
    problems = []
    seen_urls = {}
    for n, line in enumerate(lines, 1):
        if not line.startswith("- ["):
            continue
        m = ENTRY_RE.match(line)
        if not m:
            problems.append(
                f"L{n}: malformed entry, expected '- [Name](url) description'"
            )
            continue
        url = m.group("url")
        if url.startswith("#"):  # table-of-contents anchor, not a resource entry
            continue
        if not m.group("desc").strip():
            problems.append(f"L{n}: missing description for {m.group('name')!r}")
        if url in seen_urls:
            problems.append(f"L{n}: duplicate URL also on L{seen_urls[url]}: {url}")
        seen_urls.setdefault(url, n)

    for n, line in enumerate(lines, 1):
        for lm in LINK_RE.finditer(line):
            target = lm.group("target")
            if target.startswith(("#", "mailto:", "tel:")):
                continue
            if re.match(r"^https?://", target):
                continue
            if target.startswith("./") or not re.match(r"^[a-z]+:", target):
                path = (README.parent / target.split("#")[0]).resolve()
                if not path.exists():
                    problems.append(f"L{n}: local path does not exist: {target}")
                continue
            problems.append(f"L{n}: unsupported link target: {target}")

    if online:
        for url, n in seen_urls.items():
            if not url.startswith("http"):
                continue
            status = probe(url)
            if status is not None:
                problems.append(f"L{n}: {status}: {url}")

    if problems:
        print("\n".join(problems))
        print(f"\n{len(problems)} problem(s) found.")
        return 1
    print(f"OK: {len(seen_urls)} unique links, no problems found.")
    return 0


def probe(url):
    """Return None if the URL responds with <400, else a short error string."""
    req = urllib.request.Request(
        url, method="HEAD", headers={"User-Agent": "readme-tool/1.0"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return None if resp.status < 400 else f"HTTP {resp.status}"
    except urllib.error.HTTPError as e:
        if e.code in (403, 405):  # some servers reject HEAD; retry with GET
            return _probe_get(url)
        return f"HTTP {e.code}"
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return f"unreachable ({getattr(e, 'reason', e)})"


def _probe_get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "readme-tool/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return None if resp.status < 400 else f"HTTP {resp.status}"
    except urllib.error.HTTPError as e:
        return f"HTTP {e.code}"
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return f"unreachable ({getattr(e, 'reason', e)})"


def add(section, subsection, url, name, description):
    lines = read_lines()
    s_start, s_end = find_section(lines, section)
    sub_idx = None
    for i in range(s_start + 1, s_end):
        if lines[i].strip().lower() == subsection.lower():
            sub_idx = i
            break
    if sub_idx is None:
        sys.exit(f"Subsection {subsection!r} not found in {section!r}")

    insert_at = sub_idx + 1
    for i in range(sub_idx + 1, s_end):
        if HEADING_RE.match(lines[i]):
            break
        if lines[i].startswith("- ["):
            insert_at = i + 1
    entry = f"- [{name}]({url}) {description}".rstrip()
    lines.insert(insert_at, entry)
    README.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Added to {section} > {subsection} (line {insert_at + 1}): {entry}")
    return 0


def sections():
    for n, line in enumerate(read_lines(), 1):
        m = HEADING_RE.match(line)
        if m and m.group("level") in ("##", "###"):
            indent = "  " if m.group("level") == "###" else ""
            print(f"L{n}: {indent}{m.group('title')}")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_check = sub.add_parser("check", help="validate README entries and links")
    p_check.add_argument(
        "--online", action="store_true", help="also test URLs over HTTP"
    )

    p_add = sub.add_parser("add", help="add an entry under a section/subsection")
    p_add.add_argument("section", help="'## ' heading title, e.g. 'Roadmaps'")
    p_add.add_argument("subsection", help="'### ' heading line, e.g. '### Design'")
    p_add.add_argument("url")
    p_add.add_argument("name")
    p_add.add_argument("description")

    sub.add_parser("sections", help="list headings")

    args = parser.parse_args()
    if args.cmd == "check":
        return check(args.online)
    if args.cmd == "add":
        return add(args.section, args.subsection, args.url, args.name, args.description)
    return sections()


if __name__ == "__main__":
    sys.exit(main())
