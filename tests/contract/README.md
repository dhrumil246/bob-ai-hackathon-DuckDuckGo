# API contract tests

A safety net for every HTTP endpoint, so changes for industry readiness cannot silently
break the web app or change what the system tells an engineer.

## What is checked

For 50 requests across all 21 endpoints (both lot types, unknown lots, valid and invalid
uploads, every Pipeline Studio preset, and `/api/chat` with the tool chain working and
deliberately failing):

| Snapshot | Holds | A difference means |
|---|---|---|
| `snapshots/shapes.json` | status, content type, JSON keys and value types | the web app may break. Never accidental |
| `snapshots/behaviour.json` | the JSON body, with timings, timestamps and generated ids masked | the system now answers differently. Fine when intended, but say so in the pull request |

Not covered yet: `/api/stream/fab` (an open-ended event stream).

## Environment

`conftest.py` forces the mock LLM, removes provider keys, blocks outbound network
connections, and redirects the feedback and prior-read stores to a temporary folder.
Tests never spend model quota and never write into the repository.

## Running

Tests run in GitHub Actions on every push and pull request (`.github/workflows/tests.yml`),
not on team laptops.

## Regenerating snapshots after an intended change

1. GitHub → Actions → **Tests** → **Run workflow** → choose your branch → tick
   `update_snapshots` → Run. Or, with the GitHub CLI:
   `gh workflow run tests.yml -r <branch> -f update_snapshots=true`
2. The workflow commits the new snapshots to your branch.
3. GitHub does not start a new test run for a commit made by a workflow. Run **Tests**
   once more on the branch (without `update_snapshots`), or push your next commit.
4. Review the snapshot diff in the pull request. It is the record of what changed.
