#!/usr/bin/env python3
"""Calculate the next conventional-commit release version from Git tags."""

import re
import subprocess


def git(*args):
    return subprocess.check_output(["git", *args], text=True).strip()


def next_version(tags, messages):
    versions = [tuple(map(int, tag[1:].split("."))) for tag in tags
                if re.fullmatch(r"v\d+\.\d+\.\d+", tag)]
    if not versions:
        return "0.1.0"
    major, minor, patch = max(versions)
    if re.search(r"(?m)^(?:[\w-]+(?:\([^\n)]*\))?!:|BREAKING CHANGE:)", messages):
        return f"{major + 1}.0.0"
    if re.search(r"(?m)^feat(?:\([^\n)]*\))?:", messages):
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


if __name__ == "__main__":
    # Only consider tags on this branch's history.
    tags = git("tag", "--merged", "HEAD").splitlines()
    valid = [tag for tag in tags if re.fullmatch(r"v\d+\.\d+\.\d+", tag)]
    latest = max(valid, key=lambda tag: tuple(map(int, tag[1:].split(".")))) if valid else None
    messages = git("log", "--format=%B", f"{latest}..HEAD" if latest else "HEAD")
    print(next_version(tags, messages))
