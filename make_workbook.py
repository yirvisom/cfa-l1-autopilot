#!/usr/bin/env python3
"""Build the Excel tracker from lessons.json, curriculum.json, profile.json and the logs.

Usage:  python make_workbook.py
Output: CFA_Level_I_Tracker.xlsx (same folder)

The workbook is self-contained: formulas compute coverage, accuracy, due reviews,
phase progress, readiness and the calendar. Yellow cells are inputs; the rest is
formula-driven. Re-run after changing the plan to regenerate with the new dates.
"""
import csv
import json
import os
import subprocess
from datetime import date, datetime
from pathlib import Path

from openpyxl import Workbook
from openpyxl.chart import BarChart, LineChart, Reference
from openpyxl.formatting.rule import CellIsRule, DataBarRule, FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.properties import PageSetupProperties

HOME = Path(__file__).resolve().parent
PLAN = HOME / "plan"
OUT = HOME / "CFA_Level_I_Tracker.xlsx"

SESS_LAST = 1501
ERR_LAST = 301
MOCK_LAST = 101
PLAN_LAST = 18
KEY_FIRST = 22
KEY_LAST = 60

NAVY = "0B1F2A"
GOLD = "B8860B"
GOLD_LIGHT = "FFF4D6"
GREEN = "1E7B45"
GREEN_LIGHT = "E6F4EA"
RED = "B23B3B"
RED_LIGHT = "FBE9E9"
AMBER = "B7791F"
AMBER_LIGHT = "FFF4E0"
GREY = "6B7A80"
LIGHT = "F5F7F8"
INPUT = "FFFBE6"
BORDER = "DDE4E8"

FONT = "Calibri"
MONO = "Consolas"

thin = Side(style="thin", color=BORDER)
box = Border(left=thin, right=thin, top=thin, bottom=thin)


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def as_date(text):
    return date.fromisoformat(text)


def fill(hex_color):
    return PatternFill("solid", fgColor=hex_color)


def header_row(ws, row, ncols, height=26):
    for c in range(1, ncols + 1):
        cell = ws.cell(row=row, column=c)
        cell.fill = fill(NAVY)
        cell.font = Font(name=FONT, size=9, bold=True, color="FFFFFF")
        cell.alignment = Alignment(vertical="center", horizontal="left", wrap_text=True)
        cell.border = box
    ws.row_dimensions[row].height = height


def section(ws, row, ncols, text):
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=ncols)
    cell = ws.cell(row=row, column=1, value=text)
    cell.font = Font(name=MONO, size=9, bold=True, color=GOLD)
    cell.fill = fill("0F1517")
    cell.alignment = Alignment(vertical="center")
    ws.row_dimensions[row].height = 20


def widths(ws, mapping):
    for col, w in mapping.items():
        ws.column_dimensions[col].width = w


def data_cell(cell, fmt=None, editable=False, bold=False, align="left", wrap=False):
    cell.font = Font(name=FONT, size=10, bold=bold)
    cell.border = box
    cell.alignment = Alignment(vertical="center", horizontal=align, wrap_text=wrap)
    if fmt:
        cell.number_format = fmt
    if editable:
        cell.fill = fill(INPUT)


# ---------------------------------------------------------------- data ------
profile = load(HOME / "profile.json")
lessons = load(PLAN / "lessons.json")
curriculum = load(PLAN / "curriculum.json")["blocks"]
exam_date = as_date(profile["exam_date"])

by_topic = lessons["by_topic"]
topics = list(by_topic.items())
lesson_rows = lessons["lessons"]
total_budget = lessons["totals"]["total"]

# key dates: deadlines + checkpoints, deduplicated
raw_dates = [(as_date(d["date"]), d["label"], "Deadline") for d in profile.get("deadlines", [])]
for c in profile.get("checkpoints", []):
    label = c["label"]
    low = label.lower()
    kind = "Exam" if "exam" in low else ("Mock" if "mock" in low else "Checkpoint")
    raw_dates.append((as_date(c["date"]), label, kind))
seen = set()
key_dates = []
for d, label, kind in sorted(raw_dates):
    k = (d, label)
    if k in seen:
        continue
    seen.add(k)
    key_dates.append((d, kind, label))
key_dates = key_dates[: KEY_LAST - KEY_FIRST + 1]

# -------------------------------------------------------------- workbook ----
wb = Workbook()
wb.calculation.fullCalcOnLoad = True
wb.properties.creator = "YIRVIEL CAPITAL"
wb.properties.title = "CFA Level I Tracker"

dash = wb.active
dash.title = "Dashboard"
sess = wb.create_sheet("Sessions")
mods = wb.create_sheet("Modules")
errs = wb.create_sheet("Errors")
mocks = wb.create_sheet("Mocks")
plan = wb.create_sheet("Plan")
setup = wb.create_sheet("Setup")

dash.sheet_properties.tabColor = GOLD
sess.sheet_properties.tabColor = NAVY
mods.sheet_properties.tabColor = "1F6F78"
errs.sheet_properties.tabColor = RED
mocks.sheet_properties.tabColor = GREEN
plan.sheet_properties.tabColor = GREY
setup.sheet_properties.tabColor = GREY

# ================================================================ SETUP =====
setup.sheet_view.showGridLines = False
widths(setup, {"A": 26, "B": 18, "C": 4, "D": 30, "E": 13, "F": 30})
setup.merge_cells("A1:F1")
c = setup["A1"]
c.value = "SETUP"
c.font = Font(name=MONO, size=18, bold=True, color=GOLD)
c.fill = fill(NAVY)
c.alignment = Alignment(vertical="center", indent=1)
setup.row_dimensions[1].height = 38

setup["A3"] = "PARAMETERS"
setup["A3"].font = Font(name=MONO, size=9, bold=True, color=GOLD)
params = [
    ("Exam date", exam_date, "yyyy-mm-dd"),
    ("Days to exam", "=B4-TODAY()", "0"),
    ("Lesson budget (h)", "=SUM(Modules!G2:G103)", "0.0"),
    ("Mock target (%)", 70, "0"),
    ("Readiness target", 70, "0"),
    ("Accuracy target (%)", 65, "0"),
    ("Baseline h/week", 9.3, "0.0"),
]
for i, (label, value, fmt) in enumerate(params, start=4):
    setup.cell(row=i, column=1, value=label).font = Font(name=FONT, size=10, bold=True)
    setup.cell(row=i, column=1).border = box
    cell = setup.cell(row=i, column=2, value=value)
    editable = label == "Exam date" or isinstance(value, (int, float))
    data_cell(cell, fmt=fmt, editable=editable, align="right")
setup["A2"] = "Yellow cells are the only inputs here. The exam date drives every countdown; change it when CFA Institute publishes the 2028 calendar."
setup.merge_cells("A2:F2")
setup["A2"].font = Font(name=FONT, size=9, italic=True, color=GREY)
setup["A2"].alignment = Alignment(wrap_text=True, vertical="center")

setup["D4"] = "TOPIC"
setup["E4"] = "WEIGHT %"
for col in ("D", "E"):
    setup[f"{col}4"].font = Font(name=MONO, size=9, bold=True, color="FFFFFF")
    setup[f"{col}4"].fill = fill(NAVY)
    setup[f"{col}4"].border = box
for i, (key, t) in enumerate(topics, start=5):
    setup.cell(row=i, column=4, value=t["name"]).font = Font(name=FONT, size=10)
    setup.cell(row=i, column=4).border = box
    w_parts = t["exam_weight"].replace("%", "").split("-")
    w = (float(w_parts[0]) + float(w_parts[1])) / 2 if len(w_parts) == 2 else float(w_parts[0])
    cell = setup.cell(row=i, column=5, value=w)
    data_cell(cell, fmt='0.0"%"', editable=True, align="right")
    setup.cell(row=i, column=6, value=t["exam_weight"] + " of the exam").font = Font(name=FONT, size=8, color=GREY)

setup["D16"] = "SESSION TYPES"
for col in ("D",):
    setup[f"{col}16"].font = Font(name=MONO, size=9, bold=True, color="FFFFFF")
    setup[f"{col}16"].fill = fill(NAVY)
    setup[f"{col}16"].border = box
for i, name in enumerate(["Learn", "Practice", "Review", "Mock", "English"], start=17):
    setup.cell(row=i, column=4, value=name).font = Font(name=FONT, size=10)
    setup.cell(row=i, column=4).border = box

setup["D24"] = "ERROR STATUS"
setup["D24"].font = Font(name=MONO, size=9, bold=True, color="FFFFFF")
setup["D24"].fill = fill(NAVY)
setup["D24"].border = box
for i, name in enumerate(["Open", "Closed"], start=25):
    setup.cell(row=i, column=4, value=name).font = Font(name=FONT, size=10)
    setup.cell(row=i, column=4).border = box

setup["A28"] = "HOW TO USE"
setup["A28"].font = Font(name=MONO, size=9, bold=True, color=GOLD)
howto = [
    "1. Yellow cells are inputs. Grey/white cells are formulas: do not overwrite them.",
    "2. Log every session on Sessions: date, module, type, minutes. Score only question sets.",
    "3. English sessions: Type = English, Module blank. The Topic is filled automatically.",
    "4. Errors: one row per miss. Write the why-line. Close only when you can redo it cold.",
    "5. Mocks: log the score; the dashboard and the chart update immediately.",
    "6. Modules updates itself: logged hours, %, status, last session, next review, accuracy.",
    "7. Due = DUE on Modules is the spaced-review queue. Filter that column every morning.",
    "8. Keep one source of truth. If you also use the terminal, paste the same rows into Sessions weekly.",
]
for i, text in enumerate(howto, start=29):
    setup.merge_cells(start_row=i, start_column=1, end_row=i, end_column=6)
    cell = setup.cell(row=i, column=1, value=text)
    cell.font = Font(name=FONT, size=9.5, color="C3D0D4")
    cell.fill = fill("0F1517")
    cell.alignment = Alignment(vertical="center", wrap_text=True)
    setup.row_dimensions[i].height = 18

setup.merge_cells("A38:F38")
setup["A38"] = "Generated from plan/lessons.json, plan/curriculum.json and profile.json. Re-run make_workbook.py after changing the plan."
setup["A38"].font = Font(name=FONT, size=8, italic=True, color=GREY)
setup["A38"].alignment = Alignment(wrap_text=True)

# =============================================================== MODULES ====
mods.sheet_view.showGridLines = True
headers = ["LM", "Topic", "Module", "Learn h", "Practice h", "Review h", "Total h",
           "Logged h", "Remaining h", "%", "Status", "Last session", "Next review",
           "Due", "Accuracy", "Priority", "Resource"]
for i, h in enumerate(headers, start=1):
    mods.cell(row=1, column=i, value=h)
header_row(mods, 1, len(headers), 30)
mods.freeze_panes = "A2"
mods.auto_filter.ref = f"A1:Q{len(lesson_rows) + 1}"
widths(mods, {"A": 7, "B": 25, "C": 56, "D": 8, "E": 9, "F": 8, "G": 8, "H": 8,
              "I": 9, "J": 7, "K": 12, "L": 12, "M": 12, "N": 7, "O": 9, "P": 8, "Q": 46})

for r, l in enumerate(lesson_rows, start=2):
    values = [l["id"], l["topic_name"], l["title"], l["learn"], l["practice"], l["review"],
              f"=SUM(D{r}:F{r})",
              f"=SUMIFS(Sessions!$E$2:$E${SESS_LAST},Sessions!$B$2:$B${SESS_LAST},$A{r})/60",
              f"=MAX(0,$G{r}-$H{r})",
              f"=IF($G{r}=0,0,MIN(1,$H{r}/$G{r}))",
              f'=IF($H{r}=0,"Not started",IF($H{r}>=$G{r}*0.95,"Done","In progress"))',
              f'=IF(COUNTIF(Sessions!$B$2:$B${SESS_LAST},$A{r})=0,"",SUMPRODUCT(MAX((Sessions!$B$2:$B${SESS_LAST}=$A{r})*Sessions!$A$2:$A${SESS_LAST})))',
              f'=IF($L{r}="","",$L{r}+CHOOSE(MIN(COUNTIF(Sessions!$B$2:$B${SESS_LAST},$A{r}),5),1,3,7,21,45))',
              f'=IF($M{r}="","",IF(AND($M{r}<=TODAY(),$K{r}<>"Done"),"DUE",""))',
              f'=IFERROR(AVERAGEIFS(Sessions!$F$2:$F${SESS_LAST},Sessions!$B$2:$B${SESS_LAST},$A{r}),"")',
              l["priority"], l["resource"]]
    for i, v in enumerate(values, start=1):
        cell = mods.cell(row=r, column=i, value=v)
        data_cell(cell, fmt=None, wrap=(i in (3, 17)))
    for i in (4, 5, 6, 7, 8, 9):
        mods.cell(row=r, column=i).number_format = "0.0"
    mods.cell(row=r, column=10).number_format = "0%"
    mods.cell(row=r, column=12).number_format = "yyyy-mm-dd"
    mods.cell(row=r, column=13).number_format = "yyyy-mm-dd"
    mods.cell(row=r, column=15).number_format = "0.0"
    mods.cell(row=r, column=1).alignment = Alignment(horizontal="center", vertical="center")
    mods.cell(row=r, column=14).alignment = Alignment(horizontal="center", vertical="center")
    if l["priority"] == "weak":
        mods.cell(row=r, column=16).font = Font(name=FONT, size=9, bold=True, color=RED)
    elif l["priority"] == "strong":
        mods.cell(row=r, column=16).font = Font(name=FONT, size=9, bold=True, color=GREEN)
    mods.row_dimensions[r].height = 30

mods.conditional_formatting.add(f"N2:N{len(lesson_rows) + 1}",
    CellIsRule(operator="equal", formula=['"DUE"'], fill=fill(RED_LIGHT), font=Font(color=RED, bold=True)))
mods.conditional_formatting.add(f"K2:K{len(lesson_rows) + 1}",
    CellIsRule(operator="equal", formula=['"Done"'], fill=fill(GREEN_LIGHT), font=Font(color=GREEN, bold=True)))
mods.conditional_formatting.add(f"K2:K{len(lesson_rows) + 1}",
    CellIsRule(operator="equal", formula=['"In progress"'], fill=fill(AMBER_LIGHT), font=Font(color=AMBER)))
mods.conditional_formatting.add(f"J2:J{len(lesson_rows) + 1}",
    DataBarRule(start_type="num", start_value=0, end_type="num", end_value=1, color="63BE7B", showValue=True))

# ============================================================== SESSIONS ====
sess.sheet_view.showGridLines = True
s_headers = ["Date", "Module", "Topic", "Type", "Minutes", "Score", "Note",
             "Week start", "Month", "Check"]
for i, h in enumerate(s_headers, start=1):
    sess.cell(row=1, column=i, value=h)
header_row(sess, 1, len(s_headers))
sess.freeze_panes = "A2"
sess.auto_filter.ref = f"A1:J{SESS_LAST}"
widths(sess, {"A": 12, "B": 8, "C": 24, "D": 11, "E": 9, "F": 8, "G": 62, "H": 12, "I": 9, "J": 14})

for r in range(2, SESS_LAST + 1):
    sess.cell(row=r, column=3, value=f'=IF($B{r}="","",IFERROR(INDEX(Modules!$B$2:$B$103,MATCH($B{r},Modules!$A$2:$A$103,0)),""))')
    sess.cell(row=r, column=8, value=f'=IF($A{r}="","",$A{r}-WEEKDAY($A{r},3))')
    sess.cell(row=r, column=9, value=f'=IF($A{r}="","",TEXT($A{r},"YYYY-MM"))')
    sess.cell(row=r, column=10, value=f'=IF($A{r}="","",IF(AND($D{r}<>"English",$D{r}<>"Mock",$B{r}=""),"Pick a module","OK"))')
    for col in range(1, 11):
        cell = sess.cell(row=r, column=col)
        data_cell(cell, editable=(col in (1, 2, 4, 5, 6, 7)))
    sess.cell(row=r, column=1).number_format = "yyyy-mm-dd"
    sess.cell(row=r, column=8).number_format = "yyyy-mm-dd"
    sess.cell(row=r, column=5).number_format = "0"
    sess.cell(row=r, column=6).number_format = "0.0"
    sess.cell(row=r, column=2).alignment = Alignment(horizontal="center", vertical="center")
    sess.cell(row=r, column=10).alignment = Alignment(horizontal="center", vertical="center")

# seed existing sessions (deduplicated)
log = HOME / "progress.csv"
if log.exists():
    seeded = {}
    with log.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                d = as_date((row.get("date") or "").strip())
                minutes = int(float((row.get("minutes") or "0").strip() or 0))
            except (ValueError, TypeError):
                continue
            note = row.get("note") or ""
            key = (d, minutes, note.strip())
            topic = (row.get("topic") or "").strip()
            lesson = (row.get("lesson") or "").strip().upper()
            score = (row.get("score") or "").strip()
            existing = seeded.get(key)
            if existing and (existing[1] or existing[2]):
                continue
            if topic.lower() == "english" or note.lower().startswith("english"):
                typ = "English"
                lesson = ""
            elif score:
                typ = "Practice"
            else:
                typ = "Learn"
            seeded[key] = (d, lesson, note, typ, minutes, score)
    for r, (d, lesson, note, typ, minutes, score) in enumerate(seeded.values(), start=2):
        sess.cell(row=r, column=1, value=d)
        sess.cell(row=r, column=2, value=lesson or None)
        sess.cell(row=r, column=4, value=typ)
        sess.cell(row=r, column=5, value=minutes)
        if score:
            try:
                sess.cell(row=r, column=6, value=float(score))
            except ValueError:
                pass
        sess.cell(row=r, column=7, value=note)

# validation
dv_mod = DataValidation(type="list", formula1="=Modules!$A$2:$A$103", allow_blank=True,
                        showErrorMessage=True, errorTitle="Unknown module",
                        error="Pick one of the LM ids from the Modules sheet.")
dv_type = DataValidation(type="list", formula1="=Setup!$D$17:$D$21", allow_blank=True)
dv_min = DataValidation(type="whole", operator="between", formula1="1", formula2="600", allow_blank=True)
dv_score = DataValidation(type="decimal", operator="between", formula1="0", formula2="100", allow_blank=True)
dv_date = DataValidation(type="date", operator="between", formula1="DATE(2020,1,1)", formula2="DATE(2030,12,31)", allow_blank=True)
for dv in (dv_mod, dv_type, dv_min, dv_score, dv_date):
    sess.add_data_validation(dv)
dv_mod.add(f"B2:B{SESS_LAST}")
dv_type.add(f"D2:D{SESS_LAST}")
dv_min.add(f"E2:E{SESS_LAST}")
dv_score.add(f"F2:F{SESS_LAST}")
dv_date.add(f"A2:A{SESS_LAST}")

sess.conditional_formatting.add(f"A2:J{SESS_LAST}",
    FormulaRule(formula=['AND($A2<>"",$D2<>"English",$D2<>"Mock",$B2="")'], fill=fill(RED_LIGHT), stopIfTrue=False))
sess.conditional_formatting.add(f"J2:J{SESS_LAST}",
    CellIsRule(operator="equal", formula=['"Pick a module"'], fill=fill(RED_LIGHT), font=Font(color=RED, bold=True)))

# ================================================================ ERRORS ====
errs.sheet_view.showGridLines = True
e_headers = ["ID", "Date", "Module", "Topic", "What went wrong", "Why / correct rule",
             "Status", "Closed", "Age (d)", "Check"]
for i, h in enumerate(e_headers, start=1):
    errs.cell(row=1, column=i, value=h)
header_row(errs, 1, len(e_headers))
errs.freeze_panes = "A2"
errs.auto_filter.ref = f"A1:J{ERR_LAST}"
widths(errs, {"A": 6, "B": 12, "C": 8, "D": 24, "E": 46, "F": 52, "G": 9, "H": 12, "I": 8, "J": 16})

for r in range(2, ERR_LAST + 1):
    errs.cell(row=r, column=1, value=f'=IF($B{r}="","",ROW()-1)')
    errs.cell(row=r, column=4, value=f'=IF($C{r}="","",IFERROR(INDEX(Modules!$B$2:$B$103,MATCH($C{r},Modules!$A$2:$A$103,0)),""))')
    errs.cell(row=r, column=9, value=f'=IF(AND($B{r}<>"",$G{r}="Open"),TODAY()-$B{r},"")')
    errs.cell(row=r, column=10, value=f'=IF(AND($G{r}="Closed",$H{r}=""),"Add close date","")')
    for col in range(1, 11):
        cell = errs.cell(row=r, column=col)
        data_cell(cell, editable=(col in (2, 3, 5, 6, 7, 8)), wrap=(col in (5, 6)))
    errs.cell(row=r, column=2).number_format = "yyyy-mm-dd"
    errs.cell(row=r, column=8).number_format = "yyyy-mm-dd"
    errs.cell(row=r, column=3).alignment = Alignment(horizontal="center", vertical="center")
    errs.cell(row=r, column=7).alignment = Alignment(horizontal="center", vertical="center")
    errs.row_dimensions[r].height = 30

if (HOME / "errors.csv").exists():
    with (HOME / "errors.csv").open(newline="", encoding="utf-8") as f:
        for r, row in enumerate(csv.DictReader(f), start=2):
            if r > ERR_LAST:
                break
            errs.cell(row=r, column=2, value=as_date(row["date"]) if row.get("date") else None)
            errs.cell(row=r, column=3, value=row.get("lesson") or None)
            errs.cell(row=r, column=5, value=row.get("note"))
            errs.cell(row=r, column=6, value=row.get("why"))
            errs.cell(row=r, column=7, value=row.get("status") or "Open")
            errs.cell(row=r, column=8, value=as_date(row["closed"]) if row.get("closed") else None)

dv_emod = DataValidation(type="list", formula1="=Modules!$A$2:$A$103", allow_blank=True)
dv_estatus = DataValidation(type="list", formula1="=Setup!$D$25:$D$26", allow_blank=True)
errs.add_data_validation(dv_emod)
errs.add_data_validation(dv_estatus)
dv_emod.add(f"C2:C{ERR_LAST}")
dv_estatus.add(f"G2:G{ERR_LAST}")

errs.conditional_formatting.add(f"A2:J{ERR_LAST}",
    FormulaRule(formula=['$G2="Open"'], fill=fill(RED_LIGHT)))
errs.conditional_formatting.add(f"A2:J{ERR_LAST}",
    FormulaRule(formula=['$G2="Closed"'], font=Font(color=GREY), fill=fill(LIGHT)))
errs.conditional_formatting.add(f"J2:J{ERR_LAST}",
    CellIsRule(operator="equal", formula=['"Add close date"'], fill=fill(AMBER_LIGHT), font=Font(color=AMBER)))

# ================================================================= MOCKS ====
mocks.sheet_view.showGridLines = True
m_headers = ["Date", "Score", "Target", "Delta", "Running avg", "Note", "Status"]
for i, h in enumerate(m_headers, start=1):
    mocks.cell(row=1, column=i, value=h)
header_row(mocks, 1, len(m_headers))
mocks.freeze_panes = "A2"
mocks.auto_filter.ref = f"A1:G{MOCK_LAST}"
widths(mocks, {"A": 12, "B": 9, "C": 9, "D": 9, "E": 12, "F": 56, "G": 12})
for r in range(2, MOCK_LAST + 1):
    mocks.cell(row=r, column=3, value="=Setup!$B$7")
    mocks.cell(row=r, column=4, value=f'=IF($B{r}="","",$B{r}-$C{r})')
    mocks.cell(row=r, column=5, value=f'=IF($B{r}="","",AVERAGE($B$2:$B{r}))')
    mocks.cell(row=r, column=7, value=f'=IF($B{r}="","",IF($B{r}>=Setup!$B$7,"On target","Below"))')
    for col in range(1, 8):
        cell = mocks.cell(row=r, column=col)
        data_cell(cell, editable=(col in (1, 2, 6)))
    mocks.cell(row=r, column=1).number_format = "yyyy-mm-dd"
    for col in (2, 3, 4, 5):
        mocks.cell(row=r, column=col).number_format = "0.0"
    mocks.cell(row=r, column=7).alignment = Alignment(horizontal="center", vertical="center")

if (HOME / "mocks.csv").exists():
    with (HOME / "mocks.csv").open(newline="", encoding="utf-8") as f:
        for r, row in enumerate(csv.DictReader(f), start=2):
            if r > MOCK_LAST:
                break
            mocks.cell(row=r, column=1, value=as_date(row["date"]) if row.get("date") else None)
            try:
                mocks.cell(row=r, column=2, value=float(row.get("score") or 0))
            except ValueError:
                pass
            mocks.cell(row=r, column=6, value=row.get("note"))

dv_mscore = DataValidation(type="decimal", operator="between", formula1="0", formula2="100", allow_blank=True)
mocks.add_data_validation(dv_mscore)
dv_mscore.add(f"B2:B{MOCK_LAST}")
mocks.conditional_formatting.add(f"A2:G{MOCK_LAST}",
    FormulaRule(formula=['AND($B2<>"",$B2<Setup!$B$7)'], fill=fill(RED_LIGHT), font=Font(color=RED)))
mocks.conditional_formatting.add(f"A2:G{MOCK_LAST}",
    FormulaRule(formula=['AND($B2<>"",$B2>=Setup!$B$7)'], fill=fill(GREEN_LIGHT), font=Font(color=GREEN)))

chart = LineChart()
chart.title = "Mock scores vs target"
chart.style = 12
chart.y_axis.title = "Score"
chart.y_axis.scaling.min = 40
chart.y_axis.scaling.max = 100
data = Reference(mocks, min_col=2, max_col=3, min_row=1, max_row=30)
chart.add_data(data, titles_from_data=True)
chart.set_categories(Reference(mocks, min_col=1, min_row=2, max_row=30))
chart.height = 8
chart.width = 16
mocks.add_chart(chart, "I2")

# ================================================================== PLAN ====
plan.sheet_view.showGridLines = True
p_headers = ["Block", "Phase", "Start", "End", "Modules", "Planned CFA h", "h/week",
             "Actual h", "Delta", "%", "Status", "Days left", "Exit criterion"]
for i, h in enumerate(p_headers, start=1):
    plan.cell(row=1, column=i, value=h)
header_row(plan, 1, len(p_headers), 30)
plan.freeze_panes = "A2"
plan.auto_filter.ref = f"A1:M{PLAN_LAST}"
widths(plan, {"A": 12, "B": 24, "C": 12, "D": 12, "E": 9, "F": 13, "G": 9, "H": 10,
              "I": 9, "J": 8, "K": 11, "L": 8, "M": 62})
for r, b in enumerate(curriculum, start=2):
    values = [b["id"], b["phase"], as_date(b["start"]), as_date(b["end"]), len(b.get("lessons", [])),
              b.get("planned_cfa_hours", 0), b.get("hours_per_week", 0),
              f'=SUMIFS(Sessions!$E$2:$E${SESS_LAST},Sessions!$A$2:$A${SESS_LAST},">="&$C{r},Sessions!$A$2:$A${SESS_LAST},"<="&$D{r},Sessions!$D$2:$D${SESS_LAST},"<>English")/60',
              f'=IF($F{r}=0,0,$H{r}-$F{r})',
              f'=IF($F{r}=0,0,$H{r}/$F{r})',
              f'=IF($F{r}=0,"",IF($H{r}>=$F{r}*0.95,"Complete",IF(TODAY()>$D{r},"Overdue",IF(TODAY()>=$C{r},"Active","Upcoming"))))',
              f'=IF(TODAY()>$D{r},0,$D{r}-TODAY())',
              b["deliverable"]]
    for i, v in enumerate(values, start=1):
        cell = plan.cell(row=r, column=i, value=v)
        data_cell(cell, wrap=(i == 13))
    plan.cell(row=r, column=3).number_format = "yyyy-mm-dd"
    plan.cell(row=r, column=4).number_format = "yyyy-mm-dd"
    for i in (6, 7, 8, 9):
        plan.cell(row=r, column=i).number_format = "0.0"
    plan.cell(row=r, column=9).number_format = "+0.0;-0.0;0.0"
    plan.cell(row=r, column=10).number_format = "0%"
    plan.row_dimensions[r].height = 30

plan.conditional_formatting.add(f"K2:K{PLAN_LAST}",
    CellIsRule(operator="equal", formula=['"Active"'], fill=fill(GOLD_LIGHT), font=Font(color=GOLD, bold=True)))
plan.conditional_formatting.add(f"K2:K{PLAN_LAST}",
    CellIsRule(operator="equal", formula=['"Complete"'], fill=fill(GREEN_LIGHT), font=Font(color=GREEN)))
plan.conditional_formatting.add(f"K2:K{PLAN_LAST}",
    CellIsRule(operator="equal", formula=['"Overdue"'], fill=fill(RED_LIGHT), font=Font(color=RED, bold=True)))

# key dates below the plan
section(plan, 20, 7, "KEY DATES  ·  DEADLINES, MOCKS, CHECKPOINTS")
k_headers = ["Date", "Type", "Event", "", "", "Days left", "Status"]
for i, h in enumerate(k_headers, start=1):
    plan.cell(row=21, column=i, value=h)
header_row(plan, 21, 7, 22)
plan.merge_cells("C21:E21")
for r, (d, kind, label) in enumerate(key_dates, start=KEY_FIRST):
    plan.cell(row=r, column=1, value=d)
    plan.cell(row=r, column=2, value=kind)
    plan.merge_cells(start_row=r, start_column=3, end_row=r, end_column=5)
    plan.cell(row=r, column=3, value=label)
    plan.cell(row=r, column=6, value=f'=IF($A{r}>=TODAY(),$A{r}-TODAY(),"")')
    plan.cell(row=r, column=7, value=f'=IF($A{r}<TODAY(),"passed",IF($A{r}-TODAY()<=30,"soon","upcoming"))')
    for col in (1, 2, 3, 6, 7):
        data_cell(plan.cell(row=r, column=col), wrap=(col == 3))
    plan.cell(row=r, column=1).number_format = "yyyy-mm-dd"
    plan.cell(row=r, column=6).number_format = "0"
    plan.row_dimensions[r].height = 24
plan.conditional_formatting.add(f"G{KEY_FIRST}:G{KEY_LAST}",
    CellIsRule(operator="equal", formula=['"soon"'], fill=fill(AMBER_LIGHT), font=Font(color=AMBER, bold=True)))
plan.conditional_formatting.add(f"G{KEY_FIRST}:G{KEY_LAST}",
    CellIsRule(operator="equal", formula=['"passed"'], font=Font(color=GREY), fill=fill(LIGHT)))

# ============================================================== DASHBOARD ===
dash.sheet_view.showGridLines = False
dash.sheet_view.zoomScale = 90
widths(dash, {"A": 20, "B": 15, "C": 15, "D": 15, "E": 15, "F": 15, "G": 15, "H": 34})

dash.merge_cells("A1:H1")
c = dash["A1"]
c.value = "YIRVIEL CAPITAL  ·  CFA LEVEL I"
c.font = Font(name=MONO, size=18, bold=True, color=GOLD)
c.fill = fill(NAVY)
c.alignment = Alignment(vertical="center", indent=1)
dash.row_dimensions[1].height = 42

dash.merge_cells("A2:H2")
dash["A2"] = "Operating dashboard  ·  2027 curriculum, 102 modules  ·  every figure is live from the sheets"
dash["A2"].font = Font(name=FONT, size=9, italic=True, color=GREY)
dash["A2"].alignment = Alignment(vertical="center", indent=1)

section(dash, 4, 8, "POSITION")

kpi = [
    (5, "A", "DAYS TO EXAM", "=Setup!$B$5", "0"),
    (5, "C", "EXAM DATE", "=Setup!$B$4", "yyyy-mm-dd"),
    (5, "E", "READINESS", '=IFERROR((D6*100*0.4+IF(F6="",0,F6*0.35)+IF(H6="",0,H6*0.25))/(0.4+IF(F6="",0,0.35)+IF(H6="",0,0.25)),0)', "0"),
    (5, "G", "NEXT DEADLINE", '=IF(B11="","no deadline set",C11&"  |  "&(B11-TODAY())&"d")', None),
    (6, "A", "LESSON HOURS", "=SUM(Modules!$H$2:$H$103)", "0.0"),
    (6, "C", "COVERAGE", "=IFERROR(B6/SUM(Modules!$G$2:$G$103),0)", "0%"),
    (6, "E", "ACCURACY", '=IFERROR(AVERAGE(Sessions!$F$2:$F$1501),"")', "0.0"),
    (6, "G", "MOCK AVERAGE", '=IFERROR(AVERAGE(Mocks!$B$2:$B$101),"")', "0.0"),
    (7, "A", "DUE REVIEWS", '=COUNTIF(Modules!$N$2:$N$103,"DUE")', "0"),
    (7, "C", "OPEN ERRORS", '=COUNTIF(Errors!$G$2:$G$301,"Open")', "0"),
    (7, "E", "ENGLISH HOURS", '=SUMIFS(Sessions!$E$2:$E$1501,Sessions!$D$2:$D$1501,"English")/60', "0.0"),
    (7, "G", "SESSIONS LOGGED", "=COUNTA(Sessions!$A$2:$A$1501)", "0"),
]
for row, col, label, formula, fmt in kpi:
    lc = dash[f"{col}{row}"]
    lc.value = label
    lc.font = Font(name=MONO, size=7.5, bold=True, color=GREY)
    lc.alignment = Alignment(vertical="bottom")
    vc = dash.cell(row=row, column=ord(col) - 64 + 1, value=formula)
    vc.font = Font(name=FONT, size=18, bold=True, color=NAVY)
    vc.fill = fill(LIGHT)
    vc.border = box
    vc.alignment = Alignment(vertical="center", horizontal="left", indent=1)
    if fmt:
        vc.number_format = fmt

dash.conditional_formatting.add("B5:B5", DataBarRule(start_type="num", start_value=0, end_type="num", end_value=500, color=GOLD, showValue=True))
dash.conditional_formatting.add("F5:F5", DataBarRule(start_type="num", start_value=0, end_type="num", end_value=100, color="63BE7B", showValue=True))
dash.conditional_formatting.add("D6:D6", DataBarRule(start_type="num", start_value=0, end_type="num", end_value=1, color="63BE7B", showValue=True))
dash.conditional_formatting.add("B7:B7", CellIsRule(operator="greaterThan", formula=["0"], fill=fill(RED_LIGHT), font=Font(color=RED, bold=True)))
dash.conditional_formatting.add("D7:D7", CellIsRule(operator="greaterThan", formula=["0"], fill=fill(RED_LIGHT), font=Font(color=RED, bold=True)))
dash["H5"].font = Font(name=FONT, size=10, bold=True, color=NAVY)
dash["H5"].alignment = Alignment(vertical="center", wrap_text=True, indent=1)
dash["D5"].font = Font(name=FONT, size=12, bold=True, color=NAVY)
dash["D5"].number_format = "dd mmm yyyy"
dash.row_dimensions[5].height = 34

section(dash, 9, 8, "THIS WEEK  /  NEXT UP")

def label_value(row, col, label, formula, fmt=None, editable=False):
    lc = dash[f"{col}{row}"]
    lc.value = label
    lc.font = Font(name=MONO, size=7.5, bold=True, color=GREY)
    lc.alignment = Alignment(vertical="bottom")
    vc = dash.cell(row=row, column=ord(col) - 64 + 1, value=formula)
    data_cell(vc, fmt=fmt, editable=editable, bold=True)
    vc.font = Font(name=FONT, size=11, bold=True, color=NAVY)
    vc.fill = fill(LIGHT)
    return vc

label_value(10, "A", "WEEK STARTING", "=TODAY()-WEEKDAY(TODAY(),3)", "yyyy-mm-dd")
label_value(10, "C", "TARGET H", '=IFERROR(INDEX(Plan!$G$2:$G$18,MATCH("Active",Plan!$K$2:$K$18,0)),Setup!$B$10)', "0.0")
label_value(10, "E", "LOGGED H", '=SUMIFS(Sessions!$E$2:$E$1501,Sessions!$A$2:$A$1501,">="&$B10,Sessions!$A$2:$A$1501,"<="&($B10+6),Sessions!$D$2:$D$1501,"<>English")/60', "0.0")
label_value(10, "G", "DELTA", '=IF($D10=0,"",$F10-$D10)', "+0.0;-0.0;0.0")

label_value(11, "A", "NEXT DEADLINE", '=IFERROR(IF(COUNTIFS(Plan!$B$22:$B$60,"Deadline",Plan!$A$22:$A$60,">="&TODAY())=0,"",AGGREGATE(15,6,Plan!$A$22:$A$60/((Plan!$B$22:$B$60="Deadline")*(Plan!$A$22:$A$60>=TODAY())),1)),"")', "yyyy-mm-dd")
dash.merge_cells("C11:F11")
dash["C11"] = '=IF($B11="","",IFERROR(INDEX(Plan!$C$22:$C$60,MATCH($B11,Plan!$A$22:$A$60,0)),""))'
dash["C11"].font = Font(name=FONT, size=10, color=NAVY)
dash["C11"].alignment = Alignment(vertical="center", indent=1)
dash["G11"] = "IN"
dash["G11"].font = Font(name=MONO, size=7.5, bold=True, color=GREY)
dash["H11"] = '=IF($B11="","",$B11-TODAY())'
dash["H11"].font = Font(name=FONT, size=11, bold=True, color=NAVY)
dash["H11"].alignment = Alignment(horizontal="center")

label_value(12, "A", "NEXT MOCK", '=IFERROR(IF(COUNTIFS(Plan!$B$22:$B$60,"Mock",Plan!$A$22:$A$60,">="&TODAY())=0,"",AGGREGATE(15,6,Plan!$A$22:$A$60/((Plan!$B$22:$B$60="Mock")*(Plan!$A$22:$A$60>=TODAY())),1)),"")', "yyyy-mm-dd")
dash.merge_cells("C12:F12")
dash["C12"] = '=IF($B12="","",IFERROR(INDEX(Plan!$C$22:$C$60,MATCH($B12,Plan!$A$22:$A$60,0)),""))'
dash["C12"].font = Font(name=FONT, size=10, color=NAVY)
dash["C12"].alignment = Alignment(vertical="center", indent=1)
dash["G12"] = "IN"
dash["G12"].font = Font(name=MONO, size=7.5, bold=True, color=GREY)
dash["H12"] = '=IF($B12="","",$B12-TODAY())'
dash["H12"].font = Font(name=FONT, size=11, bold=True, color=NAVY)
dash["H12"].alignment = Alignment(horizontal="center")

section(dash, 14, 8, "BY TOPIC")
t_headers = ["Topic", "Weight", "Budget h", "Logged h", "Coverage", "Accuracy", "Done", "Modules"]
for i, h in enumerate(t_headers, start=1):
    dash.cell(row=15, column=i, value=h)
header_row(dash, 15, 8, 22)
for i in range(10):
    r = 16 + i
    dash.cell(row=r, column=1, value=f"=Setup!$D${5 + i}")
    dash.cell(row=r, column=2, value=f"=Setup!$E${5 + i}")
    dash.cell(row=r, column=3, value=f"=SUMIF(Modules!$B$2:$B$103,$A{r},Modules!$G$2:$G$103)")
    dash.cell(row=r, column=4, value=f"=SUMIF(Modules!$B$2:$B$103,$A{r},Modules!$H$2:$H$103)")
    dash.cell(row=r, column=5, value=f"=IF($C{r}=0,0,$D{r}/$C{r})")
    dash.cell(row=r, column=6, value=f'=IFERROR(AVERAGEIFS(Sessions!$F$2:$F${SESS_LAST},Sessions!$C$2:$C${SESS_LAST},$A{r}),"")')
    dash.cell(row=r, column=7, value=f'=COUNTIFS(Modules!$B$2:$B$103,$A{r},Modules!$K$2:$K$103,"Done")')
    dash.cell(row=r, column=8, value=f"=COUNTIF(Modules!$B$2:$B$103,$A{r})")
    for col in range(1, 9):
        data_cell(dash.cell(row=r, column=col))
    dash.cell(row=r, column=2).number_format = '0.0"%"'
    for col in (3, 4):
        dash.cell(row=r, column=col).number_format = "0.0"
    dash.cell(row=r, column=5).number_format = "0%"
    dash.cell(row=r, column=6).number_format = "0.0"

dash.cell(row=26, column=1, value="TOTAL").font = Font(name=FONT, size=10, bold=True)
for col in range(1, 9):
    dash.cell(row=26, column=col).border = box
    dash.cell(row=26, column=col).fill = fill(LIGHT)
dash.cell(row=26, column=3, value="=SUM(C16:C25)")
dash.cell(row=26, column=4, value="=SUM(D16:D25)")
dash.cell(row=26, column=5, value="=IF(C26=0,0,D26/C26)")
dash.cell(row=26, column=6, value='=IFERROR(AVERAGE(Sessions!F2:F1501),"")')
dash.cell(row=26, column=7, value="=SUM(G16:G25)")
dash.cell(row=26, column=8, value="=SUM(H16:H25)")
for col in (3, 4):
    dash.cell(row=26, column=col).number_format = "0.0"
    dash.cell(row=26, column=col).font = Font(name=FONT, size=10, bold=True)
dash.cell(row=26, column=5).number_format = "0%"
dash.cell(row=26, column=5).font = Font(name=FONT, size=10, bold=True)
dash.cell(row=26, column=6).number_format = "0.0"
dash.cell(row=26, column=6).font = Font(name=FONT, size=10, bold=True)
dash.cell(row=26, column=7).font = Font(name=FONT, size=10, bold=True)
dash.cell(row=26, column=8).font = Font(name=FONT, size=10, bold=True)

dash.conditional_formatting.add("E16:E25",
    DataBarRule(start_type="num", start_value=0, end_type="num", end_value=1, color="63BE7B", showValue=True))
dash.conditional_formatting.add("F16:F25",
    FormulaRule(formula=['AND($F16<>"",$F16<60)'], fill=fill(RED_LIGHT), font=Font(color=RED, bold=True)))
dash.conditional_formatting.add("F16:F25",
    FormulaRule(formula=['AND($F16<>"",$F16>=70)'], fill=fill(GREEN_LIGHT), font=Font(color=GREEN, bold=True)))

section(dash, 28, 8, "NEXT BEST ACTION")
dash.merge_cells("A29:H29")
dash["A29"] = ('=IF(B7>0,"Clear the spaced-review queue: "&B7&" module(s) due. Open Modules and filter Due = DUE.",'
               'IF(D7>0,"Close "&D7&" error-log item(s): read the why-line, redo the question, then set Status = Closed.",'
               'IF(OR(F6="",F6<Setup!$B$9),"Log scored question sets until accuracy is visible and above "&Setup!$B$9&"%.",'
               'IF(H6="","Sit Mock 1 and log the score on the Mocks sheet.",'
               'IF(F5<Setup!$B$8,"Readiness is below target: add timed sets on the two weakest topics.",'
               '"On plan. Execute the current week and protect the review queue.")))))')
dash["A29"].font = Font(name=FONT, size=12, bold=True, color=NAVY)
dash["A29"].fill = fill(GOLD_LIGHT)
dash["A29"].alignment = Alignment(vertical="center", wrap_text=True, indent=1)
dash["A29"].border = box
dash.row_dimensions[29].height = 38

chart2 = BarChart()
chart2.type = "col"
chart2.style = 10
chart2.title = "Budget vs logged hours by topic"
chart2.y_axis.title = "Hours"
chart2.height = 9.5
chart2.width = 17
data = Reference(dash, min_col=3, max_col=4, min_row=15, max_row=25)
chart2.add_data(data, titles_from_data=True)
chart2.set_categories(Reference(dash, min_col=1, min_row=16, max_row=25))
dash.add_chart(chart2, "J14")

# ============================================================== FINISH ======
for ws in (dash, setup):
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1
    ws.sheet_properties.pageSetUpPr = PageSetupProperties(fitToPage=True)

wb.save(OUT)
print(f"Written {OUT}")

# Excel caches an empty value for a couple of TODAY()-dependent formulas. Force a
# real calculation on Windows so the file opens with visible values everywhere.
if os.name == "nt":
    finalize = HOME / "finalize_workbook.ps1"
    if finalize.exists():
        print("Finalizing with Excel...")
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                        "-File", str(finalize)], check=False)

print(f"  sheets: {wb.sheetnames}")
print(f"  modules: {len(lesson_rows)}, phases: {len(curriculum)}, key dates: {len(key_dates)}")
print(f"  sessions seeded from log, formulas over {SESS_LAST - 1} rows")
