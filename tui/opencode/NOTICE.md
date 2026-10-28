# Provenance (watterson-environment, DEC-027)

This directory is the TUI's code. It is ours to change. It came from
opencode, `github.com/anomalyco/opencode`, branch `dev` at
`501b15af26915ba52682e20e220e7e137e89e92f` (2026-10-18, version 2.0.32),
taken from the user's fork `github.com/majax7714/opencode`. Upstream is not
tracked (DEC-026). opencode's MIT license is kept in `LICENSE`.

Imported as is, except for the following.

Left out (not used by the TUI build, `packages/cli`):
- Packages: `app`, `console`, `containers`, `desktop`,
  `effect-drizzle-sqlite`, `function`, `gui-extensions`, `identity`,
  `plugins`, `posts`, `sdk`, `session-ui`, `stats`, `storybook`, `web`.
- Top-level: `sdks/`, `services/`, `infra/`, `github/`, `nix/`,
  `flake.nix`, `flake.lock`, `salesforce/`, `specs/`, `perf/`, `install`,
  `sst.config.ts`, `sst-env.d.ts`, the translated `README.*.md`,
  `screenshot-uk.png`, `STATS.md`, `CHANGELOG.md`, `CONTRIBUTING.md`,
  `SECURITY.md`, `.github/` (except `TEAM_MEMBERS`, which
  `packages/script` reads), `.husky/`, `.opencode/`, `.vscode/`, `.zed/`,
  `.dockerignore`, `.gitleaksignore`.
- Release scripts: `script/{changelog,duplicate-pr,publish,publish-winget,raw-changelog,release,stats,update-artifact,version}.ts`,
  `script/sign-windows.ps1`, `script/{github,drive,hooks}/`, and
  `packages/cli/script/{publish,publish-aur,publish-homebrew}.ts` and
  `entitlements.plist`.
- `packages/ai/test/` (recorded provider fixtures, 15 MB).

Changed:
- `package.json`: workspaces are `packages/*` only; the scripts for the
  removed packages, `prepare` (husky), `sso` and `random` are removed; so
  are the devDependencies `@actions/artifact`, `husky` and `sst` and the
  dependencies `@aws-sdk/client-s3` and `heap-snapshot-toolkit`.
- `bun.lock`: pruned by `bun install` to match (no version changed).

Later changes are ordinary commits in watterson-environment.
