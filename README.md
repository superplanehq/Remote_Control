# Factory Remote

**Run your SuperPlane AI software factory from your badge.**

Factory Remote puts your SuperPlane factory board on the Universe 2026 badge:
the same Backlog, line step (Implement), Verify and Done lanes as the
SuperPlane dashboard. You can move work forward without a laptop:

| Lane | What you see | What you can do |
|------|--------------|-----------------|
| Backlog | Tasks from GitHub issues, age, confidence meter, owner | **Hold SELECT: Start on Implement.** The task is dispatched to the factory line and the agent starts working. |
| Implement (each line step) | Tasks the agent is working on, live time, failed or queued steps | Watch progress. The task moves to Verify by itself when the agent's step passes. |
| Verify | Tasks with an open pull request | Open the task to see the PR, its checks and **every file the agent changed** (line by line diff). **Hold SELECT: Merge** when SuperPlane says the PR can merge. |
| Done | Merged and closed work | See which PR closed it. |

When a task arrives in Verify, the badge shows a toast and the four case
lights blink, so you know a decision is waiting. While something waits in
Verify the lights breathe slowly; while an agent is working they chase.

## Controls

| Screen | UP / DOWN | LEFT / RIGHT | SELECT | BACK | MENU |
|--------|-----------|--------------|--------|------|------|
| Board | task | lane | open task | | refresh |
| Task | move (button, files) | | hold: Start / Merge; on a file: view diff | board | refresh |
| Diff | scroll (hold to scroll fast) | previous / next file | next page | task | |

HOME always returns to the launcher. Both actions need a one-second hold, so a
stray tap never starts or merges anything.

## Setup

Add these to the badge's root `secrets.py` (double-tap RESET for disk mode):

```python
WIFI_SSID = "..."
WIFI_PASSWORD = "..."
SUPERPLANE_TOKEN = "..."       # SuperPlane > Profile > API token (or a service account token)
SUPERPLANE_WORKSPACE = "SC"    # optional: workspace key or name; blank = first workspace
SUPERPLANE_LINE = ""           # optional: factory line name; blank = first line
GITHUB_TOKEN = "..."           # optional: needed to show changed files of private repos
```

The token stays on the badge and is never shown on screen. Anyone who holds
the badge can start and merge tasks, so use a token with only the access it
needs and revoke it if the badge is lost.

**Demo mode:** with no `SUPERPLANE_TOKEN`, the app runs an offline demo
factory ("Sup Community") so you can rehearse the whole flow: start a task,
watch the agent implement it, review the diff and merge it. Nothing is sent
anywhere in demo mode. The header shows a DEMO label.

## How it talks to SuperPlane

All calls use `Authorization: Bearer <SUPERPLANE_TOKEN>` against
`https://app.superplane.com` (set `SUPERPLANE_URL` in `config.py` for a
self-hosted install). The endpoints come from SuperPlane's open-source API
definition (`superplanehq/superplane`, `protos/factories.proto`):

| Purpose | Request |
|---------|---------|
| Workspace and its lines | `GET /api/v1/factories` |
| Board | `GET /api/v1/factories/{id}/orders?states=STATE_DRAFT`, `...STATE_OPEN&line_id=`, `...STATE_CLOSED&line_id=` |
| Task details | `GET /api/v1/factories/{id}/orders/{order}` |
| Start | `PATCH /api/v1/factories/{id}/orders/{order}/dispatch` with `{"lineName": ...}` |
| Can it merge? | `GET /api/v1/factories/{id}/prs/{pr}/mergeability` |
| Merge | `POST /api/v1/factories/{id}/prs/{pr}/merge` with the allowed merge method and head SHA |
| Changed files | GitHub `GET /repos/{owner}/{repo}/pulls/{n}/files` |

Lane placement follows the SuperPlane web board: drafts are Backlog, open tasks
sit on the line step of their latest run, a task whose last step passed and is
waiting goes to Verify, and closed tasks are Done (archived ones are hidden).
Merging through SuperPlane closes the task, so it moves to Done.

The board refreshes every 20 seconds (three requests), and an open task every
8 seconds while its agent works. The screen only redraws when something
changes, which keeps the vector text (Mona Sans) fast.

## Files

| File | Purpose |
|------|---------|
| `__init__.py` | App setup, screens, refresh timers, toasts, case lights |
| `board.py` | The lane board |
| `detail.py` | Task screen with the Start and Merge actions |
| `diff.py` | Changed-file viewer |
| `superplane.py` | SuperPlane and GitHub client, board placement rules |
| `demo.py` | Offline demo factory |
| `core.py` | Settings, Wi-Fi check, one-request-per-frame jobs |
| `theme.py` | Colours, Mona Sans text, vector glyphs |
| `compat.py` | Key mapping for the Pimoroni web simulator; does nothing on the badge |
| `config.py` | Non-secret defaults |

## Web simulator

Upload every file in this folder except `README.md` with **Upload file**, open
`__init__.py` and press **Run**. With no token it starts in demo mode. Keys:
arrows are UP/DOWN and A/C (LEFT/RIGHT), **Space** is SELECT, **Esc** is BACK,
**Up + Down** together is MENU. Live mode may not work in the browser: it can
only call SuperPlane if SuperPlane allows cross-site browser requests.

## Testing status

- `validate_app.py Team3/factory-remote`: OK, 0 warnings.
- Run end to end in Pimoroni's native Badgeware simulator through a Universe
  2026 API shim:
  - demo mode: board, opening tasks, hold to start, the move to Implement,
    the automatic move to Verify, waiting for checks, the changed-files list,
    the diff viewer, hold to merge, the move to Done;
  - live mode against mocked SuperPlane responses shaped like the real API:
    lane placement (running, failed, verify, done, archived hidden),
    the exact Start and Merge requests, the GitHub files request, a rejected
    token and missing Wi-Fi.

Still to check on a physical badge with a real SuperPlane workspace: real
responses and timing, response sizes in memory, vector text speed on the
RP2350, and the case lights.
