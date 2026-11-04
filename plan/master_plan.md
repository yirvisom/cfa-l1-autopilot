# CFA Level I — master plan (CURATED, v2)

> Hand-maintained roadmap, rebuilt on the **2027 curriculum: 102 learning modules**.
> Target: **May 2028 window (est. 15–21 May)**. **558 days** from 4 Nov 2026.
> Module budget: **471 h** of learn + practice + revision. Full programme: **~730 h CFA + 60 min/day English**.
> The full 102-row hour table is in `plan/lessons.md`; regenerate it with `cfa.py lessons --write`.

## 1. Executive summary

The plan is now built from the actual syllabus, not from topic labels. Every one of the 102 modules has an hour budget split into **learn / practice / revision**, and every week of the calendar names the modules it covers.

The arithmetic that matters:

| Item | Hours |
|---|---:|
| Learn the 102 modules (first contact, notes, formula sheet) | 223.5 |
| Practice (end-of-module sets, question bank, timed sets) | 165.5 |
| Revision (two spaced passes, flashcards, error log) | 82.0 |
| **Module work** | **471.0** |
| Mocks, timed sets, remediation and the M2 maintenance month | 259.0 |
| **Programme (Nov 2026 – May 2028, 79 weeks)** | **730** |
| English, 1 h/day (inside the weekly budget, outside the 730) | ~550 |

That is **~9.3 CFA hours per week on average**, not 30. The 30 h/week ceiling in `profile.json` stays as a ceiling; the spare capacity is deliberate insurance against M2 exams, the PFE, internships and missed weeks. A plan that assumes 30 h/week for 18 months fails in month four; this one assumes the hours the syllabus actually needs and lets you add practice when life is calm.

Three consequences:

1. **The first pass is a learning pass, not a race.** You touch all 102 modules once between Nov 2026 and Jul 2027, weakest topics first (Ethics, Fixed Income, Derivatives, Economics).
2. **Practice is a separate, dated phase.** From Jul 2027 the question bank and timed sets carry the load; reading time falls.
3. **The last 10 weeks taper.** No new material after 3 April 2028. Mocks, error log, formula sheets, sleep.

## 2. What the hour numbers mean

| Component | What counts | What does not count |
|---|---|---|
| **Learn** | Read the module once, take notes in your own words, write the formula-sheet entry, do 5–10 check questions | Re-reading, highlighting, copying the curriculum |
| **Practice** | End-of-module questions, question-bank sets, timed topic sets, full correction of every miss | Passive video watching |
| **Revision** | Two spaced passes: flashcards (1/3/7/21 days) and redoing the misses from the error log | A third full read |

Hours are CFA-only. English (1 h/day) sits on top and is counted inside each block's weekly budget.

Why the totals differ by topic: Fixed Income is both the largest block (19 modules) and your weakest, so it gets 95.5 h. Quantitative Methods and Equity are strengths, so they get 36.5 h and 46.5 h for the same exam weight. The budget follows **your** gaps, not the syllabus page count.

## 3. Budget by topic

| Topic | Exam weight (2027 proxy) | Modules | Learn | Practice | Revision | Total | h / module |
|---|---|---:|---:|---:|---:|---:|---:|
| Quantitative Methods | 11–14 % | 11 | 17.0 | 14.0 | 5.5 | 36.5 | 3.3 |
| Economics | 6–9 % | 8 | 20.0 | 13.0 | 7.5 | 40.5 | 5.1 |
| Corporate Issuers | 6–9 % | 7 | 13.5 | 10.5 | 5.0 | 29.0 | 4.1 |
| Financial Statement Analysis | 11–14 % | 12 | 30.5 | 23.5 | 11.0 | 65.0 | 5.4 |
| Equity | 11–14 % | 12 | 22.0 | 16.5 | 8.0 | 46.5 | 3.9 |
| Fixed Income | 11–14 % | 19 | 44.5 | 33.5 | 17.5 | 95.5 | 5.0 |
| Derivatives and Risk Management | 5–8 % | 10 | 25.0 | 17.5 | 9.0 | 51.5 | 5.2 |
| Alternative Investments | 7–10 % | 7 | 13.5 | 10.5 | 4.0 | 28.0 | 4.0 |
| Portfolio Construction | 8–12 % | 6 | 12.5 | 9.0 | 4.5 | 26.0 | 4.3 |
| Ethical and Professional Standards | 10–15 % | 10 | 25.0 | 17.5 | 10.0 | 52.5 | 5.3 |
| **Total** | | **102** | **223.5** | **165.5** | **82.0** | **471.0** | **4.6** |

## 4. Phase plan

`h/week` includes the 7 h/week English block. `CFA h` is the block total.

| Phase | Dates | Weeks | Modules | CFA h | h/week | Exit criteria |
|---|---|---:|---|---:|---:|---|
| 0. Setup | 26 Oct – 8 Nov 2026 | 2 | toolkit | 46 | 30 | Error log, formula sheet, deck; baseline diagnostic scored |
| 1a. Learn | 9 Nov – 20 Dec 2026 | 6 | LM93–102, LM1–4 | 43 | 14 | Ethics Standards from memory; 100 questions logged |
| 1b. Learn | 21 Dec 2026 – 31 Jan 2027 | 6 | LM27–33, LM20–23 | 38 | 13.5 | Three-statement map; FSA quiz ≥ 70 % |
| 1c. Learn | 1 Feb – 14 Mar 2027 | 6 | LM51–62 | 42 | 14 | Duration/convexity by hand; 80 FI questions |
| 1d. Learn | 15 Mar – 25 Apr 2027 | 6 | LM63–69, LM70–74 | 39 | 13.5 | Credit/curve questions ≥ 70 %; forwards from a blank sheet |
| 1e. Learn | 26 Apr – 6 Jun 2027 | 6 | LM75–79, LM12–19 | 47 | 15 | Payoff diagrams from memory; FX/parity ≥ 65 % |
| 1f. Learn | 7 Jun – 18 Jul 2027 | 6 | LM5–11, 24–26, 34–38, 39–50, 80–92 | 113 | 26 | Half diagnostic ≥ 55 %; all 102 modules seen once |
| 2a. Practice | 19 Jul – 15 Aug 2027 | 4 | LM1–19 | 36 | 16 | End-of-module sets ≥ 70 % |
| 2b. Practice | 16 Aug – 12 Sep 2027 | 4 | LM20–38 | 32 | 15 | Mock 1 ≥ 55 % |
| 2c. Practice | 13 Sep – 17 Oct 2027 | 5 | LM51–69 | 40 | 15 | FI timed sets ≥ 70 % |
| 2d. Practice | 18 Oct – 7 Nov 2027 | 3 | LM70–79, LM39–50 | 30 | 17 | Derivatives ≥ 70 %; valuation models rebuilt |
| 2e. Practice | 8 – 28 Nov 2027 | 3 | LM80–92, LM93–102 | 34 | 18.5 | Mock 2 ≥ 60 %; every module marked done |
| 3a. Timed | 29 Nov 2027 – 9 Jan 2028 | 6 | mixed | 84 | 21 | Mock 3 ≥ 65 %; two weakest topics ≥ 65 % |
| 3m. Maintenance | 10 – 31 Jan 2028 | 3 | mixed | 10 | 10.5 | M2 exams: 100 questions logged, no lost ground |
| 3b. Mocks | 1 – 13 Feb 2028 | 2 | mixed | 45 | 29.5 | Mock average ≥ 65 %; test-centre slot booked |
| 4a. Final | 14 Feb – 2 Apr 2028 | 7 | mixed | 60 | 15.5 | Mock average ≥ 70 %; error log current |
| 4b. Taper | 3 Apr – 14 May 2028 | 6 | consolidation | 35 | 13 | Exam-ready; passport and calculator checked |

The two spikes are deliberate: June–July 2027 is the summer holiday (no classes), and the two weeks before Mock 5 are a short mock block. Every other week is 13–18 h of total study, which fits around an M2 timetable.

## 5. Mock calendar

| Date | Event | Target |
|---|---|---|
| 18 Jul 2027 | Half-length diagnostic (end of Learn) | ≥ 55 % |
| 26 Sep 2027 | Mock 1 | ≥ 55 % |
| 28 Nov 2027 | Mock 2 (end of Practice) | ≥ 60 % |
| 20 Dec 2027 | Mock 3 | ≥ 65 % |
| 6 Feb 2028 | Mock 4 | ≥ 65 % |
| 13 Feb 2028 | Mock 5 | ≥ 65 % |
| 27 Feb 2028 | Mock 6 | ≥ 70 % |
| 12 Mar 2028 | Mock 7 | ≥ 70 % |
| 26 Mar 2028 | Mock 8 | ≥ 70 % |
| 2 Apr 2028 | Mock 9 | ≥ 70 % |
| 16 Apr 2028 | Mock 10 | ≥ 72 % |
| 1 May 2028 | Mock 11 | ≥ 72 % |
| 8 May 2028 | Mock 12 (last full mock) | ≥ 75 % |

Full mock = 4.5 h under exam conditions + 4 h correction. Correction is worth more than the score: every miss gets a one-line *why* and an error-log entry.

## 6. Weekly rhythm

**Term (typical 7–8 CFA h/week):** English 06:30–07:30 every day. CFA on five weekday evenings of 60–75 min (19:30–20:45, never past 22:00) plus 2–3 h on Saturday and Sunday mornings. Friday is light: flashcards and error log only. This is intentionally less than the 30 h ceiling — the extra time is for M2 coursework and recovery.

**Holiday (15–19 CFA h/week):** add the 09:00–12:00 block on weekdays. Hardest material there, questions in the afternoon. English stays at 06:30.

**Final 10 weeks:** mocks on Saturday mornings, correction on Sunday. Weekdays become flashcards + error log + 25 questions. No new material.

## 7. Adaptation rules

- A week below 60 % of planned minutes: **cut the lowest-value task next week**. Never add hours to catch up.
- Behind the module schedule by more than 3 modules: drop the practice extras, protect the learn block.
- Ahead of schedule: **do not add new modules**; add question sets and bring the next mock forward by a week.
- A mock below 55 %: one week of pure remediation on the two weakest topics, then resume. No date changes.
- The same topic below 60 % twice: switch resource (own book → official curriculum) for that topic.
- Two consecutive missed weeks: 3 h/week for one week to restart the habit; do not attempt the backlog.
- Model unavailable on Sunday: the week is built offline from `curriculum.json` + `lessons.json`. Never plan by hand in a rush.
- Registration not done by **14 Oct 2027**: stop the study plan and fix the deadline first.

## 8. Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| Burnout: M2 + PFE + 18-month runway | High | ~9 h/week average, Friday light, one full rest week per quarter, no backlog chasing |
| PFE collision (Feb–May 2028) | High | No new material after 3 Apr; mocks on Saturday mornings only; taper in May |
| M2 exams (Jan and May 2028) | Certain | January is a 5 h/week maintenance block; May is taper-only |
| Module-level drift (a topic silently skipped) | Medium | `cfa lessons --remaining` shows exactly what is untouched; weekly plan names module ids |
| Over-preparation complacency (content done by Jul 2027) | Medium | Practice phase is dated and scored; the score comes from questions, not readings |
| Tooling failure (API, timers, laptop off) | Medium | Offline fallback from JSON, file inbox, `Persistent=true` |
| Missing the registration window | Low but fatal | Countdown in every daily brief |

## 9. Metrics and commands

```bash
cfa today                     # today's tasks, target, logged minutes, next deadline and mock
cfa log "LM56 20 questions" 60 --lesson LM56 --score 70
cfa due                       # spaced-review queue: what is due now
cfa error "text" --lesson LM56 --why "cause"   # add an error-log item
cfa errors                    # open error-log items
cfa close 3                   # mark an error as fixed
cfa mock 68 --note "cold"     # log a mock score
cfa analytics                 # readiness, coverage and accuracy by topic
cfa pace                      # planned vs logged hours, projected finish
cfa lessons --next 8          # next modules in sequence with their hour budgets
cfa lessons --remaining       # everything not yet logged
cfa lessons --topic fixed income
cfa status                    # hours, module coverage, streak, week progress
cfa week --offline            # rebuild this week without calling the model
cfa doctor                    # validate the plan and data files
cfa guide                     # open the HTML operating manual
```

Log every session against a module id. Without the id, `lessons` cannot tell what is done; the topic total alone is not enough. Log scores only on question sets: that is what makes `analytics` able to separate coverage from accuracy.

## 10. Files

- `plan/lessons.json` — the 102 modules, hour split, topic, exam weight, resource. **Source of truth.**
- `plan/lessons.md` — readable 102-row table, regenerated with `cfa lessons --write`.
- `plan/curriculum.json` — 17 dated blocks naming the modules they cover, weekly load and exit criteria.
- `plan/weeks/` — generated weekly plans (`.json` + `.md`), now module-aware.
- `progress.csv` — `date,minutes,topic,note,score,lesson`.
- `profile.json` — exam date, ceilings, checkpoints, constraints.
