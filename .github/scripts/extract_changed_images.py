#!/usr/bin/env python3
"""
Extract container image references from YAML files changed in a PR.

Reads file paths from CHANGED_FILES (newline-separated), parses each as YAML,
and emits one image reference per line on stdout. Image refs are stripped of
@sha256:... digests so Trivy can pull the tagged image directly.

Two patterns are detected:
- inline scalars matching `<repo>:<tag>` or `<repo>:<tag>@sha256:...`
- nested objects with `repository:` + `tag:` siblings (bjw-s app-template idiom)
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.stderr.write("PyYAML not installed\n")
    sys.exit(1)


# repository looks like:  ghcr.io/foo/bar  or  docker.io/library/nginx  or  nginx
REPO_RE = re.compile(r"^[a-z0-9][a-z0-9.\-]*(/[a-z0-9][a-z0-9.\-_]*)*(/[a-z0-9][a-z0-9.\-_]*)?$")
# tag is a simple version-ish string
TAG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._\-]*$")


def strip_digest(ref: str) -> str:
    return ref.split("@", 1)[0]


def looks_like_image(s: str) -> bool:
    if not isinstance(s, str):
        return False
    # need at least one : separator and one slash (registry/path:tag)
    if ":" not in s or "/" not in s:
        return False
    # base ref before @ digest
    base = s.split("@", 1)[0]
    parts = base.rsplit(":", 1)
    if len(parts) != 2:
        return False
    repo, tag = parts
    return bool(REPO_RE.match(repo) and TAG_RE.match(tag))


def walk(node, out: set[str]) -> None:
    if isinstance(node, dict):
        # bjw-s pattern: nested object with repository + tag
        repo = node.get("repository")
        tag = node.get("tag")
        if isinstance(repo, str) and isinstance(tag, (str, int, float)):
            tag_s = str(tag)
            if REPO_RE.match(repo) and TAG_RE.match(tag_s):
                out.add(strip_digest(f"{repo}:{tag_s}"))
        # also handle simple image: ref strings
        img = node.get("image")
        if isinstance(img, str) and looks_like_image(img):
            out.add(strip_digest(img))
        # k8s image volume pattern: { reference: 'ghcr.io/...:tag' }
        ref = node.get("reference")
        if isinstance(ref, str) and looks_like_image(ref):
            out.add(strip_digest(ref))
        for v in node.values():
            walk(v, out)
    elif isinstance(node, list):
        for v in node:
            walk(v, out)


def main() -> int:
    changed = os.environ.get("CHANGED_FILES", "").splitlines()
    images: set[str] = set()
    for path in changed:
        p = Path(path.strip())
        if not p.is_file() or p.suffix not in (".yaml", ".yml"):
            continue
        try:
            with p.open() as f:
                for doc in yaml.safe_load_all(f):
                    walk(doc, images)
        except yaml.YAMLError as e:
            sys.stderr.write(f"warn: {path}: {e}\n")
            continue

    for img in sorted(images):
        print(img)
    return 0


if __name__ == "__main__":
    sys.exit(main())
