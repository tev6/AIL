"""ail doctor — sanity-check an AIL project and report what's wrong.

Field test 2026-04-29: Arche project hit infinite "Input cannot be
empty" loop because (a) scaffold app.ail rejected empty input,
(b) schedule.json fired forever against it, (c) deploy was
unreachable because no .ail file had an evolve block. Each piece on
its own was a small bug; together they were a 2-hour debugging
session.

`ail doctor` is the *5-second* version of that diagnosis. Read the
project root, run a fixed checklist, print findings sorted by
severity. Every finding has a `hint` line — the user always knows
the next concrete action.

Telos 2026-04-29 — Arche directive for the "next round" of post-Arche
field test fixes.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


SEVERITY_RANK = {"error": 0, "warning": 1, "info": 2}


@dataclass
class Finding:
    severity: str          # "error" | "warning" | "info"
    code: str              # short stable identifier (for tests / scripts)
    message: str           # one-line plain-Korean message
    hint: str              # one-line concrete next action

    def __lt__(self, other: "Finding") -> bool:
        return (
            SEVERITY_RANK[self.severity], self.code
        ) < (
            SEVERITY_RANK[other.severity], other.code
        )


@dataclass
class DoctorReport:
    project_root: Path
    findings: list[Finding] = field(default_factory=list)

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "error"]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "warning"]

    @property
    def infos(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "info"]


# ---------- individual checks ----------

_SCAFFOLD_MARKERS = (
    'return error("Input cannot be empty")',
    'A short paragraph describing what this service should do',
)


def _list_ail_files(root: Path) -> list[Path]:
    try:
        return sorted(
            p for p in root.iterdir()
            if p.is_file() and p.suffix == ".ail"
        )
    except OSError:
        return []


def _check_scaffold_leftovers(root: Path) -> list[Finding]:
    out: list[Finding] = []
    app_ail = root / "app.ail"
    if app_ail.is_file():
        try:
            text = app_ail.read_text(encoding="utf-8")
        except OSError:
            text = ""
        for marker in _SCAFFOLD_MARKERS:
            if marker in text:
                out.append(Finding(
                    severity="warning",
                    code="scaffold_app_ail",
                    message=(
                        "app.ail이 `ail init` scaffold의 거부 함수를 "
                        "그대로 가지고 있어요. 빈 입력을 받으면 에러를 "
                        "내고, scheduler/run이 호출하면 무한 에러 루프로 "
                        "이어질 수 있어요."
                    ),
                    hint=(
                        "다른 .ail 파일이 진짜 프로그램이라면 app.ail은 "
                        "삭제하거나 `entry main(input: Text) "
                        "{{ return ok(input) }}`로 대체하세요."
                    ),
                ))
                break

    intent_md = root / "INTENT.md"
    if intent_md.is_file():
        try:
            text = intent_md.read_text(encoding="utf-8")
        except OSError:
            text = ""
        if "A short paragraph describing what this service should do" in text:
            out.append(Finding(
                severity="info",
                code="scaffold_intent_preamble",
                message=(
                    "INTENT.md preamble이 아직 scaffold 그대로예요. "
                    "비워두면 chat의 자연어 메시지만으로 모델이 작업해요."
                ),
                hint=(
                    "INTENT.md의 첫 문단을 본인 프로젝트 설명 한 줄로 "
                    "바꾸거나, 그대로 비워두면 chat 메시지만 컨텍스트로 "
                    "사용됩니다."
                ),
            ))
    return out


def _check_evolve_and_listen(root: Path) -> list[Finding]:
    """If the user expects deploy but no .ail has an evolve block."""
    out: list[Finding] = []
    files = _list_ail_files(root)
    has_evolve = False
    has_listen = False
    for p in files:
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:
            continue
        if re.search(r"\bevolve\s+\w+\s*\{", text):
            has_evolve = True
        if re.search(r"\blisten\s*:", text):
            has_listen = True

    from .bundle import detect_lifecycle_files
    scattered = detect_lifecycle_files(root)
    if scattered and not has_evolve:
        out.append(Finding(
            severity="warning",
            code="scattered_lifecycle_no_evolve",
            message=(
                f"라이프사이클 파일 {len(scattered)}개가 흩어져 있고 "
                "어디에도 `evolve` 블록이 없어요. 이 상태로는 배포가 "
                "안 됩니다."
            ),
            hint=(
                "chat에서 [🔧 지금 합치기] 카드를 누르거나 터미널에서 "
                "`ail bundle " + " ".join(p.name for p in scattered)
                + "`을 실행해 한 파일로 합치세요."
            ),
        ))
    elif has_evolve and not has_listen:
        out.append(Finding(
            severity="info",
            code="evolve_without_listen",
            message=(
                "evolve 블록은 있는데 `listen:` 포트가 선언되지 않았어요. "
                "evolve-server 모드로 배포하려면 포트가 필요해요."
            ),
            hint="evolve 블록 안에 `listen: 8090` 한 줄 추가하세요.",
        ))
    return out


def _check_schedule_orphan(root: Path) -> list[Finding]:
    """schedule.json present but no .ail registers it via schedule.every,
    OR schedule is paused (auto-throttle fired)."""
    out: list[Finding] = []
    sched_path = root / ".ail" / "schedule.json"
    if not sched_path.is_file():
        return out
    try:
        payload = json.loads(sched_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return out
    if not isinstance(payload, dict):
        return out

    if payload.get("paused"):
        reason = payload.get("paused_reason") or "(원인 정보 없음)"
        n = payload.get("paused_consecutive_failures") or 0
        out.append(Finding(
            severity="warning",
            code="schedule_paused",
            message=(
                f"스케줄러가 self-throttle로 멈춰있어요 ({n}번 연속 실패). "
                f"마지막 에러: {str(reason)[:140]}"
            ),
            hint=(
                "chat의 노란 카드 [▶ 다시 켜기] 또는 "
                "`POST /authoring-schedule/resume` 호출로 재가동하세요. "
                "원인 먼저 고치고 다시 켜는 걸 권장."
            ),
        ))
        return out

    seconds = payload.get("seconds")
    if seconds is None:
        return out

    # Look for `schedule.every` in any .ail. If none, the file is
    # orphaned — created by a deleted program.
    has_register = False
    for p in _list_ail_files(root):
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:
            continue
        if re.search(r"\bschedule\s*\.\s*every\b", text):
            has_register = True
            break
    if not has_register:
        out.append(Finding(
            severity="warning",
            code="orphan_schedule_json",
            message=(
                "`.ail/schedule.json`이 있는데 어떤 .ail 파일도 "
                "`perform schedule.every(...)`를 호출하지 않아요. "
                "옛 프로그램이 남긴 잔재로 보여요."
            ),
            hint=(
                "스케줄을 더 이상 쓰지 않는다면 "
                "`rm .ail/schedule.json`. 다시 쓰려면 어느 .ail 파일에 "
                "`perform schedule.every(N)`을 추가하세요."
            ),
        ))
    return out


def _check_active_program(root: Path) -> list[Finding]:
    out: list[Finding] = []
    marker = root / ".ail" / "active_program"
    if not marker.is_file():
        return out
    try:
        name = marker.read_text(encoding="utf-8").strip()
    except OSError:
        return out
    if not name:
        return out
    target = root / name
    if not target.is_file():
        out.append(Finding(
            severity="warning",
            code="active_program_missing",
            message=(
                f"활성 프로그램 마커가 `{name}`을 가리키는데 파일이 없어요. "
                "옛 emit 결과가 ail bundle로 archive된 뒤 마커가 따라오지 "
                "못한 경우가 흔해요."
            ),
            hint=(
                f"`rm .ail/active_program` 또는 chat 파일 트리에서 "
                "현재 사용 중인 .ail 파일을 클릭해 마커를 갱신하세요."
            ),
        ))
    return out


def _check_parse_status(root: Path) -> list[Finding]:
    out: list[Finding] = []
    try:
        from . import compile_source
    except ImportError:
        return out
    files = _list_ail_files(root)
    for p in files:
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:
            continue
        try:
            compile_source(text)
        except Exception as e:
            out.append(Finding(
                severity="error",
                code="parse_error",
                message=(
                    f"`{p.name}`이 파스되지 않아요: "
                    f"{type(e).__name__}: {str(e)[:140]}"
                ),
                hint=(
                    "chat에서 \"이 파일 고쳐줘\"라고 말하면 자동 수정해요. "
                    "수동으로 고치고 싶다면 spec/08-reference-card.ai.md 참고."
                ),
            ))
    return out


def _check_has_entry_main(root: Path) -> list[Finding]:
    files = _list_ail_files(root)
    if not files:
        return [Finding(
            severity="info",
            code="empty_project",
            message=(
                "프로젝트 폴더에 .ail 파일이 하나도 없어요."
            ),
            hint=(
                "chat에 만들고 싶은 기능을 자연어로 적으면 첫 .ail이 "
                "생성됩니다. 또는 `ail init <name>`으로 새 프로젝트를 "
                "스캐폴드하세요."
            ),
        )]
    has_entry = False
    for p in files:
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:
            continue
        if re.search(r"\bentry\s+main\s*\(", text):
            has_entry = True
            break
    if not has_entry:
        return [Finding(
            severity="error",
            code="no_entry_main",
            message=(
                "어떤 .ail 파일에도 `entry main(...)`이 없어요. "
                "프로그램을 실행할 진입점이 없습니다."
            ),
            hint=(
                "최소 하나의 .ail 파일에 `entry main(input: Text) { ... }`을 "
                "추가하세요. 또는 lifecycle 파일들을 `ail bundle`로 합치면 "
                "synthetic entry main이 자동 부착됩니다."
            ),
        )]
    return []


# ---------- public API ----------

def diagnose(project_root: Path) -> DoctorReport:
    """Run the full checklist against `project_root` and return findings."""
    root = Path(project_root).expanduser().resolve()
    findings: list[Finding] = []
    findings.extend(_check_scaffold_leftovers(root))
    findings.extend(_check_evolve_and_listen(root))
    findings.extend(_check_schedule_orphan(root))
    findings.extend(_check_active_program(root))
    findings.extend(_check_parse_status(root))
    findings.extend(_check_has_entry_main(root))
    findings.sort()
    return DoctorReport(project_root=root, findings=findings)


def render_report(report: DoctorReport) -> str:
    """Format a report as human-readable Korean text for terminals.

    Used by the CLI; the same data structure can be reused by the chat
    UI later (render_html alternative TBD).
    """
    lines: list[str] = []
    lines.append(f"🔍 ail doctor — {report.project_root}")
    lines.append("")
    if not report.findings:
        lines.append("✅ 모든 검사 통과 — 배포 준비 OK.")
        return "\n".join(lines) + "\n"

    icons = {"error": "❌", "warning": "⚠️", "info": "ℹ️"}
    for f in report.findings:
        icon = icons.get(f.severity, "•")
        lines.append(f"{icon} [{f.code}] {f.message}")
        lines.append(f"   → {f.hint}")
        lines.append("")

    summary = (
        f"오류 {len(report.errors)} · 경고 {len(report.warnings)} · "
        f"안내 {len(report.infos)}"
    )
    lines.append(summary)
    return "\n".join(lines) + "\n"
