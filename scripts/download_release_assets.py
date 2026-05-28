#!/usr/bin/env python3

import argparse
import datetime as dt
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


GITHUB_API = "https://api.github.com"


def fail(message: str) -> "NoReturn":
    print(message, file=sys.stderr)
    raise SystemExit(1)


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


def load_config(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)

    apps = raw.get("apps")
    if not isinstance(apps, list) or not apps:
        fail("config/apps.json must contain a non-empty apps array.")

    for index, app in enumerate(apps, start=1):
        repo = app.get("repo")
        target_dir = app.get("target_dir")
        source_release_tag = app.get("source_release_tag")
        suffixes = app.get("asset_suffixes")
        if not isinstance(repo, str) or "/" not in repo:
            fail(f"apps[{index}] is missing a valid repo value like owner/name.")
        if not isinstance(target_dir, str) or not target_dir or "/" in target_dir or ".." in target_dir:
            fail(f"apps[{index}] has invalid target_dir. Use a simple folder name such as windows.")
        if not isinstance(source_release_tag, str) or not source_release_tag.strip():
            fail(f"apps[{index}] must define a non-empty source_release_tag.")
        if not isinstance(suffixes, list) or not suffixes or not all(isinstance(item, str) for item in suffixes):
            fail(f"apps[{index}] must define a non-empty asset_suffixes array.")
    return apps


def matching_assets(release: dict, suffixes: list[str]) -> list[dict]:
    release_assets = release.get("assets", [])
    return [
        asset
        for asset in release_assets
        if any(asset.get("name", "").endswith(suffix) for suffix in suffixes)
    ]


def download_asset(url: str, destination: Path, token: str | None) -> str:
    request = urllib.request.Request(url)
    request.add_header("User-Agent", "www-download-release-workflow")
    if token:
        request.add_header("Authorization", f"Bearer {token}")

    digest = hashlib.sha256()
    with urllib.request.urlopen(request) as response, destination.open("wb") as handle:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
            handle.write(chunk)
    return digest.hexdigest()


def render_release_notes(release_tag: str, manifest: dict) -> str:
    lines = [
        f"# {release_tag}",
        "",
        "Artifacts synced to Cloudflare R2 from source GitHub Releases.",
        "",
    ]
    for source in manifest["sources"]:
        lines.append(f"## {source['target_dir']} ({source['repo']})")
        lines.append("")
        lines.append(f"- Source tag: {source['source_release_tag']}")
        lines.append(f"- Source release: {source['release_html_url']}")
        for asset in source["assets"]:
            lines.append(
                f"- {asset['name']} -> {asset['r2_key']} (sha256: {asset['sha256']})"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--release-tag", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    token = os.environ.get("SOURCE_GH_TOKEN") or os.environ.get("GH_TOKEN")
    output_dir = Path(args.output_dir)
    release_root = output_dir / args.release_tag
    release_root.mkdir(parents=True, exist_ok=True)

    manifest = {
        "release_tag": args.release_tag,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "sources": [],
    }

    for app in load_config(Path(args.config)):
        source_release_tag = app["source_release_tag"].strip()
        release = github_json(
            f"/repos/{app['repo']}/releases/tags/{source_release_tag}", token, allow_404=True
        )
        if release is None:
            fail(
                f"Release tag {source_release_tag} was not found in source repo {app['repo']}."
            )

        assets = matching_assets(release, app["asset_suffixes"])
        if not assets:
            fail(
                f"Release {source_release_tag} in {app['repo']} has no assets matching {app['asset_suffixes']}."
            )

        target_dir = release_root / app["target_dir"]
        target_dir.mkdir(parents=True, exist_ok=True)
        manifest_source = {
            "repo": app["repo"],
            "target_dir": app["target_dir"],
            "source_release_tag": source_release_tag,
            "release_html_url": release.get("html_url"),
            "assets": [],
        }

        for asset in assets:
            destination = target_dir / asset["name"]
            sha256 = download_asset(asset["browser_download_url"], destination, token)
            manifest_source["assets"].append(
                {
                    "name": asset["name"],
                    "size": asset.get("size"),
                    "sha256": sha256,
                    "download_url": asset.get("browser_download_url"),
                    "r2_key": f"{args.release_tag}/{app['target_dir']}/{asset['name']}",
                }
            )

        manifest["sources"].append(manifest_source)

    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    (output_dir / "release-notes.md").write_text(
        render_release_notes(args.release_tag, manifest), encoding="utf-8"
    )


if __name__ == "__main__":
    main()