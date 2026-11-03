# SuperPlane factory client: the same board the SuperPlane app shows
# (Backlog, one column per line step, Verify, Done) plus the two actions that
# move work forward: Start (dispatch a task to the line) and Merge.
#
# Endpoints (superplanehq/superplane protos/factories.proto):
#   GET   /api/v1/factories
#   GET   /api/v1/factories/{factory}/orders?states=...&line_id=...&limit=...
#   GET   /api/v1/factories/{factory}/orders/{order}
#   PATCH /api/v1/factories/{factory}/orders/{order}/dispatch   {"lineName": ...}
#   GET   /api/v1/factories/{factory}/prs/{pr}/mergeability
#   POST  /api/v1/factories/{factory}/prs/{pr}/merge  {"mergeMethod", "expectedHeadSha"}
# Changed files come from GitHub: GET /repos/{owner}/{repo}/pulls/{n}/files
#
# Auth: a SuperPlane API token (Profile > API token, or a service account)
# sent as "Authorization: Bearer <token>". The token stays on the badge in
# secrets.py and is never shown on screen.
import gc
import json

import requests

from theme import Clock, clean, parse_iso

AGENT = "FactoryRemote-Badge"
ACTIVE_EXECUTION = ("STATE_PENDING", "STATE_STARTED", "STATE_CANCELLING")


class ApiError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


def _header(headers, name):
    if not headers:
        return None
    name = name.lower()
    for key in headers:
        if key.lower() == name:
            return headers[key]
    return None


def _friendly(status, data, service):
    message = ""
    if isinstance(data, dict):
        message = data.get("message") or data.get("error") or ""
    if status == 401:
        if service == "GitHub":
            return "GitHub rejected GITHUB_TOKEN in secrets.py."
        return "SuperPlane rejected the API token. Make a new one under Profile > API token."
    if status == 403:
        return message or "This token isn't allowed to do that."
    if status == 404:
        return message or "Not found."
    return clean(message) or "%s returned HTTP %d" % (service, status)


def _int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _http(method, url, headers, body=None, service="SuperPlane"):
    gc.collect()
    response = requests.request(method, url, json=body, headers=headers)
    try:
        status = response.status_code
        date = _header(getattr(response, "headers", None), "date")
        if date and service == "SuperPlane":
            Clock.sync(date)
        raw = response.content
    finally:
        response.close()
    data = None
    if raw:
        try:
            data = json.loads(raw)
        except ValueError:
            data = None
    del raw
    gc.collect()
    if status >= 400:
        raise ApiError(status, _friendly(status, data, service))
    return data if data is not None else {}


# ---------------------------------------------------------------- board model
def is_done_step(name, app_id):
    if (name or "").strip().lower() == "done":
        return True
    app_id = app_id or ""
    return "pr-closure" in app_id or app_id == "app-refund-done"


def compact_line(line, step_names=None):
    """A factory line as board columns."""
    steps = []
    for index, step in enumerate(line.get("steps") or []):
        app = ((step.get("app") or {}).get("app") or "").strip()
        name = (step_names or {}).get(index) or ""
        steps.append({"index": index, "app": app, "name": clean(name)})
    stages = [s for s in steps if not is_done_step(s["name"], s["app"])]
    if not stages and steps:
        stages = steps
    for position, stage in enumerate(stages):
        if not stage["name"]:
            stage["name"] = "Implement" if len(stages) == 1 else "Step %d" % (position + 1)
    return {
        "id": line.get("id", ""),
        "name": clean(line.get("name") or ""),
        "stages": stages,
        "colors": line.get("columnColors") or {},
    }


def columns_for(line):
    cols = [{"key": "backlog", "title": "Backlog", "kind": "backlog"}]
    for stage in line["stages"]:
        cols.append({"key": "phase-%d" % stage["index"], "title": stage["name"], "kind": "phase",
                     "step": stage["index"]})
    cols.append({"key": "verify", "title": "Verify", "kind": "verify"})
    cols.append({"key": "done", "title": "Done", "kind": "done"})
    return cols


def _latest(items, field="createdAt"):
    best = None
    best_key = ""
    for item in items:
        key = item.get(field) or ""
        if best is None or key >= best_key:
            best = item
            best_key = key
    return best


def _confidence(order):
    for check in order.get("checkScores") or order.get("checks") or []:
        if check.get("key") == "confidence" or check.get("name") == "Confidence score":
            score = _float(check.get("score"))
            if score is None:
                return None
            score = int(score + 0.5)
            return 0 if score < 0 else 5 if score > 5 else score
    return None


def _main_pr(order):
    prs = order.get("pullRequests") or []
    if not prs:
        return None
    pr = _latest(prs, "updatedAt")
    url = pr.get("url") or ""
    repo = pr.get("repository") or ""
    if not repo and "github.com/" in url:
        parts = url.split("github.com/", 1)[1].split("/")
        if len(parts) >= 2:
            repo = parts[0] + "/" + parts[1]
    return {
        "id": pr.get("id", ""),
        "number": _int(pr.get("number")),
        "title": clean(pr.get("title") or ""),
        "state": pr.get("state") or "",
        "url": url,
        "repo": repo,
        "github": pr.get("provider") in ("PROVIDER_GITHUB", None, ""),
        "sha": (pr.get("currentRevision") or {}).get("sha") or "",
    }


def place(order, line):
    """Column key and status for one work order, following the web board."""
    state = order.get("state")
    result = order.get("result") or ""
    if state == "STATE_DRAFT":
        return "backlog", "draft", None
    if state == "STATE_CLOSED":
        if result == "RESULT_ARCHIVED":
            return None, "archived", None
        status = {
            "RESULT_PR_CLOSED": "closed",
            "RESULT_REJECTED": "rejected",
            "RESULT_FAILED": "failed",
        }.get(result, "completed")
        return "done", status, None

    dispatches = order.get("lineDispatches") or []
    mine = [d for d in dispatches if (d.get("line") or {}).get("id") == line["id"]]
    dispatch = _latest(mine or dispatches)
    stage_indexes = [s["index"] for s in line["stages"]]
    first = stage_indexes[0] if stage_indexes else 0
    if dispatch is None:
        return "phase-%d" % first, "waiting", first

    queue = dispatch.get("queueItem")
    if queue:
        index = _int(queue.get("stepIndex"))
        return "phase-%d" % index, "queued", index

    executions = dispatch.get("stepExecutions") or []
    active = [e for e in executions if e.get("state") in ACTIVE_EXECUTION]
    if active:
        execution = _latest(active)
        index = _int(execution.get("stepIndex"))
        if index not in stage_indexes:
            return "done", "running", index
        return "phase-%d" % index, "running", index

    execution = _latest(executions)
    if execution is None:
        return "phase-%d" % first, "running" if dispatch.get("state") == "STATE_ACTIVE" else "waiting", first
    index = _int(execution.get("stepIndex"))
    if index not in stage_indexes:
        return "done", "waiting", index
    passed = execution.get("result") == "RESULT_PASSED"
    if passed and stage_indexes and index == stage_indexes[-1] and dispatch.get("state") != "STATE_ACTIVE":
        return "verify", "waiting", index
    if execution.get("result") == "RESULT_FAILED":
        return "phase-%d" % index, "failed", index
    return "phase-%d" % index, "waiting", index


def compact_order(order, line):
    column, status, step = place(order, line)
    if column is None:
        return None
    origin = order.get("origin") or {}
    assignees = order.get("assignees") or []
    started = None
    dispatch = _latest(order.get("lineDispatches") or [])
    if dispatch:
        started = parse_iso(dispatch.get("createdAt"))
    return {
        "id": order.get("id", ""),
        "key": order.get("key") or ("#%s" % order.get("number", "")),
        "title": clean(order.get("title") or "Untitled task"),
        "column": column,
        "status": status,
        "step": step,
        "created": parse_iso(order.get("createdAt")),
        "updated": parse_iso(order.get("updatedAt")),
        "started": started,
        "confidence": _confidence(order),
        "origin": origin.get("url") or "",
        "origin_label": clean(origin.get("label") or ""),
        "assignee": clean((assignees[0] or {}).get("name") or "") if assignees else "",
        "pr": _main_pr(order),
    }


def step_names_from(orders, line_id):
    """Step names live on dispatch snapshots, not on the line itself."""
    names = {}
    for order in orders:
        for dispatch in order.get("lineDispatches") or []:
            if (dispatch.get("line") or {}).get("id") != line_id:
                continue
            for step in dispatch.get("steps") or []:
                index = _int(step.get("stepIndex"))
                if step.get("name") and index not in names:
                    names[index] = step["name"]
    return names


def compact_detail(order, line):
    summary = compact_order(order, line) or {}
    checks = []
    for check in order.get("checks") or []:
        score = _float(check.get("score"))
        top = _float(check.get("maxScore"))
        checks.append({
            "name": clean(check.get("name") or check.get("key") or "Check"),
            "score": score,
            "max": top,
            "format": check.get("format") or "",
            "level": check.get("level") or "",
            "summary": clean(check.get("summary") or ""),
        })
    steps = []
    dispatch = _latest(order.get("lineDispatches") or [])
    if dispatch:
        names = {}
        for step in dispatch.get("steps") or []:
            names[_int(step.get("stepIndex"))] = clean(step.get("name") or "")
        latest_by_step = {}
        for execution in dispatch.get("stepExecutions") or []:
            index = _int(execution.get("stepIndex"))
            current = latest_by_step.get(index)
            if current is None or (execution.get("createdAt") or "") >= (current.get("createdAt") or ""):
                latest_by_step[index] = execution
        for index in sorted(names):
            execution = latest_by_step.get(index) or {}
            state = execution.get("state") or ""
            result = execution.get("result") or ""
            if state in ACTIVE_EXECUTION:
                mark = "running"
            elif result == "RESULT_PASSED":
                mark = "passed"
            elif result == "RESULT_FAILED":
                mark = "failed"
            elif result == "RESULT_CANCELLED":
                mark = "cancelled"
            else:
                mark = "pending"
            steps.append({
                "name": names[index] or "Step %d" % (index + 1),
                "mark": mark,
                "seconds": _int(execution.get("durationSeconds"), None) if execution else None,
                "started": parse_iso(execution.get("createdAt")) if execution else None,
            })
    notes = []
    for note in order.get("statusNotes") or []:
        headline = clean(note.get("headline") or "")
        if headline:
            notes.append(headline)
    activity = []
    for pr in order.get("pullRequests") or []:
        for item in (pr.get("activities") or []) + (pr.get("runs") or []):
            title = clean(item.get("title") or "")
            body = clean(item.get("description") or "")
            if title or body:
                activity.append({"title": title, "body": body})
    summary.update({
        "description": clean(order.get("description") or ""),
        "checks": checks,
        "steps": steps,
        "notes": notes,
        "activity": activity[:6],
        "cost_cents": _int(order.get("totalCostCents")),
        "seconds": _int(order.get("totalDurationSeconds")),
    })
    return summary


def compact_files(items):
    files = []
    for item in items or []:
        patch = item.get("patch") or ""
        lines = []
        for row in patch.split("\n")[:400]:
            lines.append(row[:160])
        files.append({
            "name": item.get("filename") or "?",
            "status": item.get("status") or "modified",
            "add": _int(item.get("additions")),
            "del": _int(item.get("deletions")),
            "lines": lines,
        })
    return files


# ---------------------------------------------------------------- live client
class SuperPlane:
    demo = False

    def __init__(self, base_url, token, workspace="", line_name="", github_token=""):
        self.base = (base_url or "https://app.superplane.com").rstrip("/")
        self.token = token
        self.workspace = (workspace or "").strip()
        self.line_name = (line_name or "").strip()
        self.github_token = github_token
        self.factory = None
        self.line = None

    def _api(self, method, path, body=None):
        headers = {
            "Authorization": "Bearer " + self.token,
            "Accept": "application/json",
            "User-Agent": AGENT,
        }
        if body is not None:
            headers["Content-Type"] = "application/json"
        return _http(method, self.base + path, headers, body)

    def _fid(self):
        return self.factory["id"]

    # ------------------------------------------------------------ reads
    def connect(self):
        data = self._api("GET", "/api/v1/factories")
        factories = data.get("factories") or []
        if not factories:
            raise ApiError(404, "No SuperPlane workspaces found for this token.")
        wanted = self.workspace.lower()
        chosen = factories[0]
        if wanted:
            chosen = None
            for f in factories:
                if wanted in ((f.get("key") or "").lower(), (f.get("name") or "").lower(),
                              f.get("id") or "", (f.get("urlId") or "").lower()):
                    chosen = f
                    break
            if chosen is None:
                raise ApiError(404, "No workspace called %s. Check SUPERPLANE_WORKSPACE." % self.workspace)
        lines = chosen.get("lines") or []
        if not lines:
            raise ApiError(404, "This workspace has no factory line yet.")
        line = lines[0]
        if self.line_name:
            for candidate in lines:
                if (candidate.get("name") or "").lower() == self.line_name.lower():
                    line = candidate
                    break
        self.factory = {
            "id": chosen.get("id", ""),
            "key": clean(chosen.get("key") or ""),
            "name": clean(chosen.get("name") or "Factory"),
        }
        self._raw_line = line
        self.line = compact_line(line)
        del data
        gc.collect()
        return self.factory

    def board(self):
        """Every card on the board, grouped by column key."""
        line_id = self.line["id"]
        base = "/api/v1/factories/%s/orders?" % self._fid()
        raw = []
        for query in ("states=STATE_DRAFT&limit=25",
                      "states=STATE_OPEN&limit=25&line_id=" + line_id,
                      "states=STATE_CLOSED&limit=12&line_id=" + line_id):
            data = self._api("GET", base + query)
            raw.extend(data.get("orders") or [])
            del data
            gc.collect()
        names = step_names_from(raw, line_id)
        if names:
            self.line = compact_line(self._raw_line, names)
        cards = {}
        for col in columns_for(self.line):
            cards[col["key"]] = []
        seen = {}
        for order in raw:
            item = compact_order(order, self.line)
            if item is None or item["id"] in seen:
                continue
            seen[item["id"]] = True
            cards.setdefault(item["column"], []).append(item)
        del raw
        gc.collect()
        return cards

    def detail(self, order_id):
        data = self._api("GET", "/api/v1/factories/%s/orders/%s" % (self._fid(), order_id))
        result = compact_detail(data.get("order") or {}, self.line)
        del data
        gc.collect()
        return result

    def mergeability(self, pr):
        data = self._api("GET", "/api/v1/factories/%s/prs/%s/mergeability" % (self._fid(), pr["id"]))
        m = data.get("mergeability") or {}
        return {
            "can_merge": bool(m.get("canMerge")),
            "reason": m.get("blockedReason") or "",
            "message": clean(m.get("message") or ""),
            "methods": m.get("allowedMethods") or [],
            "sha": m.get("headSha") or "",
        }

    def files(self, pr):
        if not pr or not pr.get("repo") or not pr.get("number"):
            raise ApiError(404, "This pull request isn't on GitHub.")
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": AGENT,
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.github_token:
            headers["Authorization"] = "Bearer " + self.github_token
        data = _http(
            "GET",
            "https://api.github.com/repos/%s/pulls/%d/files?per_page=30" % (pr["repo"], pr["number"]),
            headers, service="GitHub",
        )
        files = compact_files(data if isinstance(data, list) else [])
        del data
        gc.collect()
        return files

    # ------------------------------------------------------------ actions
    def start(self, order):
        self._api("PATCH", "/api/v1/factories/%s/orders/%s/dispatch" % (self._fid(), order["id"]),
                  {"lineName": self._raw_line.get("name") or ""})

    def merge(self, pr, mergeability):
        methods = mergeability.get("methods") or []
        method = "MERGE_METHOD_SQUASH"
        if methods and method not in methods:
            method = methods[0]
        self._api("POST", "/api/v1/factories/%s/prs/%s/merge" % (self._fid(), pr["id"]),
                  {"mergeMethod": method, "expectedHeadSha": mergeability.get("sha") or ""})
