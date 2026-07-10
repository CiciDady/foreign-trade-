# AGENTS.md

## Cursor Cloud specific instructions

- This repository is currently an **empty scaffold**. The only tracked file is `README.md`
  (contents: `# foreign-trade-`). There is no application code, no dependency manifests
  (no `package.json`, `requirements.txt`, `go.mod`, etc.), no setup scripts, no tests,
  no lint config, and no build/run tooling.
- Because there are no dependency manifests, the startup **update script is intentionally a
  no-op** (it just prints a message). Once real project code and a dependency manifest are
  added (e.g. `package.json`, `requirements.txt`), update the startup script to install
  those dependencies (e.g. `npm install`, `pip install -r requirements.txt`).
- There is nothing to lint, test, build, or run yet. Any "run the app" request cannot be
  fulfilled until an application is added to the repo.
- Available runtimes in this environment: Node.js `v22.x`, Python `3.12.x`, Git `2.43.x`.
