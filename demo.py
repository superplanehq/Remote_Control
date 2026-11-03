# Demo factory: the same board, offline. Used when no SUPERPLANE_TOKEN is set
# (and in the browser simulator), so the flow can be rehearsed anywhere:
# Start a task, watch the agent implement it, review the changes, merge.
# Nothing here talks to SuperPlane or GitHub.
import time

from theme import Clock

DAY = 86400
IMPLEMENT_MS = 14000
CHECKS_MS = 6000

BACKLOG = (
    ("Navbar update", 5),
    ('Remove the "Learning Paths" section from the home page', 2),
    ('Remove "Meet the Community" button from the hero', 3),
    ("Change the home page of the community page", 1),
    ("Change the header of the page", 1),
    ("Change the website footer", 1),
    ("Add the workflow page in the current website", 3),
)

NAVBAR_FILES = (
    ("src/components/Navbar.tsx", "modified", (
        "@@ -1,18 +1,26 @@",
        " import { Link } from \"react-router-dom\";",
        "-import logo from \"../assets/logo.svg\";",
        "+import logo from \"../assets/sup-logo.svg\";",
        "+import { useState } from \"react\";",
        " ",
        " export function Navbar() {",
        "+  const [open, setOpen] = useState(false);",
        "   return (",
        "-    <nav className=\"navbar\">",
        "+    <nav className=\"navbar\" aria-label=\"Main\">",
        "       <img src={logo} alt=\"Sup Community\" />",
        "-      <ul>",
        "+      <button className=\"navbar-toggle\" onClick={() => setOpen(!open)}>",
        "+        Menu",
        "+      </button>",
        "+      <ul className={open ? \"open\" : \"\"}>",
        "         <li><Link to=\"/\">Home</Link></li>",
        "-        <li><Link to=\"/learn\">Learning Paths</Link></li>",
        "+        <li><Link to=\"/playground\">Playground</Link></li>",
        "+        <li><Link to=\"/workflows\">Workflows</Link></li>",
        "         <li><Link to=\"/community\">Community</Link></li>",
        "       </ul>",
        "     </nav>",
    )),
    ("src/styles/navbar.css", "modified", (
        "@@ -4,9 +4,18 @@",
        " .navbar {",
        "   display: flex;",
        "-  padding: 12px 24px;",
        "+  padding: 12px 32px;",
        "+  position: sticky;",
        "+  top: 0;",
        " }",
        "+",
        "+.navbar-toggle { display: none; }",
        "+",
        "+@media (max-width: 720px) {",
        "+  .navbar-toggle { display: block; }",
        "+  .navbar ul { display: none; }",
        "+  .navbar ul.open { display: flex; }",
        "+}",
    )),
    ("src/components/__tests__/Navbar.test.tsx", "added", (
        "@@ -0,0 +1,14 @@",
        "+import { render, screen } from \"@testing-library/react\";",
        "+import { Navbar } from \"../Navbar\";",
        "+",
        "+test(\"links to the playground\", () => {",
        "+  render(<Navbar />);",
        "+  expect(screen.getByText(\"Playground\")).toBeTruthy();",
        "+});",
        "+",
        "+test(\"opens the menu on small screens\", () => {",
        "+  render(<Navbar />);",
        "+  screen.getByText(\"Menu\").click();",
        "+  expect(screen.getByRole(\"list\").className).toBe(\"open\");",
        "+});",
    )),
)


def _generic_files(title):
    slug = "".join(ch.lower() if ch.isalpha() else "-" for ch in title).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    page = "src/pages/Home.tsx"
    return (
        (page, "modified", (
            "@@ -12,14 +12,11 @@ export function Home() {",
            "   return (",
            "     <main>",
            "       <Hero />",
            "-      <LearningPaths />",
            "-      <MeetTheCommunity />",
            "+      <Highlights />",
            "       <Footer />",
            "     </main>",
            "   );",
        )),
        ("docs/changes/%s.md" % slug[:40], "added", (
            "@@ -0,0 +1,4 @@",
            "+# %s" % title,
            "+",
            "+Implemented by the SuperPlane Implement agent.",
            "+Verified with the existing test suite.",
        )),
    )


class Demo:
    demo = True

    def __init__(self):
        if Clock.now() is None:
            Clock.epoch = time.mktime((2026, 11, 3, 18, 0, 0, 0, 0))
            Clock.at_ticks = badge.ticks
        now = Clock.now()
        self.factory = {"id": "demo", "key": "SC", "name": "Sup Community"}
        self.line = {
            "id": "line-1",
            "name": "Default",
            "stages": [{"index": 0, "app": "implement", "name": "Implement"}],
            "colors": {},
        }
        self.tasks = []
        for i, (title, score) in enumerate(BACKLOG):
            self.tasks.append({
                "id": "t%d" % (i + 1),
                "key": "SC-%d" % (i + 2),
                "title": title,
                "phase": "draft",
                "confidence": score,
                "created": now - 61 * DAY + i * 3600,
                "updated": now - 61 * DAY + i * 3600,
                "since": 0,
                "pr": None,
            })
        self.tasks.append({
            "id": "t0",
            "key": "SC-1",
            "title": "Create the Playground page Hero section",
            "phase": "done",
            "confidence": 5,
            "created": now - 20 * DAY,
            "updated": now - 7 * DAY,
            "since": 0,
            "pr": self._pr(21, "Create the Playground page Hero section", merged=True),
            "assignee": "Bhawna",
        })
        self.next_pr = 22

    def connect(self):
        return self.factory

    @staticmethod
    def _pr(number, title, merged=False):
        return {
            "id": "pr-%d" % number,
            "number": number,
            "title": title,
            "state": "STATE_MERGED" if merged else "STATE_OPEN",
            "url": "https://github.com/pixawna/sup_community/pull/%d" % number,
            "repo": "pixawna/sup_community",
            "github": True,
            "sha": "demo%d" % number,
        }

    def _advance(self):
        now = badge.ticks
        for task in self.tasks:
            if task["phase"] == "implement" and now - task["since"] >= IMPLEMENT_MS:
                task["phase"] = "verify"
                task["since"] = now
                task["pr"] = self._pr(self.next_pr, task["title"])
                self.next_pr += 1
                task["updated"] = Clock.now()

    def _card(self, task):
        phase = task["phase"]
        column = {"draft": "backlog", "implement": "phase-0", "verify": "verify", "done": "done"}[phase]
        status = {"draft": "draft", "implement": "running", "verify": "waiting", "done": "completed"}[phase]
        started = None
        if phase in ("implement", "verify"):
            started = Clock.now() - (badge.ticks - task["since"]) // 1000
        return {
            "id": task["id"],
            "key": task["key"],
            "title": task["title"],
            "column": column,
            "status": status,
            "step": 0 if phase == "implement" else None,
            "created": task["created"],
            "updated": task["updated"],
            "started": started,
            "confidence": task["confidence"],
            "origin": "https://github.com/pixawna/sup_community/issues/%s" % task["key"][3:],
            "origin_label": "Issue #%s" % task["key"][3:],
            "assignee": task.get("assignee", ""),
            "pr": task["pr"],
        }

    def _task(self, task_id):
        for task in self.tasks:
            if task["id"] == task_id:
                return task
        raise KeyError(task_id)

    def board(self):
        self._advance()
        cards = {"backlog": [], "phase-0": [], "verify": [], "done": []}
        for task in self.tasks:
            card = self._card(task)
            cards[card["column"]].append(card)
        for key in ("phase-0", "verify", "done"):
            cards[key].sort(key=lambda c: -(c["updated"] or 0))
        return cards

    def detail(self, task_id):
        self._advance()
        task = self._task(task_id)
        info = self._card(task)
        phase = task["phase"]
        elapsed = (badge.ticks - task["since"]) // 1000 if task["since"] else 0
        steps = []
        notes = []
        activity = []
        if phase == "implement":
            steps = [{"name": "Implement", "mark": "running", "seconds": elapsed, "started": None}]
            notes = ["Implement agent is writing the change"]
        elif phase in ("verify", "done"):
            steps = [{"name": "Implement", "mark": "passed", "seconds": IMPLEMENT_MS // 1000, "started": None}]
            activity = [{"title": "Implement", "body": "Made the change for \"%s\", added tests and "
                         "opened a pull request." % task["title"]}]
        if phase == "verify":
            if badge.ticks - task["since"] < CHECKS_MS:
                notes = ["Waiting for status checks"]
            else:
                notes = ["Ready to merge: checks passed"]
        info.update({
            "description": "Imported from GitHub (%s): %s." % (info["origin_label"].lower(), task["title"]),
            "checks": [{"name": "Confidence score", "score": task["confidence"], "max": 5,
                        "format": "FORMAT_FRACTION", "level": "", "summary":
                        "How likely an agent finishes this task in one run."}],
            "steps": steps,
            "notes": notes,
            "activity": activity,
            "cost_cents": 0 if phase == "draft" else 38,
            "seconds": 0 if phase == "draft" else (IMPLEMENT_MS // 1000),
        })
        return info

    def mergeability(self, pr):
        for task in self.tasks:
            if task["pr"] is pr or (task["pr"] and task["pr"]["id"] == pr["id"]):
                if task["phase"] == "done":
                    return {"can_merge": False, "reason": "", "message": "Already merged",
                            "methods": [], "sha": ""}
                if badge.ticks - task["since"] < CHECKS_MS:
                    return {"can_merge": False, "reason": "BLOCKED_REASON_CHECKS_UNFINISHED",
                            "message": "Status checks are still running.", "methods": [], "sha": ""}
                return {"can_merge": True, "reason": "", "message": "", "sha": pr["sha"],
                        "methods": ["MERGE_METHOD_SQUASH"]}
        return {"can_merge": False, "reason": "BLOCKED_REASON_UNAVAILABLE", "message": "Unknown PR",
                "methods": [], "sha": ""}

    def files(self, pr):
        title = pr.get("title") or ""
        source = NAVBAR_FILES if title.lower().startswith("navbar") else _generic_files(title)
        files = []
        for name, status, lines in source:
            add = 0
            delete = 0
            for row in lines:
                if row.startswith("+"):
                    add += 1
                elif row.startswith("-"):
                    delete += 1
            files.append({"name": name, "status": status, "add": add, "del": delete, "lines": list(lines)})
        return files

    def start(self, order):
        task = self._task(order["id"])
        if task["phase"] != "draft":
            return
        task["phase"] = "implement"
        task["since"] = badge.ticks
        task["updated"] = Clock.now()

    def merge(self, pr, mergeability):
        for task in self.tasks:
            if task["pr"] and task["pr"]["id"] == pr["id"]:
                task["phase"] = "done"
                task["pr"]["state"] = "STATE_MERGED"
                task["updated"] = Clock.now()
