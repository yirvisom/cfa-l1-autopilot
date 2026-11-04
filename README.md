# CFA Level I autopilot

A terminal-first study system that turns 102 learning modules into a week you can actually execute.

I built this for my own May 2028 run. It is not a course, a question bank, or a dashboard that congratulates you. It is a small Python program that answers one question every morning: **what exactly do I do today, and for how long?**

```text
$ cfa today
Wed 04 Nov 2026  |  0 - Setup  |  558 days to exam
Target 195 min  ·  logged 0 min  ·  English 0/60 min  ·  0%
Next deadline: Registration opens (May 2028) + Access Scholarship window opens - 284 days (2027-08-15)
Focus: Toolkit: error log, formula sheet, flashcard deck, calculator drills, baseline diagnostic

[ ] English: 30 min reading + 30 min explaining yesterday's topic aloud  (60 min)  - financial press, own voice notes
[ ] Build the formula sheet skeleton for all 10 topics  (80 min)  - profile resources / official curriculum
[ ] Practice the same material: 15 questions, immediate correction  (55 min)  - question bank

Checkpoint: Error log, formula sheet and deck created; baseline diagnostic scored by topic
```

## Why this exists

I lost a Sunday to planning. Not to studying — to planning. I had the syllabus, a spreadsheet, three colours of highlighter, and no idea what to do on Monday at 19:30. The spreadsheet said "Fixed Income". That is not a task. That is a topic.

So I wrote a script that prints the day. Then I missed a week, and the plan kept pretending I had not. That was the real bug: **a plan that does not read your log is fiction.** The log became the source of truth, and the weekly plan became something that reacts to it instead of performing at it.

The hour model follows the same logic. `plan/lessons.json` gives every module a learn / practice / review budget. The 102 modules total **471 hours**. Add mocks, timed sets and remediation and you get roughly **730 hours** across 79 weeks — about **9.3 CFA hours a week**, not 30. The 30-hour ceiling in `profile.json` is insurance against exams, work and missed weeks. A plan that assumes 30 hours a week for 18 months dies in month four.

## Quick start

### Linux, macOS, WSL or Git Bash

```bash
git clone https://github.com/yirvisom/cfa-l1-autopilot.git
cd cfa-l1-autopilot
bash install.sh
cfa doctor
cfa today
```

The installer checks Python 3.9+, creates `profile.json` from the example, creates `~/.config/cfa/env`, puts a `cfa` launcher in `~/.local/bin`, and adds that folder to your shell PATH once. On Linux it also installs four systemd user timers. On macOS there is no systemd, so it skips them; run `cfa today` by hand or wire it into your own scheduler.

If `cfa` is not found, open a new terminal or `source ~/.bashrc` (or `~/.zshrc`).

### Windows

```powershell
git clone https://github.com/yirvisom/cfa-l1-autopilot.git
cd cfa-l1-autopilot
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

Open a new terminal, then:

```powershell
cfa doctor
cfa today
```

Add `-Timers` if you want the four Scheduled Tasks:

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1 -Timers
```

### The optional key

The only network calls are the weekly planner and `cfa master`. If you do not give it a key, the week falls back to the offline builder. The rest — logging, reviews, analytics, the Excel tracker — runs locally.

```bash
nano ~/.config/cfa/env          # Linux / macOS / WSL
notepad $HOME\.config\cfa\env   # Windows PowerShell
```

```dotenv
DEEPSEEK_API_KEY=your-key
# DEEPSEEK_BASE_URL=https://api.deepseek.com
# DEEPSEEK_MODEL=deepseek-flash
```

Any OpenAI-compatible `/chat/completions` endpoint works. If the call fails, the script does not leave you without a plan: it builds the week deterministically from `plan/curriculum.json` and `plan/lessons.json`.

## The 60-second tour

```bash
cfa today                     # today's tasks, target, logged minutes, next deadline
cfa log "LM56 20 questions" 60 --lesson LM56 --score 70
cfa status                    # hours, coverage, due reviews, errors, streak
cfa lessons --next 8          # the next modules, with hours and what is already logged
cfa due                       # spaced-review queue, with stage and days late
cfa analytics                 # readiness index, coverage and accuracy by topic
cfa pace                      # planned vs logged, required h/week, projected finish
cfa doctor                    # validate the plan and the CSV files
```

Logging is the part that matters. A session without a lesson id still counts toward total hours, but it cannot advance a module's coverage or its spaced-review clock. Use `--lesson LM56` when you can.

## How the week gets built

`cfa week --next` collects the master plan, the current dated block, the exact modules due that week, the spaced-review queue, the open error log, last week's plan and your recent log. Then it asks for a Monday-to-Sunday plan under hard rules:

- the total must stay inside the weekly budget;
- every CFA task names one of the week's module ids;
- reviews come before new material;
- the daily English block stays where it is;
- resources come from the profile, never invented;
- Friday is light, Saturday and Sunday carry the long blocks.

If you would rather not involve a model at all:

```bash
cfa week --force --offline
```

That builds the same week from `curriculum.json`: a seven-day read / practice / read / practice / review / long block / review arc, with the budget allocated by your day weights. It is less specific than a model-written week, and it never invents a page number.

The Sunday 19:00 timer runs `cfa review`, then `cfa week --next`. The review file lands in `plan/reviews/`, the new week in `plan/weeks/`.

## Spaced repetition and the error log

The review queue is derived entirely from `progress.csv`. First session: review in 1 day. Then 3, 7, 21, 45. Logging the review against the same module id is what advances the interval, so the queue cannot be gamed by opening a flashcard app and closing it.

The error log is deliberately blunt:

```bash
cfa error "Duration sign flipped on a putable bond" --lesson LM58 --why "confused modified duration with Macaulay"
cfa errors
cfa close 3
```

The `--why` line is the useful part. "I got it wrong" is not a cause. "I used modified duration where the question asked for the price change per 100 bp" is a cause you can fix.

## Commands

| Command | What it does |
|---|---|
| `cfa today` | Today's tasks, target minutes, logged minutes, next deadline and mock |
| `cfa log "LM56 20 questions" 60 --lesson LM56 --score 70` | Record a session against a module |
| `cfa log "ethics" 60 --topic ethics --date 2026-10-27` | Backfill a forgotten day |
| `cfa lessons --next 8` | The next modules in sequence, with hours and logged time |
| `cfa lessons --remaining` | Everything not yet covered |
| `cfa lessons --topic fixed income` | One topic, module by module |
| `cfa due` | Spaced-review queue: what is due now, with stage and days late |
| `cfa error "text" --lesson LM56 --why "cause"` | Add an error-log item |
| `cfa errors` / `cfa close 3` | List open errors / mark them fixed |
| `cfa mock 68 --note "cold"` / `cfa mock` | Log a mock score / list the mock history |
| `cfa analytics` | Readiness index, coverage and accuracy by topic, next best action |
| `cfa pace` | Planned vs logged hours, required h/week, projected finish |
| `cfa doctor` | Validate the plan and data files |
| `cfa guide` | Open the HTML operating manual |
| `cfa tracker` | Open the Excel tracker |
| `cfa status` | Hours, module coverage, due reviews, errors, streak, week progress |
| `cfa review` | Written planned-vs-logged review of last week |
| `cfa week --offline` | Rebuild the week without calling the model |
| `cfa nudge` / `cfa nudge --final` | Evening check-in / end-of-day close |

## What lives where

```text
profile.json                  exam date, weekly ceilings, day weights, deadlines, resources
plan/lessons.json             the 102 modules and their hour budgets (source of truth)
plan/lessons.md               readable table; regenerate with `cfa lessons --write`
plan/master_plan.md           the human roadmap: phases, budget, mocks, risks
plan/curriculum.json          17 dated blocks, used as context and as the offline fallback
plan/weeks/                   generated weekly plans (.json + readable .md)
plan/reviews/                 generated weekly reconciliations
progress.csv                  one row per session
errors.csv                    the error log
mocks.csv                     one row per mock sitting
guide.html                    the operating manual (open with `cfa guide`)
CFA_Level_I_Tracker.xlsx      the Excel tracker (open with `cfa tracker`)
```

Everything is local. There is no account, no sync service and no telemetry. If you delete the folder, the data is gone.

## The Excel tracker

`CFA_Level_I_Tracker.xlsx` has Dashboard, Sessions, Modules, Errors, Mocks, Plan and Setup sheets. It is generated from the same JSON files, so the 102 modules, hours, phases and exam dates match the terminal. Yellow cells are inputs; the rest are formulas.

Rebuild it after changing the plan:

```bash
pip install openpyxl
python make_workbook.py
```

On Windows, `finalize_workbook.ps1` recalculates the cached values with Excel if Excel is installed. Do not edit the formula sheets by hand.

## Timers

| Time | Unit / task | What it sends |
|---|---|---|
| 07:30 daily | `cfa-daily` | Today's tasks, target and next deadline |
| 21:30 daily | `cfa-nudge` | "Behind today" alert if under 60% of the target |
| 22:30 daily | `cfa-final` | "Close the day": log what is left, or move it explicitly |
| Sun 19:00 | `cfa-weekly` | Weekly review, then next week's plan |

On Linux, `install.sh` writes systemd **user** units. `Persistent=true` means a run missed while the laptop was off happens at the next boot. `loginctl enable-linger` keeps the timers alive when you are logged out. If linger cannot be enabled, the installer says so instead of pretending.

On Windows, `install.ps1 -Timers` registers the same four tasks in Task Scheduler and uses `StartWhenAvailable` for the same reason.

Every notification is also appended to `~/.local/state/cfa/inbox.log`, so a missed desktop notification is still a line in a file. Optional phone push: install ntfy and set `NTFY_TOPIC` in `~/.config/cfa/env`.

## Make it yours

The shipped plan is a worked example, not a universal syllabus. The dates assume a May 2028 window and a start in late October 2026.

- **Change the exam date or weekly ceiling:** edit `profile.json`, then `cfa week --force`.
- **Change a module's hours:** edit `plan/lessons.json`, then `cfa lessons --write` and `cfa week --force`.
- **Change the roadmap:** edit `plan/master_plan.md` and `plan/curriculum.json` together, then `cfa week --force`.
- **Change the planner's rules:** edit `prompts/weekly.md`. This is the most useful file to tune once you know how you actually study.
- **Change the voice of the notifications:** `cfa.py`, `notify()`.

`cfa master --force` would overwrite the curated `master_plan.md` with a model-generated one. Read it before you run it.

## What it does not do

- **It is not official CFA material.** The 102 module names and 471-hour budget are my own planning notes. No CFA Institute curriculum text, question bank or mock is included. CFA Institute is not affiliated with this project and does not endorse it.
- **It does not replace practice questions.** The system tells you what to do and records what you did. The actual learning happens in the question bank and in the correction.
- **The exam date is an estimate.** 15 May 2028 is a placeholder for the May 2028 window. Change it in `profile.json` when the real calendar is published.
- **A model-written week can be wrong.** The prompt constrains the budget and the module ids, but you should still read the week before you follow it. `cfa doctor` validates structure, not judgement.
- **No mobile app, no cloud, no sync.** CSV files in a folder. That is the point, but it is also a limit.
- **Timers are platform-specific.** systemd on Linux, Task Scheduler on Windows. macOS users get the `cfa` command and the installer stops there.
- **Not investment advice.** Nothing here is a recommendation to buy or sell anything.

## License

MIT. See [LICENSE](LICENSE).

---

Built by [Yirviel Somé](https://deyirviel.com). The longer story — why the log matters more than the plan, and what the system still gets wrong — is on the [project page](https://deyirviel.com/tools/cfa-l1-autopilot/).
