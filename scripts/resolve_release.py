#!/usr/bin/env python3

import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request


SEMVER_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")
GITHUB_API = "https://api.github.com"


def fail(message: str) -> "NoReturn":
    print(message, file=sys.stderr)
    raise SystemExit(1)


def normalize_tag(raw_tag: str) -> str:
    match = SEMVER_RE.fullmatch(raw_tag.strip())
    if not match:
        fail(
            "The workflow tag input must be a semantic version such as v1.2.3 or 1.2.3."
        )
    major, minor, patch = match.groups()
    return f"v{major}.{minor}.{patch}"


def increment_patch(tag: str) -> str:
    match = SEMVER_RE.fullmatch(tag)
    if not match:
        fail(f"Cannot increment non-semver tag: {tag}")
    major, minor, patch = (int(part) for part in match.groups())
    return f"v{major}.{minor}.{patch + 1}"


def github_json(path: str, token: str | None, allow_404: bool = False) -> dict | None:
    request = urllib.request.Request(f"{GITHUB_API}{path}")
    request.add_header("Accept", "application/vnd.github+json")
    request.add_header("X-GitHub-Api-Version", "2022-11-28")
    request.add_header("User-Agent", "www-download-release-workflow")
    if token:
        request.add_header("Authorization", f"Bearer {token}")

    try:
        with urllib.request.urlopen(request) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        if allow_404 and error.code == 404:
            return None
        body = error.read().decode("utf-8", errors="replace")
        fail(f"GitHub API request failed for {path}: HTTP {error.code} {body}")


def resolve_tag_commit(repo: str, tag: str, token: str | None) -> str | None:
    encoded_tag = urllib.parse.quote(tag, safe="")
    ref = github_json(f"/repos/{repo}/git/ref/tags/{encoded_tag}", token, allow_404=True)
    if ref is None:
        return None

    target = ref["object"]
    while target["type"] == "tag":
        tag_object = github_json(f"/repos/{repo}/git/tags/{target['sha']}", token)
        target = tag_object["object"]

    if target["type"] != "commit":
        fail(f"Tag {tag} for {repo} resolved to unsupported git object type: {target['type']}")
    return target["sha"]


def resolve_main_head(repo: str, token: str | None) -> str:
    branch = github_json(f"/repos/{repo}/branches/main", token)
    return branch["commit"]["sha"]


def latest_release_tag(repo: str, token: str | None) -> str | None:
    release = github_json(f"/repos/{repo}/releases/latest", token, allow_404=True)
    if release is None:
        return None
    tag_name = release.get("tag_name")
    if not tag_name:
        fail("Latest GitHub Release is missing tag_name.")
    return normalize_tag(tag_name)


def write_outputs(values: dict[str, str]) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        return
    with open(output_path, "a", encoding="utf-8") as handle:
        for key, value in values.items():
            handle.write(f"{key}={value}\n")


def main() -> None:
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not repo:
        fail("GITHUB_REPOSITORY is required.")

    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    requested_tag = os.environ.get("INPUT_TAG", "").strip()

    if requested_tag:
        release_tag = normalize_tag(requested_tag)
        version_source = "input"
    else:
        current_tag = latest_release_tag(repo, token)
        release_tag = increment_patch(current_tag) if current_tag else "v0.0.1"
        version_source = "auto"

    target_commit = resolve_tag_commit(repo, release_tag, token)
    tag_exists = target_commit is not None
    if target_commit is None:
        target_commit = resolve_main_head(repo, token)

    result = {
        "release_tag": release_tag,
        "target_commit": target_commit,
        "tag_exists": "true" if tag_exists else "false",
        "version_source": version_source,
    }

    write_outputs(result)
    print(json.dumps(result))


if __name__ == "__main__":
    main()