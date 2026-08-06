---
name: azure-container-registry
description: Use for Azure Container Registry image builds, especially ACR remote builds, minimal Docker contexts, cross-platform context helpers, build verification, and avoiding noisy repo roots during az acr build.
---

# Azure Container Registry

Use this skill for ACR image builds and remote build context preparation. Keep Container Apps deployment details in `azure-container-apps`.

## Remote Build Contexts

ACR remote build can fail or hang before queuing when the local workspace has heavy or unusual folders such as agent caches, worktrees, generated outputs, browser artifacts, virtual environments, or nested tooling state.

Before running `az acr build`, prefer a cross-platform helper:

```bash
python3 <this-skill-dir>/scripts/build_acr_context.py --dry-run
python3 <this-skill-dir>/scripts/build_acr_context.py --output-dir .acr-context --force
az acr build --registry <registry-name> --image <repo>:<tag> .acr-context
```

Resolve `<this-skill-dir>` to the directory containing this `SKILL.md`, for example `~/.codex/skills/azure-skills/azure-container-registry` after workbench installation. The helper is bundled with this skill so it remains available when the skill is installed on macOS/Linux.

The helper reads common Dockerfile `COPY` and `ADD` sources, includes common root manifests and lockfiles, and prints the generated context path. Use `--include <path-or-glob>` for project-specific files that are needed at build time but are not visible from Dockerfile copy statements or use unusual Dockerfile syntax.

If the target project has its own shell-specific helpers, prefer the project helper and choose by local shell and OS:

- PowerShell: `scripts/build_acr_context.ps1`
- bash/zsh: `scripts/build_acr_context.sh`

Submit the generated context, not the noisy repository root, when root packaging is unreliable.

## What To Include

The minimal context should include only what the Dockerfile actually copies, for example:

- `Dockerfile`
- `.dockerignore`
- common root files such as `package.json`, `pnpm-lock.yaml`, `pnpm-workspace.yaml`, `pyproject.toml`, `uv.lock`, and `README.md` when present
- target app source
- related packages copied by the Dockerfile
- required config files

Default exclusions should cover `.git/`, `node_modules/`, `.turbo/`, `.next/`, `dist/`, coverage output, temp folders, worktrees, and agent caches.

## Build Verification

After an ACR build, verify the artifact rather than trusting the build log alone:

```bash
az acr repository list --name <registry-name> --output table
az acr repository show-tags --name <registry-name> --repository <repo> --output table
```

Keep image tags explicit. Avoid reusing an ambiguous tag during incident response unless the deployment process records the digest or revision that consumed it.

## When To Open Docs

- ACR Tasks and remote builds: <https://learn.microsoft.com/en-us/azure/container-registry/container-registry-tasks-overview>
- `az acr build`: <https://learn.microsoft.com/en-us/cli/azure/acr?view=azure-cli-latest#az-acr-build>
- ACR repositories: <https://learn.microsoft.com/en-us/azure/container-registry/container-registry-repositories>
