#!/usr/bin/env python3
"""CFA Level I autopilot: master plan -> weekly plans -> daily brief, via DeepSeek.

Commands:
  master [--force]  rebuild the roadmap with the model (the shipped plan is curated: this overwrites it)
  week [--next] [--force] [--offline]
                    build this week's (or next week's) detailed plan
  today [--notify]  today's tasks, target, progress and next deadline
  log "text" MIN    record what you studied   [--topic X] [--score 72] [--date YYYY-MM-DD] [--lesson LM56]
  lessons           per-module hour budget vs logged time   [--topic X] [--next N] [--remaining] [--write]
  due               spaced-repetition queue: what is due now   [--limit N] [--all] [--write]
  error "text"      add an error-log item   [--lesson LM56] [--topic X] [--why "cause"]
  errors            open error-log items   [--all] [--topic X]
  close ID [ID..]   mark error-log items as fixed
  mock [SCORE]      log a mock score, or list the mock history   [--note] [--date]
  analytics         readiness index, coverage and accuracy by topic, next best action
  pace              planned vs logged hours, required h/week, projected finish
  doctor            validate the plan, log and CSV files
  guide             open the HTML operating manual
  tracker           open the Excel tracker
  status            hours logged, streak, week progress, deadlines
  review            weekly reconciliation: planned vs logged
  nudge [--final]   evening check-in, graded against today's target

The 102 learning modules of the 2027 curriculum live in plan/lessons.json. Each
carries a learn / practice / review budget; the weekly planner names the modules
it expects that week, so a day is never just "study fixed income".

Design rule: the timers must never fail silently. Every model call has a
deterministic fallback built from plan/curriculum.json, and every notification
is also appended to ~/.local/state/cfa/inbox.log.
"""
import argparse
import csv
import datetime as dt
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
import webbrowser
from collections import defaultdict
from pathlib import Path

HOME = Path(os.environ.get("CFA_HOME", Path(__file__).resolve().parent))
PROFILE = HOME / "profile.json"
PROMPTS = HOME / "prompts"
PLAN = HOME / "plan"
WEEKS = PLAN / "weeks"
REVIEWS = PLAN / "reviews"
MASTER = PLAN / "master_plan.md"
CURRICULUM = PLAN / "curriculum.json"
LESSONS = PLAN / "lessons.json"
LOG = HOME / "progress.csv"
ERRORS = HOME / "errors.csv"
MOCKS = HOME / "mocks.csv"
ENV_FILE = Path.home() / ".config" / "cfa" / "env"
INBOX = Path.home() / ".local" / "state" / "cfa" / "inbox.log"
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
LOG_FIELDS = ["date", "minutes", "topic", "note", "score", "lesson"]
ERROR_FIELDS = ["id", "date", "topic", "lesson", "note", "why", "status", "closed"]
MOCK_FIELDS = ["date", "score", "note"]
SPACED_DAYS = [1, 3, 7, 21, 45]


def load_env():
    """Load ~/.config/cfa/env when run by hand (systemd already injects it)."""
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


load_env()
API_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/") + "/chat/completions"
# Official docs name the model "deepseek-flash"; "deepseek-v4-flash" is a legacy alias.
MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-flash")


# ---------- LLM ----------
def call_llm(system, user, json_mode=False, max_tokens=32000):
    key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not key or key.startswith("paste"):
        sys.exit(f"DEEPSEEK_API_KEY missing. Put it in {ENV_FILE}")
    while True:
        body = {
            "model": MODEL,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "max_tokens": max_tokens,
            "stream": False,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        req = urllib.request.Request(
            API_URL,
            json.dumps(body).encode(),
            {"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
        )
        try:
            with urllib.request.urlopen(req, timeout=900) as r:
                data = json.load(r)
            break
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="replace")
            if e.code == 400 and "max_tokens" in msg and max_tokens > 4000:
                max_tokens //= 2  # limit lower than assumed: retry smaller
                continue
            sys.exit(f"API error {e.code}: {msg}")
        except urllib.error.URLError as e:
            sys.exit(f"Network error: {e}")
    choice = data["choices"][0]
    if choice.get("finish_reason") == "length":
        print("WARNING: output was truncated (raise max_tokens or shorten the prompt)", file=sys.stderr)
    return choice["message"]["content"]


# ---------- helpers ----------
def profile():
    return json.loads(PROFILE.read_text())


def curriculum():
    return json.loads(CURRICULUM.read_text())["blocks"]


_LESSON_CACHE = None


def lessons_data():
    global _LESSON_CACHE
    if _LESSON_CACHE is None:
        _LESSON_CACHE = json.loads(LESSONS.read_text())
    return _LESSON_CACHE


def lessons():
    return lessons_data()["lessons"]


def lesson_index():
    return {l["id"]: l for l in lessons()}


def compact_ids(ids):
    """LM1 LM2 LM3 LM7 -> 'LM1-LM3, LM7'. Keeps weekly plans readable."""
    nums = sorted({int(i[2:]) for i in ids if i.startswith("LM") and i[2:].isdigit()})
    out, start, prev = [], None, None
    for n in nums:
        if start is None:
            start = prev = n
        elif n == prev + 1:
            prev = n
        else:
            out.append(f"LM{start}" if start == prev else f"LM{start}-LM{prev}")
            start = prev = n
    if start is not None:
        out.append(f"LM{start}" if start == prev else f"LM{start}-LM{prev}")
    return ", ".join(out)



def prompt(name):
    return (PROMPTS / name).read_text()


def monday(d):
    return d - dt.timedelta(days=d.weekday())


def read_log():
    """Rows for real sessions only. Skips malformed lines so a bad append never breaks the timers."""
    if not LOG.exists():
        return []
    rows = []
    with LOG.open(newline="") as f:
        for r in csv.DictReader(f):
            date = (r.get("date") or "").strip()
            try:
                dt.date.fromisoformat(date)
                minutes = int(float((r.get("minutes") or "0").strip() or 0))
            except (ValueError, TypeError):
                continue
            rows.append({"date": date, "minutes": minutes,
                         "topic": (r.get("topic") or "").strip(),
                         "note": r.get("note") or "",
                         "score": (r.get("score") or "").strip(),
                         "lesson": (r.get("lesson") or "").strip()})
    return rows


def ensure_log_header():
    """Older progress.csv files have 5 columns; add the lesson column once, in place."""
    if not LOG.exists():
        return
    with LOG.open(newline="") as f:
        rows = list(csv.reader(f))
    if not rows or rows[0] == LOG_FIELDS:
        return
    if rows[0][:5] == LOG_FIELDS[:5]:
        rows[0] = LOG_FIELDS
        with LOG.open("w", newline="") as f:
            csv.writer(f).writerows(rows)


def read_table(path, fields):
    if not path.exists():
        return []
    out = []
    try:
        with path.open(newline="", encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                out.append({k: (r.get(k) or "").strip() for k in fields})
    except OSError:
        return []
    return out


def write_table(path, fields, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})


def read_errors():
    return read_table(ERRORS, ERROR_FIELDS)


def read_mocks():
    return read_table(MOCKS, MOCK_FIELDS)


def open_errors():
    return [e for e in read_errors() if e["status"] != "closed"]


def session_stats(rows):
    """Per-module: number of sessions, last date, minutes logged."""
    stats = {}
    for r in rows:
        lid = r.get("lesson", "")
        if not lid:
            continue
        try:
            day = dt.date.fromisoformat(r["date"])
        except ValueError:
            continue
        s = stats.setdefault(lid, {"count": 0, "last": day, "minutes": 0})
        s["count"] += 1
        s["minutes"] += r["minutes"]
        if day > s["last"]:
            s["last"] = day
    return stats


def due_lessons(rows=None, today=None, include_done=False):
    """Spaced repetition queue, derived entirely from progress.csv.

    Session 1 -> review in 1 day, 2 -> 3 days, 3 -> 7, 4 -> 21, 5 -> 45.
    Logging a session is the review, so the interval grows with each touch.
    """
    rows = read_log() if rows is None else rows
    today = today or dt.date.today()
    idx = lesson_index()
    out = []
    for lid, s in session_stats(rows).items():
        lesson = idx.get(lid)
        if not lesson:
            continue
        done = s["minutes"] >= lesson["total"] * 60 * 0.95
        if done and not include_done:
            continue
        stage = min(max(s["count"] - 1, 0), len(SPACED_DAYS) - 1)
        due = s["last"] + dt.timedelta(days=SPACED_DAYS[stage])
        if due <= today:
            out.append({"lesson": lesson, "due": due, "overdue": (today - due).days,
                        "stage": stage + 1, "logged": s["minutes"], "done": done})
    out.sort(key=lambda x: x["due"])
    return out




def totals_by_topic(rows):
    t = defaultdict(int)
    for r in rows:
        t[r["topic"] or "unspecified"] += int(r["minutes"] or 0)
    return dict(t)


def minutes_on(day, rows=None, topic=None):
    rows = read_log() if rows is None else rows
    d = day.isoformat()
    return sum(r["minutes"] for r in rows
               if r["date"] == d and (topic is None or r["topic"] == topic))


def regime(day, p):
    for a, b in p.get("holiday_ranges", []):
        if dt.date.fromisoformat(a) <= day <= dt.date.fromisoformat(b):
            return "holiday"
    return "term"


def weekly_hours(day, p):
    b = block_for(day)
    if b.get("hours_per_week"):
        return b["hours_per_week"]
    return p.get("weekly_hours_holiday" if regime(day, p) == "holiday" else "weekly_hours_term", 30)


def block_for(day):
    blocks = curriculum()
    for b in blocks:
        if dt.date.fromisoformat(b["start"]) <= day <= dt.date.fromisoformat(b["end"]):
            return b
    return blocks[-1]


def block_weeks(b):
    s, e = dt.date.fromisoformat(b["start"]), dt.date.fromisoformat(b["end"])
    return max(((monday(e) - monday(s)).days // 7) + 1, 1)


def lessons_for_week(ws, b):
    """Contiguous slice of the block's modules for this week, weighted by their hour budget.

    Deterministic: same week -> same modules, whether or not the model is reachable.
    """
    idx = lesson_index()
    seq = [idx[i] for i in b.get("lessons", []) if i in idx]
    if not seq:
        return []
    nw = block_weeks(b)
    k = min(max(((ws - monday(dt.date.fromisoformat(b["start"]))).days // 7), 0), nw - 1)
    # Equal module counts per week, with the remainder spread by rounding. Every
    # module lands in exactly one week: no gaps, no week re-teaching the same module.
    n = len(seq)
    lo = round(n * k / nw)
    hi = max(round(n * (k + 1) / nw), lo + 1)
    return seq[lo:hi]


def next_checkpoints(p, today, n=3):
    out = []
    for c in p.get("checkpoints", []):
        days = (dt.date.fromisoformat(c["date"]) - today).days
        if days >= 0:
            out.append((days, c))
    out.sort(key=lambda x: x[0])
    return out[:n]



def upcoming_deadlines(p, today, n=3):
    out = []
    for d in p.get("deadlines", []):
        days = (dt.date.fromisoformat(d["date"]) - today).days
        if days >= 0:
            out.append((days, d))
    out.sort(key=lambda x: x[0])
    return out[:n]


def notify(title, body):
    """Three channels: desktop, file inbox, phone (optional). None may crash the timer."""
    stamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    try:
        INBOX.parent.mkdir(parents=True, exist_ok=True)
        with INBOX.open("a") as f:
            f.write(f"[{stamp}] {title}\n{body}\n\n")
    except OSError as e:
        print(f"inbox write failed: {e}", file=sys.stderr)
    try:
        subprocess.run(["notify-send", "-a", "CFA", "-u", "normal", title, body[:900]],
                       check=False, timeout=10)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    topic = os.environ.get("NTFY_TOPIC")
    if topic:  # optional phone push via https://ntfy.sh
        req = urllib.request.Request(
            f"https://ntfy.sh/{topic}", body.encode(),
            {"Title": title.encode("ascii", "ignore").decode() or "CFA"}
        )
        try:
            urllib.request.urlopen(req, timeout=15)
        except Exception as e:  # noqa: BLE001
            print(f"ntfy failed: {e}", file=sys.stderr)


# ---------- master ----------
def cmd_master(a):
    p, today = profile(), dt.date.today()
    days_left = (dt.date.fromisoformat(p["exam_date"]) - today).days
    user = (
        f"Today: {today.isoformat()}\nDays to target exam date: {days_left}\n\n"
        f"LEARNER PROFILE (JSON):\n{json.dumps(p, indent=2, ensure_ascii=False)}\n\n"
        f"STRUCTURED BLOCKS (JSON):\n{json.dumps(curriculum(), indent=2, ensure_ascii=False)}"
    )
    PLAN.mkdir(parents=True, exist_ok=True)
    if MASTER.exists():
        if not a.force and "CURATED" in MASTER.read_text()[:400]:
            sys.exit("master_plan.md is curated. Re-run with --force to replace it, or edit it by hand.")
        MASTER.rename(PLAN / f"master_plan.{today.isoformat()}.bak.md")
    MASTER.write_text(call_llm(prompt("master.md"), user))
    print(f"Master plan written to {MASTER}")


# ---------- week ----------
def render_week(w):
    lines = [f"# Week of {w['week_start']} - {w.get('phase', '')}", "", f"**Focus:** {w.get('focus', '')}",
             f"**Budget:** {w.get('hours_budget', '?')} h", ""]
    if w.get("lessons"):
        lines.insert(3, f"**Modules:** {compact_ids(w['lessons'])}")
    for d in DAYS:
        tasks = w["days"].get(d, [])
        total = sum(t.get("minutes", 0) for t in tasks)
        lines.append(f"## {d} ({total} min)")
        lines += [f"- [ ] {t['task']} ({t.get('minutes', 0)} min, {t.get('type', '')}) - {t.get('resource', '')}"
                  for t in tasks]
        lines.append("")
    if w.get("checkpoint"):
        lines.append(f"**Checkpoint:** {w['checkpoint']}")
    if w.get("notes"):
        lines.append(f"**Notes:** {w['notes']}")
    return "\n".join(lines)


def fallback_week(ws, p):
    """Deterministic week: never leave the learner without a plan.

    Seven-day arc (read / practise / read / practise / review / long block / review),
    with the English block every day. Minutes are allocated by day weight and the
    rounding remainder is pushed to Saturday, so the total always equals the budget.
    """
    b = block_for(ws)
    eng = int(p.get("english_minutes_per_day", 60))
    budget = int(weekly_hours(ws, p) * 60)
    cfa_min = max(budget - eng * 7, 300)
    weights = p.get("day_weights", {d: 1 for d in DAYS})
    total_w = sum(weights.get(d, 1) for d in DAYS)
    topic = b["topic"]
    mode = b["mode"]
    focus = b["focus"]
    week_lessons = lessons_for_week(ws, b)
    due = due_lessons()
    due_ids = compact_ids([d["lesson"]["id"] for d in due][:6])
    ids = compact_ids([l["id"] for l in week_lessons])
    label = ids or (focus.split(":")[0] if ":" in focus else topic)
    resource = week_lessons[0]["resource"] if week_lessons else "profile resources / official curriculum"
    short = label
    verb = "Learn" if mode == "read" else "Practice"

    arc = {
        "Mon": (f"{verb} {label}: read the module and take notes in your own words", "read", 0.55 if mode == "read" else 0.0),
        "Tue": (f"{label}: 25 questions on Monday's material, log every miss with a why-line", "practice", 0.0),
        "Wed": (f"{verb} {label}: second half, close the gaps found on Tuesday", "read", 0.55 if mode == "read" else 0.0),
        "Thu": (f"{label}: 25 new questions, then triage the error log", "practice", 0.0),
        "Fri": ("Spaced recall: flashcards (1/3/7 days) + formula sheet from memory", "review", 0.0),
        "Sat": (f"{label}: timed set under exam conditions, then full correction", "practice", 0.0),
        "Sun": ("Weekly review: redo the week's misses, then read next week's focus", "review", 0.0),
    }
    if mode == "practice":
        arc["Mon"] = (f"{label}: timed question set, then correct every miss", "practice", 0.0)
        arc["Wed"] = (f"{label}: 25 more questions, target Monday's errors", "practice", 0.0)
    elif mode == "setup":
        arc["Mon"] = (f"Set up: {focus}", "notes", 0.6)
        arc["Tue"] = ("Baseline diagnostic, 40 questions, timed - log % by topic", "mock", 0.0)
        arc["Wed"] = ("Build the formula sheet skeleton for all 10 topics", "notes", 0.6)
    elif mode == "mock":
        arc["Sat"] = (f"{label}: full mock, exam conditions, no pause", "mock", 0.0)
        arc["Thu"] = ("Mock preparation: formula sheet and calculator drills only", "review", 0.0)
    elif mode == "review" and not week_lessons:
        arc["Sat"] = (f"{label}: half-mock, then correct every question", "mock", 0.0)

    if due_ids:
        arc["Fri"] = (f"Spaced recall: due reviews {due_ids} (20 min each), then formula sheet from memory", "review", 0.0)
        arc["Sun"] = (f"Weekly review: clear due reviews {due_ids}, redo the week's misses, then 25 mixed questions", "review", 0.0)

    english_tpl = {
        "Mon": "English: 30 min reading (FT/WSJ) + 30 min reading aloud",
        "Tue": "English: 30 min reading + 30 min shadowing an earnings call",
        "Wed": "English: 30 min reading + 30 min explaining yesterday's topic aloud",
        "Thu": "English: 30 min reading + 30 min recorded 2-minute summary",
        "Fri": "English: 30 min reading + 30 min vocabulary review",
        "Sat": "English: 30 min reading + 30 min speaking practice",
        "Sun": "English: 30 min reading + 30 min free speaking",
    }

    mins = {d: max(int(cfa_min * weights.get(d, 1) / total_w / 5) * 5, 25) for d in DAYS}
    mins["Sat"] += cfa_min - sum(mins.values())

    days = {}
    for d in DAYS:
        text, typ, split = arc[d]
        tasks = [{"task": english_tpl[d], "resource": "financial press, own voice notes",
                  "minutes": eng, "type": "read"}]
        if split and mins[d] >= 90:  # two blocks inside the same theme
            a = max(int(mins[d] * split / 5) * 5, 20)
            tasks.append({"task": text, "resource": resource, "minutes": a, "type": typ})
            tasks.append({"task": "Practice the same material: 15 questions, immediate correction",
                          "resource": "question bank", "minutes": mins[d] - a, "type": "practice"})
        else:
            tasks.append({"task": text,
                          "resource": resource if typ in ("read", "notes", "review", "flashcards") else "question bank",
                          "minutes": mins[d], "type": typ})
        days[d] = tasks

    return {"week_start": ws.isoformat(), "phase": b["phase"],
            "focus": focus, "hours_budget": round(budget / 60, 1), "days": days,
            "checkpoint": b["deliverable"],
            "lessons": [l["id"] for l in week_lessons],
            "notes": f"Generated offline from curriculum.json (model unavailable). {short} - budget respected, no resource invented."}


def build_week(ws, force=False, offline=False):
    out = WEEKS / f"{ws.isoformat()}.json"
    if out.exists() and not force:
        return out
    if not MASTER.exists():
        sys.exit("No master plan yet. Run: cfa.py master")
    WEEKS.mkdir(parents=True, exist_ok=True)
    p, rows = profile(), read_log()
    prev = WEEKS / f"{(ws - dt.timedelta(days=7)).isoformat()}.json"
    cutoff = (dt.date.today() - dt.timedelta(days=14)).isoformat()
    recent = [r for r in rows if r["date"] >= cutoff]
    weeks_left = (dt.date.fromisoformat(p["exam_date"]) - ws).days // 7
    block = block_for(ws)
    week_lessons = lessons_for_week(ws, block)
    due = due_lessons(rows, ws)
    errors = open_errors()[:10]
    due_lines = "\n".join(
        f"- {d['lesson']['id']} | {d['lesson']['title']} | stage {d['stage']}, {d['overdue']}d late"
        for d in due
    ) or "(none)"
    error_lines = "\n".join(
        f"- {e['topic']} {e['lesson']} | {e['note']} | why: {e['why'] or 'not written'}"
        for e in errors
    ) or "(none)"
    lesson_progress = defaultdict(int)
    for r in rows:
        if r["lesson"]:
            lesson_progress[r["lesson"]] += r["minutes"]
    lesson_lines = "\n".join(
        f"- {l['id']} | {l['title']} | total {l['total']} h "
        f"(learn {l['learn']}, practice {l['practice']}, review {l['review']}) | "
        f"logged {lesson_progress[l['id']] / 60:.1f} h | {l['resource']}"
        for l in week_lessons
    ) or "(no modules: consolidation, mocks or maintenance week)"
    user = (
        f"today: {dt.date.today().isoformat()}\nweek_start: {ws.isoformat()}\nweeks to exam: {weeks_left}\n"
        f"regime: {regime(ws, p)}\nweekly budget: {weekly_hours(ws, p)} h (including 7 h English)\n"
        f"english_minutes_per_day: {p.get('english_minutes_per_day', 60)} (inside the budget)\n\n"
        f"MASTER PLAN:\n{MASTER.read_text()}\n\n"
        f"CURRENT BLOCK:\n{json.dumps(block, ensure_ascii=False)}\n\n"
        f"THIS WEEK'S MODULES (use these ids in every CFA task):\n{lesson_lines}\n\n"
        f"DUE FOR SPACED REVIEW (put these first, 15-25 min each):\n{due_lines}\n\n"
        f"OPEN ERRORS (fold the relevant ones into practice):\n{error_lines}\n\n"
        f"PROFILE:\n{json.dumps(p, ensure_ascii=False)}\n\n"
        f"PREVIOUS WEEK:\n{prev.read_text() if prev.exists() else '(none)'}\n\n"
        f"RECENT LOG (date,minutes,topic,note,score,lesson):\n"
        + "\n".join(",".join(str(r[k]) for k in LOG_FIELDS) for r in recent)
        + f"\n\nTOTALS (minutes by topic): {json.dumps(totals_by_topic(rows))}"
    )
    plan = None
    if not offline:
        try:
            raw = call_llm(prompt("weekly.md"), user, json_mode=True, max_tokens=16000)
            plan = json.loads(raw)
            if "days" not in plan or not isinstance(plan["days"], dict):
                raise ValueError("model JSON has no 'days' object")
        except (SystemExit, Exception) as e:  # noqa: BLE001 - any failure must fall back
            print(f"[fallback] weekly model unavailable: {e}", file=sys.stderr)
            plan = None
    if plan is None:
        plan = fallback_week(ws, p)
    plan["week_start"] = ws.isoformat()
    out.write_text(json.dumps(plan, indent=2, ensure_ascii=False))
    out.with_suffix(".md").write_text(render_week(plan))
    print(f"Week plan written to {out.with_suffix('.md')}")
    return out


def cmd_week(a):
    ws = monday(dt.date.today()) + (dt.timedelta(days=7) if a.next else dt.timedelta(0))
    out = build_week(ws, force=a.force, offline=a.offline)
    print(out)


# ---------- today ----------
def day_tasks(ws, day):
    f = WEEKS / f"{ws.isoformat()}.json"
    if not f.exists():
        build_week(ws)
    plan = json.loads(f.read_text())
    return plan, plan["days"].get(DAYS[day.weekday()], [])


def cmd_today(a):
    today = dt.date.today()
    p = profile()
    ws = monday(today)
    plan, tasks = day_tasks(ws, today)
    target = sum(t.get("minutes", 0) for t in tasks)
    rows = read_log()
    logged = minutes_on(today, rows)
    eng = minutes_on(today, rows, topic="english")
    left = (dt.date.fromisoformat(p["exam_date"]) - today).days
    ratio = 100 * logged / target if target else 0
    dl = upcoming_deadlines(p, today, 1)

    lines = [f"{today:%a %d %b %Y}  |  {plan.get('phase', '')}  |  {left} days to exam",
             f"Target {target} min  ·  logged {logged} min  ·  English {eng}/{p.get('english_minutes_per_day', 60)} min  ·  {ratio:.0f}%"]
    if dl:
        days, d = dl[0]
        flag = "  <<< ACTION" if days <= d.get("lead_days", 14) else ""
        lines.append(f"Next deadline: {d['label']} - {days} days ({d['date']}){flag}")
    cps = next_checkpoints(p, today, 1)
    if cps:
        days, c = cps[0]
        lines.append(f"Next check: {c['label']} - {days} days ({c['date']})")
    if plan.get("lessons"):
        lines.append(f"Modules this week: {compact_ids(plan['lessons'])}")
    due = due_lessons(rows, today)
    if due:
        lines.append(f"Due review: {compact_ids([d['lesson']['id'] for d in due])} ({len(due)})  - cfa due")
    errs = open_errors()
    if errs:
        lines.append(f"Open errors: {len(errs)}  - cfa errors")
    lines.append(f"Focus: {plan.get('focus', '')}")
    lines.append("")
    if tasks:
        lines += [f"[ ] {t['task']}  ({t.get('minutes', 0)} min)  - {t.get('resource', '')}" for t in tasks]
    else:
        lines.append("Rest day.")
    if plan.get("checkpoint"):
        lines.append(f"\nCheckpoint: {plan['checkpoint']}")
    body = "\n".join(lines)
    print(body)
    if a.notify:
        notify("CFA today", body)


# ---------- log / status / lessons / nudge / review ----------
def cmd_log(a):
    day = dt.date.fromisoformat(a.date) if a.date else dt.date.today()
    lesson = (a.lesson or "").strip().upper()
    topic = a.topic or ""
    if lesson:
        idx = lesson_index()
        if lesson not in idx:
            sys.exit(f"Unknown lesson {lesson}. Try: cfa.py lessons --next 5")
        topic = topic or idx[lesson]["topic"]
    ensure_log_header()
    new = not LOG.exists()
    with LOG.open("a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(LOG_FIELDS)
        w.writerow([day.isoformat(), a.minutes, topic, a.text, a.score or "", lesson])
    suffix = f" ({lesson})" if lesson else ""
    print(f"Logged {a.minutes} min on {day.isoformat()}{suffix}.")


def cmd_status(a):
    rows, p = read_log(), profile()
    today = dt.date.today()
    total = sum(r["minutes"] for r in rows)
    days = sorted({r["date"] for r in rows})
    streak, d = 0, today
    while d.isoformat() in days:
        streak, d = streak + 1, d - dt.timedelta(days=1)
    left = (dt.date.fromisoformat(p["exam_date"]) - today).days

    ws = monday(today)
    try:
        plan, _ = day_tasks(ws, today)
        week_target = sum(t.get("minutes", 0) for day in plan["days"].values() for t in day)
    except SystemExit:
        week_target = 0
    week_logged = sum(r["minutes"] for r in rows if r["date"] >= ws.isoformat())
    eng = sum(r["minutes"] for r in rows if r["topic"] == "english")
    ldata = lessons_data()
    per = defaultdict(int)
    for r in rows:
        if r["lesson"]:
            per[r["lesson"]] += r["minutes"]
    used = sum(per.values()) / 60
    done = sum(1 for l in ldata["lessons"] if per[l["id"]] >= l["total"] * 60 * 0.95)

    print(f"Total: {total / 60:.1f} h | English: {eng / 60:.1f} h | Streak: {streak} d | Days to exam: {left}")
    print(f"Modules: {used:.1f}/{ldata['totals']['total']:.0f} h logged | {done}/{len(ldata['lessons'])} done")
    due = due_lessons(rows, today)
    errs = open_errors()
    mocks = [float(m["score"]) for m in read_mocks() if m["score"]]
    mock_txt = f"{sum(mocks) / len(mocks):.1f}%" if mocks else "none yet"
    print(f"Due reviews: {len(due)}" + (f" ({compact_ids([d['lesson']['id'] for d in due])})" if due else "")
          + f" | Open errors: {len(errs)} | Mock average: {mock_txt}")
    if week_target:
        print(f"This week: {week_logged}/{week_target} min ({100 * week_logged / week_target:.0f}%) | "
              f"regime: {regime(today, p)} @ {weekly_hours(today, p)} h/week")
    for days_left, dl in upcoming_deadlines(p, today, 3):
        print(f"  {dl['date']}  {dl['label']}  ({days_left} d)")
    for days_left, c in next_checkpoints(p, today, 2):
        print(f"  {c['date']}  {c['label']}  ({days_left} d)")
    for k, v in sorted(totals_by_topic(rows).items(), key=lambda kv: -kv[1])[:8]:
        print(f"  {k:<28}{v / 60:6.1f} h")


def write_lessons_md(per):
    data = lessons_data()
    ls, tot = data["lessons"], data["totals"]
    lines = [
        "# CFA Level I - 102 learning modules: hour budget",
        "",
        "Generated from `plan/lessons.json` by `cfa.py lessons --write`.",
        "Hours are CFA-only and include two spaced revisions; English (1 h/day) sits on top.",
        "",
        f"**Total: {tot['total']:.0f} h** - learn {tot['learn']:.0f} h, practice {tot['practice']:.0f} h, "
        f"revision {tot['review']:.0f} h, {tot['hours_per_lesson']:.1f} h per module on average.",
        "",
        "## By topic",
        "",
        "| Topic | Exam weight | LMs | Learn | Practice | Revision | Total |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for v in data["by_topic"].values():
        lines.append(f"| {v['name']} | {v['exam_weight']} | {v['lessons']} | {v['learn']:.1f} | "
                     f"{v['practice']:.1f} | {v['review']:.1f} | {v['total']:.1f} |")
    lines += ["", "## Modules", "",
              "| LM | Lesson | Topic | Learn | Practice | Revision | Total | Logged | Resource |",
              "|---|---|---|---:|---:|---:|---:|---:|---|"]
    for l in ls:
        lines.append(f"| {l['id']} | {l['title']} | {l['topic_name']} | {l['learn']:.1f} | {l['practice']:.1f} | "
                     f"{l['review']:.1f} | {l['total']:.1f} | {per[l['id']] / 60:.1f} | {l['resource']} |")
    path = PLAN / "lessons.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def cmd_lessons(a):
    data, ls = lessons_data(), lessons()
    rows = read_log()
    per = defaultdict(int)
    for r in rows:
        if r["lesson"]:
            per[r["lesson"]] += r["minutes"]

    if a.write:
        print(f"Written {write_lessons_md(per)}")
        if not (a.topic or a.next or a.remaining):
            return

    sel = ls
    if a.topic:
        q = a.topic.lower()
        sel = [l for l in sel if q in l["topic"].lower() or q in l["title"].lower() or q == l["id"].lower()]
    if a.remaining:
        sel = [l for l in sel if per[l["id"]] < l["total"] * 60 * 0.99]
    if a.next:
        sel = [l for l in sel if per[l["id"]] < l["total"] * 60 * 0.95][:a.next]

    print(f"{'LM':<5} {'Hours':>6} {'Done':>7} {'%':>4}  Lesson")
    for l in sel:
        h, m = l["total"], per[l["id"]]
        pct = min(100, 100 * m / (h * 60)) if h else 0
        if pct >= 95:
            mark = "x"
        elif pct > 0:
            mark = ">"
        else:
            mark = " "
        print(f"{mark}{l['id']:<4} {h:>5.1f}h {m / 60:>6.1f}h {pct:>4.0f}%  {l['title'][:56]}")

    used = sum(per.values()) / 60
    done = sum(1 for l in ls if per[l["id"]] >= l["total"] * 60 * 0.95)
    print(f"\n{len(sel)} of {len(ls)} modules shown | {used:.1f}/{data['totals']['total']:.0f} h logged | "
          f"{done}/{len(ls)} done | {left_hours(data, per):.0f} h remaining")
    print("Log a session: cfa.py log \"LM56 20 questions\" 60 --lesson LM56 --score 70")


def left_hours(data, per):
    return sum(max(l["total"] - per[l["id"]] / 60, 0) for l in data["lessons"])


def bar(pct, width=20):
    pct = max(0.0, min(100.0, pct))
    n = int(round(pct / 100 * width))
    return "█" * n + "░" * (width - n)


def cmd_due(a):
    rows = read_log()
    due = due_lessons(rows, include_done=a.all)
    if not due:
        print("Nothing due. Next modules: cfa.py lessons --next 5")
        return
    print(f"SPACED REVIEW QUEUE - {len(due)} due")
    print(f"{'LM':<5}{'Stage':>6}{'Late':>6}{'Logged':>10}  Lesson")
    for d in due[:a.limit]:
        l = d["lesson"]
        print(f"{l['id']:<5}{d['stage']:>6}{str(d['overdue']) + 'd':>6}"
              f"{d['logged'] / 60:>8.1f}h  {l['title'][:52]}")
    print(f"\nReview = 15-25 min: 10 missed questions, flashcards, then explain the mechanism aloud.")
    print(f"Log it: cfa.py log \"{due[0]['lesson']['id']} review\" 20 --lesson {due[0]['lesson']['id']}")
    if a.write:
        lines = [f"# Review queue - {dt.date.today().isoformat()}", ""]
        lines += [f"- [ ] {d['lesson']['id']} {d['lesson']['title']} - stage {d['stage']}, {d['overdue']}d late"
                  for d in due]
        out = PLAN / "due.md"
        out.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"Written {out}")


def cmd_error(a):
    rows = read_errors()
    lesson = (a.lesson or "").strip().upper()
    topic = a.topic or ""
    if lesson:
        idx = lesson_index()
        if lesson not in idx:
            sys.exit(f"Unknown lesson {lesson}. Try: cfa.py lessons --next 5")
        topic = topic or idx[lesson]["topic"]
    nid = max([int(r["id"]) for r in rows if r["id"].isdigit()] or [0]) + 1
    day = a.date or dt.date.today().isoformat()
    rows.append({"id": str(nid), "date": day, "topic": topic, "lesson": lesson,
                 "note": a.text, "why": a.why or "", "status": "open", "closed": ""})
    write_table(ERRORS, ERROR_FIELDS, rows)
    print(f"Error #{nid} logged." + (f" ({lesson})" if lesson else ""))
    print("Close it when you can redo the question from scratch: cfa.py close %d" % nid)


def cmd_errors(a):
    rows = read_errors()
    sel = rows if a.all else [e for e in rows if e["status"] != "closed"]
    if a.topic:
        q = a.topic.lower()
        sel = [e for e in sel if q in e["topic"].lower() or q in e["lesson"].lower()]
    if not sel:
        print("No open errors. Keep it that way.")
        return
    today = dt.date.today()
    print(f"{'ID':>3} {'AGE':>4}  {'TOPIC':<24}{'LM':<6} NOTE / WHY")
    for e in sel:
        try:
            age = (today - dt.date.fromisoformat(e["date"])).days
        except ValueError:
            age = 0
        note = e["note"]
        if e["why"]:
            note += "  /  " + e["why"]
        print(f"{e['id']:>3} {str(age) + 'd':>4}  {e['topic'][:23]:<24}{e['lesson']:<6} {note[:70]}")
    opened = [e for e in rows if e["status"] != "closed"]
    oldest = 0
    for e in opened:
        try:
            oldest = max(oldest, (today - dt.date.fromisoformat(e["date"])).days)
        except ValueError:
            pass
    print(f"\n{len(sel)} shown | {len(opened)} open | oldest {oldest}d | cfa.py close ID")


def cmd_close(a):
    rows = read_errors()
    wanted = {str(i) for i in a.ids}
    now = dt.date.today().isoformat()
    hit = 0
    for r in rows:
        if r["id"] in wanted and r["status"] != "closed":
            r["status"] = "closed"
            r["closed"] = now
            hit += 1
    if not hit:
        sys.exit(f"No open error with id {', '.join(sorted(wanted))}")
    write_table(ERRORS, ERROR_FIELDS, rows)
    print(f"Closed {hit} error(s). Remaining open: {len(open_errors())}")


def cmd_mock(a):
    rows = read_mocks()
    if a.score is None:
        if not rows:
            print("No mocks logged. Add one: cfa.py mock 62 --note \"cold, no notes\"")
            return
        rows.sort(key=lambda r: r["date"])
        print(f"{'DATE':<12}{'SCORE':>7}  {'':<22} VS 70")
        scores = []
        for r in rows:
            try:
                s = float(r["score"])
            except ValueError:
                continue
            scores.append(s)
            diff = s - 70
            print(f"{r['date']:<12}{s:>6.1f}%  {bar(s, 22)} {diff:+.1f}")
        if scores:
            avg = sum(scores) / len(scores)
            print(f"\nAverage {avg:.1f}%  |  best {max(scores):.1f}%  |  last {scores[-1]:.1f}%"
                  f"  |  {len(scores)} mock(s)")
        p = profile()
        cps = [c for c in p.get("checkpoints", []) if "mock" in c["label"].lower()]
        nxt = None
        for c in cps:
            d = (dt.date.fromisoformat(c["date"]) - dt.date.today()).days
            if d >= 0:
                nxt = (d, c)
                break
        if nxt:
            print(f"Next scheduled: {nxt[1]['label']} in {nxt[0]} d (target {nxt[1].get('target', 70)}%)")
        return
    score = float(a.score)
    if not 0 <= score <= 100:
        sys.exit("Score must be 0-100.")
    rows.append({"date": a.date or dt.date.today().isoformat(), "score": f"{score:.1f}", "note": a.note or ""})
    write_table(MOCKS, MOCK_FIELDS, rows)
    scores = [float(r["score"]) for r in rows if r["score"]]
    print(f"Mock logged: {score:.1f}%  |  average {sum(scores) / len(scores):.1f}% over {len(scores)}")


def readiness(rows):
    data = lessons_data()
    by_topic = data["by_topic"]
    idx = lesson_index()
    minutes = defaultdict(int)
    scores = []
    for r in rows:
        lid = r["lesson"]
        lesson = idx.get(lid)
        topic = r["topic"] or (lesson["topic"] if lesson else "")
        if topic:
            minutes[topic] += r["minutes"]
        if r["score"]:
            try:
                scores.append(float(r["score"]))
            except ValueError:
                pass
    covered = 0.0
    budget = 0.0
    for key, v in by_topic.items():
        hours = v["total"] * 60
        covered += min(minutes[key], hours)
        budget += hours
    coverage = 100 * covered / budget if budget else 0
    accuracy = sum(scores) / len(scores) if scores else None
    mocks = [float(m["score"]) for m in read_mocks() if m["score"]]
    mock_avg = sum(mocks) / len(mocks) if mocks else None
    parts = [(coverage, 0.40)]
    if accuracy is not None:
        parts.append((accuracy, 0.35))
    if mock_avg is not None:
        parts.append((mock_avg, 0.25))
    index = sum(v * w for v, w in parts) / sum(w for _, w in parts)
    return {"coverage": coverage, "accuracy": accuracy, "mock": mock_avg,
            "index": index, "minutes": minutes}


def cmd_analytics(a):
    rows = read_log()
    r = readiness(rows)
    print(f"READINESS {r['index']:.0f}/100  {bar(r['index'], 24)}")
    acc = f"{r['accuracy']:.1f}%" if r["accuracy"] is not None else "no scores yet"
    mck = f"{r['mock']:.1f}%" if r["mock"] is not None else "no mocks yet"
    print(f"Coverage {r['coverage']:.0f}%  ·  Accuracy {acc}  ·  Mocks {mck}")

    data = lessons_data()
    idx = lesson_index()
    scores_by_topic = defaultdict(list)
    for row in rows:
        if not row["score"]:
            continue
        lesson = idx.get(row["lesson"])
        topic = row["topic"] or (lesson["topic"] if lesson else "")
        if not topic:
            continue
        try:
            scores_by_topic[topic].append(float(row["score"]))
        except ValueError:
            pass

    print(f"\n{'TOPIC':<38}{'HOURS':>12}  {'COVER':<16}{'ACC':>6}  N")
    for key, v in sorted(data["by_topic"].items(), key=lambda kv: -kv[1]["total"]):
        hours = r["minutes"][key] / 60
        pct = 100 * min(r["minutes"][key], v["total"] * 60) / (v["total"] * 60)
        sc = scores_by_topic.get(key, [])
        acc = f"{sum(sc) / len(sc):.0f}%" if sc else "-"
        print(f"{v['name'][:37]:<38}{hours:>6.1f}/{v['total']:<5.1f}  {bar(pct, 14)} {pct:>3.0f}%  {acc:>5} {len(sc):>3}")

    open_n = len(open_errors())
    due_n = len(due_lessons(rows))
    weak = sorted(((sum(s) / len(s), k) for k, s in scores_by_topic.items() if s), key=lambda x: x[0])
    actions = []
    if due_n:
        actions.append(f"Clear the spaced-review queue: {due_n} module(s) due  (cfa.py due)")
    if open_n:
        actions.append(f"Close error-log items: {open_n} open  (cfa.py errors)")
    if weak:
        names = {k: v["name"] for k, v in data["by_topic"].items()}
        label = names.get(weak[0][1], weak[0][1])
        actions.append(f"Weakest scored topic: {label} at {weak[0][0]:.0f}% - timed set of 25")
    if r["accuracy"] is None:
        actions.append("Log scores on practice sets so accuracy becomes measurable.")
    elif not r["mock"]:
        actions.append("Sit Mock 1 as soon as the learn phase is complete.")
    if actions:
        print("NEXT BEST ACTION")
        for i, text in enumerate(actions, 1):
            print(f"  {i}. {text}")


def cmd_pace(a):
    rows = read_log()
    p = profile()
    today = dt.date.today()
    budget = lessons_data()["totals"]["total"] * 60
    logged = sum(r["minutes"] for r in rows if r["lesson"])
    remaining = max(budget - logged, 0)
    exam = dt.date.fromisoformat(p["exam_date"])
    weeks = max((exam - today).days / 7, 1)
    req = remaining / 60 / weeks

    planned = 0.0
    idx = lesson_index()
    for b in curriculum():
        mix = b.get("lesson_mix", {})
        lesson_h = 0.0
        for lid in b.get("lessons", []):
            item = idx.get(lid)
            if not item:
                continue
            lesson_h += (mix.get("learn", 0) * item["learn"]
                         + mix.get("practice", 0) * item["practice"]
                         + mix.get("review", 0) * item["review"])
        s = dt.date.fromisoformat(b["start"])
        e = dt.date.fromisoformat(b["end"])
        if today >= e:
            planned += lesson_h
        elif today >= s:
            planned += lesson_h * (today - s).days / max((e - s).days, 1)
    delta = logged / 60 - planned

    cutoff = today - dt.timedelta(days=28)
    recent = sum(r["minutes"] for r in rows if r["lesson"] and r["date"] >= cutoff.isoformat()) / 60
    rate = recent / 4
    active_days = len({r["date"] for r in rows if r["lesson"] and r["date"] >= cutoff.isoformat()})
    print(f"Lesson work: {logged / 60:.1f}/{budget / 60:.0f} h  ({100 * logged / budget:.0f}%)")
    print(f"Planned to date: {planned:.1f} h  ->  delta {delta:+.1f} h")
    print(f"Remaining: {remaining / 60:.1f} h over {weeks:.0f} weeks  ->  {req:.1f} h/week required")
    print(f"Trailing 4 weeks: {rate:.1f} h/week over {active_days} study day(s)")
    if rate > 0 and active_days >= 4:
        finish = today + dt.timedelta(weeks=(remaining / 60) / rate)
        verdict = "ON TIME" if finish <= exam else "LATE"
        print(f"At this rate: finish {finish.isoformat()}  ({verdict}; exam {exam.isoformat()})")
    elif rate > 0:
        print("At this rate: not enough recent data for a projection (need 4+ study days in 28).")
    else:
        print("At this rate: no recent lesson sessions logged.")
    if delta >= 5:
        print("Verdict: AHEAD of the plan. Do not add modules; add questions.")
    elif delta <= -5:
        print("Verdict: BEHIND. Protect the learn block and cut optional practice extras.")
    else:
        print("Verdict: ON PLAN.")


def cmd_doctor(a):
    problems = []
    today = dt.date.today()
    for name in ("profile.json", "plan/curriculum.json", "plan/lessons.json", "plan/master_plan.md"):
        path = HOME / name
        if path.exists():
            print(f"[ok]   {name}")
        else:
            print(f"[fail] {name} missing")
            problems.append(name)
    try:
        p = profile()
        if dt.date.fromisoformat(p["exam_date"]) <= today:
            print("[warn] exam_date is in the past")
        else:
            print(f"[ok]   exam_date {p['exam_date']}")
    except Exception as e:  # noqa: BLE001
        print(f"[fail] profile.json: {e}")
        problems.append("profile")
    try:
        ls = lessons()
        nums = [l["n"] for l in ls]
        assert len(ls) == 102 and nums == list(range(1, 103)), "lesson ids are not LM1..LM102"
        assert all(abs(l["learn"] + l["practice"] + l["review"] - l["total"]) < 1e-9 for l in ls)
        print("[ok]   102 modules, hour splits consistent")
    except Exception as e:  # noqa: BLE001
        print(f"[fail] lessons.json: {e}")
        problems.append("lessons")
    try:
        ids = {l["id"] for l in lessons()}
        p1 = [b for b in curriculum() if b["id"].startswith("P1")]
        p2 = [b for b in curriculum() if b["id"].startswith("P2")]
        c1 = [i for b in p1 for i in b["lessons"]]
        c2 = [i for b in p2 for i in b["lessons"]]
        assert len(c1) == 102 and set(c1) == ids, "learn phase does not cover each module once"
        assert len(c2) == 102 and set(c2) == ids, "practice phase does not cover each module once"
        print("[ok]   curriculum covers all modules once in Learn and once in Practice")
    except Exception as e:  # noqa: BLE001
        print(f"[fail] curriculum.json: {e}")
        problems.append("curriculum")
    rows = read_log()
    bad = [r for r in rows if r["lesson"] and r["lesson"] not in {l["id"] for l in lessons()}]
    if bad:
        print(f"[warn] {len(bad)} progress rows reference unknown lesson ids")
    else:
        print(f"[ok]   progress.csv: {len(rows)} sessions, all lesson ids valid")
    for r in rows:
        if r["score"]:
            try:
                s = float(r["score"])
                assert 0 <= s <= 100
            except (ValueError, AssertionError):
                print(f"[warn] score out of range on {r['date']}: {r['score']}")
                break
    err = read_errors()
    print(f"[ok]   errors.csv: {len(err)} logged, {len(open_errors())} open")
    mocks = read_mocks()
    print(f"[ok]   mocks.csv: {len(mocks)} logged")
    if problems:
        sys.exit(1)


def cmd_guide(a):
    path = HOME / "guide.html"
    if not path.exists():
        sys.exit(f"{path} not found.")
    webbrowser.open(path.as_uri())
    print(f"Opened {path}")


def cmd_tracker(a):
    path = HOME / "CFA_Level_I_Tracker.xlsx"
    if not path.exists():
        sys.exit("Tracker not found. Run: python make_workbook.py")
    webbrowser.open(path.as_uri())
    print(f"Opened {path}")




def cmd_nudge(a):
    today = dt.date.today()
    p = profile()
    try:
        _, tasks = day_tasks(monday(today), today)
        target = sum(t.get("minutes", 0) for t in tasks)
    except SystemExit:
        target = 0
    logged = minutes_on(today)
    ratio = logged / target if target else 1.0
    if target == 0:
        return
    remaining = max(target - logged, 0)
    if a.final:
        if ratio < 1.0:
            notify("CFA - close the day",
                   f"{logged}/{target} min. {remaining} min left. Log what you did, or move it to tomorrow "
                   f"and say so: cfa.py log \"...\" MIN")
        return
    if ratio < 0.6:
        notify("CFA - behind today",
               f"{logged}/{target} min ({ratio:.0%}). {remaining} min left in the evening block. "
               f"Do the highest-value task first, skip the rest.")


def cmd_review(a):
    today = dt.date.today()
    ws = monday(today) - dt.timedelta(days=7)
    f = WEEKS / f"{ws.isoformat()}.json"
    rows = read_log()
    lines = [f"# Weekly review - week of {ws.isoformat()}", ""]
    if not f.exists():
        lines.append("No plan was generated for that week.")
    else:
        plan = json.loads(f.read_text())
        lines += ["| Day | Planned | Logged | Delta |", "|---|---|---|---|"]
        tp = tl = 0
        for d in DAYS:
            day = ws + dt.timedelta(days=DAYS.index(d))
            planned = sum(t.get("minutes", 0) for t in plan["days"].get(d, []))
            logged = minutes_on(day, rows)
            tp += planned
            tl += logged
            lines.append(f"| {d} {day.isoformat()} | {planned} | {logged} | {logged - planned:+d} |")
        lines += ["", f"**Total: {tl}/{tp} min ({100 * tl / tp:.0f}%)**" if tp else "", ""]
        lines.append(f"**Checkpoint:** {plan.get('checkpoint', '')}")
    REVIEWS.mkdir(parents=True, exist_ok=True)
    out = REVIEWS / f"{today.isoformat()}.md"
    out.write_text("\n".join(lines))
    print("\n".join(lines))
    print(f"\nWritten to {out}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    m = sub.add_parser("master")
    m.add_argument("--force", action="store_true")
    m.set_defaults(fn=cmd_master)

    w = sub.add_parser("week")
    w.add_argument("--next", action="store_true")
    w.add_argument("--force", action="store_true")
    w.add_argument("--offline", action="store_true", help="skip the model, build from curriculum.json")
    w.set_defaults(fn=cmd_week)

    t = sub.add_parser("today")
    t.add_argument("--notify", action="store_true")
    t.set_defaults(fn=cmd_today)

    lg = sub.add_parser("log")
    lg.add_argument("text")
    lg.add_argument("minutes", type=int)
    lg.add_argument("--topic")
    lg.add_argument("--score")
    lg.add_argument("--date")
    lg.add_argument("--lesson", help="module id, e.g. LM56")
    lg.set_defaults(fn=cmd_log)

    sub.add_parser("status").set_defaults(fn=cmd_status)

    ls = sub.add_parser("lessons")
    ls.add_argument("--topic")
    ls.add_argument("--next", type=int)
    ls.add_argument("--remaining", action="store_true")
    ls.add_argument("--write", action="store_true", help="regenerate plan/lessons.md")
    ls.set_defaults(fn=cmd_lessons)

    du = sub.add_parser("due")
    du.add_argument("--limit", type=int, default=15)
    du.add_argument("--all", action="store_true", help="include modules already at budget")
    du.add_argument("--write", action="store_true", help="also write plan/due.md")
    du.set_defaults(fn=cmd_due)

    er = sub.add_parser("error")
    er.add_argument("text")
    er.add_argument("--topic")
    er.add_argument("--lesson")
    er.add_argument("--why")
    er.add_argument("--date")
    er.set_defaults(fn=cmd_error)

    ers = sub.add_parser("errors")
    ers.add_argument("--all", action="store_true")
    ers.add_argument("--topic")
    ers.set_defaults(fn=cmd_errors)

    cl = sub.add_parser("close")
    cl.add_argument("ids", nargs="+", type=int)
    cl.set_defaults(fn=cmd_close)

    mk = sub.add_parser("mock")
    mk.add_argument("score", nargs="?", type=float)
    mk.add_argument("--note")
    mk.add_argument("--date")
    mk.set_defaults(fn=cmd_mock)

    sub.add_parser("analytics").set_defaults(fn=cmd_analytics)
    sub.add_parser("pace").set_defaults(fn=cmd_pace)
    sub.add_parser("doctor").set_defaults(fn=cmd_doctor)
    sub.add_parser("guide").set_defaults(fn=cmd_guide)
    sub.add_parser("tracker").set_defaults(fn=cmd_tracker)

    n = sub.add_parser("nudge")
    n.add_argument("--final", action="store_true")
    n.set_defaults(fn=cmd_nudge)

    sub.add_parser("review").set_defaults(fn=cmd_review)

    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
