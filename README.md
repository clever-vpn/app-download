# App Download Release Workflow

This repository exists only to collect app artifacts from other repositories' GitHub Releases and publish them into Cloudflare R2.

## Configuration

Edit `config/apps.json` and list each source repository, the destination folder under the release tag, and the asset suffixes to copy.

```json
{
  "apps": [
    {
      "repo": "your-org/clever-vpn-windows",
      "source_release_tag": "v1.2.3",
      "target_dir": "windows",
      "asset_suffixes": [".exe", ".msi"]
    },
    {
      "repo": "your-org/clever-vpn-apple",
      "source_release_tag": "v1.2.3",
      "target_dir": "apple",
      "asset_suffixes": [".dmg", ".pkg"]
    }
  ]
}
```

The workflow input `tag` is only for this repository's release tag and the top-level R2 directory name. Each source repository release tag is read from `source_release_tag` in the config file.

Each workflow run writes files to `R2_BUCKET/<tag>/<target_dir>/...`.

## Workflow behavior

The manual workflow is defined in `.github/workflows/publish-to-r2.yml`.

- If `tag` is provided and already exists in this repository, the workflow uses the commit currently pointed to by that tag.
- If `tag` is provided and does not exist, the workflow uses `main` HEAD during prepare, then creates the missing tag only in the final publish stage.
- If `tag` is omitted, the workflow reads the latest GitHub Release tag in this repository, increments the patch version, and uses that `v`-prefixed tag. If no release exists yet, it starts at `v0.0.1`.
- If a newly created tag cannot be paired with a successful GitHub Release write, the workflow deletes that tag before the job exits with failure.

## Required GitHub secrets and variables

- GitHub secret: `BW_SM_ACCESS_TOKEN`
- GitHub variable: `BW_CLOUD_REGION` when not using the default Bitwarden US region
- GitHub variable: `R2_ACCOUNT_ID`
- GitHub variable: `R2_BUCKET`
- GitHub variable: `BW_SECRET_ID_R2_ACCESS_KEY_ID`
- GitHub variable: `BW_SECRET_ID_R2_SECRET_ACCESS_KEY`
- GitHub variable: `BW_SECRET_ID_SOURCE_GH_TOKEN`

`BW_SECRET_ID_SOURCE_GH_TOKEN` should point to a Bitwarden secret containing a GitHub token that can read the source repositories when they are private.

## Development Rules

The project copies the repository workflow rules into `.github/copilot-instructions.md` and provides a local Git pre-push hook in `.githooks/pre-push` that blocks pushes to `main`.

Enable the hook locally from the repository root:

```bash
git config core.hooksPath www-download/.githooks
chmod +x www-download/.githooks/pre-push
```