#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 README 人工精选表格按 Star 从高到低排序。

用法：
    GITHUB_TOKEN=xxx python3 scripts/sort_tables.py [--dry-run]

规则：
- 只处理「行内含 badgen star 徽章」的表格，表头与分隔行原样保留。
- 没有徽章的行（在线 demo、官方文档等）沉到该表末尾，彼此保持原有顺序。
- 自动榜区块 <!-- HOT:START/END --> 由 collect_hot.py 负责，这里跳过。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
BADGE = re.compile(r"badgen\.net/github/stars/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)")
HOT = re.compile(r"<!-- HOT:START -->.*?<!-- HOT:END -->", re.S)


def stars(repo: str, token: str | None, cache: dict[str, int]) -> int:
    if repo in cache:
        return cache[repo]
    req = urllib.request.Request(f"https://api.github.com/repos/{repo}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "awesome-jev-zh-sorter")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            cache[repo] = json.loads(resp.read().decode("utf-8")).get("stargazers_count", 0)
    except Exception as exc:  # noqa: BLE001
        print(f"  取 star 失败 {repo}：{exc}", file=sys.stderr)
        cache[repo] = -1
    return cache[repo]


def sort_block(lines: list[str], token: str, cache: dict[str, int]) -> list[str]:
    """lines 是一段连续的表格行，含表头与分隔行。"""
    if len(lines) < 3 or ":--" not in lines[1]:
        return lines
    head, sep, body = lines[0], lines[1], lines[2:]
    if not any(BADGE.search(l) for l in body):
        return lines

    starred, plain = [], []
    for idx, line in enumerate(body):
        m = BADGE.search(line)
        if m:
            starred.append((-stars(m.group(1), token, cache), idx, line))
        else:
            plain.append((idx, line))
    starred.sort()
    return [head, sep] + [l for _, _, l in starred] + [l for _, l in plain]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""

    text = README.read_text(encoding="utf-8")
    hot = HOT.search(text)
    placeholder = "\x00HOT\x00"
    if hot:
        text = text.replace(hot.group(0), placeholder)

    cache: dict[str, int] = {}
    out, block, moved = [], [], 0
    for line in text.split("\n"):
        if line.lstrip().startswith("|"):
            block.append(line)
            continue
        if block:
            new = sort_block(block, token, cache)
            moved += sum(1 for a, b in zip(block, new) if a != b)
            out.extend(new)
            block = []
        out.append(line)
    if block:
        new = sort_block(block, token, cache)
        moved += sum(1 for a, b in zip(block, new) if a != b)
        out.extend(new)

    result = "\n".join(out)
    if hot:
        result = result.replace(placeholder, hot.group(0))

    print(f"查询 {len(cache)} 个仓库，调整 {moved} 行。", file=sys.stderr)
    if args.dry_run:
        return 0
    README.write_text(result, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
