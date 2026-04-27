"""
home_ui — bare `ail` opens this. A small browser landing page that lets
the user navigate their filesystem, create a new polis (AIL project),
and hand off to the existing authoring chat UI.

Designed for the user vision (msg_1777258038_0 Phase C): no terminal-
typed paths. Click a folder. Click "Create polis". Get an env wizard.
Land in the chat.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from flask import Flask, jsonify, redirect, request


_ENV_GUIDE = [
    {
        "var": "ANTHROPIC_API_KEY",
        "label": "Anthropic API key (Claude)",
        "where": "https://console.anthropic.com/settings/keys",
        "why": "Default authoring + intent backend. Highest-quality AIL author. "
               "Either this OR an OpenAI key OR a local Ollama model is required.",
    },
    {
        "var": "OPENAI_API_KEY",
        "label": "OpenAI API key (GPT-4o etc)",
        "where": "https://platform.openai.com/api-keys",
        "why": "Alternative authoring backend. Used if no Anthropic key set. "
               "Also accepts Azure-OpenAI / OpenRouter via AIL_OPENAI_COMPAT_BASE_URL.",
    },
    {
        "var": "AIL_OLLAMA_MODEL",
        "label": "Ollama model name (offline)",
        "where": "https://ollama.com — install, then `ollama pull qwen2.5-coder:7b-instruct-q4_K_M`",
        "why": "Local fallback. Slower, lower-quality author, but works offline and free.",
    },
    {
        "var": "GOOGLE_API_KEY",
        "label": "Google Custom Search API key (search.web effect)",
        "where": "https://console.cloud.google.com/apis/credentials — enable Custom Search API",
        "why": "Optional. Enables `perform search.web(query)` for any polis that needs web search.",
    },
    {
        "var": "GOOGLE_CSE_ID",
        "label": "Google Custom Search Engine ID",
        "where": "https://programmablesearchengine.google.com/ — create one set to 'search the entire web'",
        "why": "Pairs with GOOGLE_API_KEY. Both required for search.web to work.",
    },
]


def _make_app(start_root: Path):
    app = Flask(__name__)

    @app.route("/")
    def index():
        return _render_index_html(start_root)

    @app.route("/tree")
    def tree():
        path_arg = request.args.get("path", str(start_root))
        try:
            target = Path(path_arg).expanduser().resolve()
        except Exception as e:
            return jsonify({"error": f"bad path: {e}"}), 400
        if not target.is_dir():
            return jsonify({"error": "not a directory"}), 400
        entries = []
        try:
            for child in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
                if child.name.startswith("."):
                    continue
                is_dir = child.is_dir()
                is_polis = is_dir and (child / "INTENT.md").exists()
                entries.append({
                    "name": child.name,
                    "path": str(child),
                    "is_dir": is_dir,
                    "is_polis": is_polis,
                })
        except PermissionError:
            return jsonify({"error": "permission denied"}), 403
        parent = str(target.parent) if target.parent != target else None
        return jsonify({
            "path": str(target),
            "parent": parent,
            "entries": entries,
            "is_polis": (target / "INTENT.md").exists(),
        })

    @app.route("/create-polis", methods=["POST"])
    def create_polis():
        data = request.get_json(silent=True) or {}
        parent = data.get("parent", "").strip()
        name = data.get("name", "").strip()
        port = int(data.get("port") or 0) or _next_chat_port()
        if not parent or not name:
            return jsonify({"error": "parent and name are required"}), 400
        if "/" in name or name in ("", ".", ".."):
            return jsonify({"error": "invalid project name"}), 400
        target_parent = Path(parent).expanduser().resolve()
        if not target_parent.is_dir():
            return jsonify({"error": "parent dir does not exist"}), 400
        new_dir = target_parent / name
        if new_dir.exists():
            # Don't overwrite. Return a structured 409 the UI can hand
            # to the trash-and-retry flow (HEAAL: AIL has no
            # destructive primitive — UI moves to trash with consent).
            return jsonify({
                "error": f"{new_dir} already exists",
                "error_code": "name_exists",
                "existing_path": str(new_dir),
            }), 409
        # Spawn `ail init <name>` from inside parent dir, --no-open so we
        # control the browser hand-off ourselves. Capture output to a
        # log file so we can surface failures (auth missing, port race).
        log_path = _spawn_log_path("init", port)
        try:
            with open(log_path, "wb") as logf:
                proc = subprocess.Popen(
                    [sys.executable, "-m", "ail", "init", name,
                     "--port", str(port), "--no-open"],
                    cwd=str(target_parent),
                    stdout=logf, stderr=subprocess.STDOUT,
                )
            _register_spawned(proc, port, "init")
        except Exception as e:
            return jsonify({"error": f"spawn failed: {type(e).__name__}: {e}"}), 500
        return jsonify({
            "ok": True,
            "path": str(new_dir),
            "chat_url": f"http://127.0.0.1:{port}/",
            "port": port,
            "log_path": str(log_path),
        })

    @app.route("/trash-polis", methods=["POST"])
    def trash_polis():
        """Move a directory to ~/.ail/.Trashcan/<ts>-<name>/ instead of
        deleting it. AIL itself has no destructive primitive (Arche's
        position): the UI offers move-to-trash with explicit user
        consent so a colliding name can be reused without losing prior
        work. The user can manually delete from .Trashcan later.
        """
        data = request.get_json(silent=True) or {}
        path = data.get("path", "").strip()
        confirm = bool(data.get("confirm"))
        if not path:
            return jsonify({"error": "path is required"}), 400
        if not confirm:
            return jsonify({
                "error": "confirm=true required",
                "error_code": "confirm_required",
            }), 400
        target = Path(path).expanduser().resolve()
        if not target.exists():
            return jsonify({"error": "path does not exist"}), 404
        if not target.is_dir():
            return jsonify({"error": "not a directory"}), 400
        # Refuse to trash anything that isn't recognizably a polis or
        # an empty dir — defensive against UI misuse pointing at /Users
        # or similar.
        is_polis = (target / "INTENT.md").exists()
        is_empty = not any(target.iterdir())
        if not (is_polis or is_empty):
            return jsonify({
                "error": "refusing to trash a non-polis non-empty directory "
                         "(no INTENT.md found)",
                "error_code": "not_a_polis",
            }), 400
        # Refuse to trash a path that looks like a system or home root
        # by accident (parent of trash, $HOME exact, /, etc.).
        home = Path.home().resolve()
        if target == home or target == home.parent or str(target) == "/":
            return jsonify({"error": "refusing to trash a root/home path"}), 400
        try:
            trash_dir = home / ".ail" / ".Trashcan"
            trash_dir.mkdir(parents=True, exist_ok=True)
            import time
            stamp = time.strftime("%Y%m%d-%H%M%S")
            trash_target = trash_dir / f"{stamp}-{target.name}"
            # Disambiguate if a same-second trash entry already exists
            counter = 1
            while trash_target.exists():
                trash_target = trash_dir / f"{stamp}-{target.name}-{counter}"
                counter += 1
            target.rename(trash_target)
        except OSError as e:
            return jsonify({
                "error": f"trash move failed: {type(e).__name__}: {e}"
            }), 500
        return jsonify({
            "ok": True,
            "moved_from": str(target),
            "moved_to": str(trash_target),
        })

    @app.route("/open-polis", methods=["POST"])
    def open_polis():
        data = request.get_json(silent=True) or {}
        path = data.get("path", "").strip()
        port = int(data.get("port") or 0) or _next_chat_port()
        target = Path(path).expanduser().resolve()
        if not target.is_dir():
            return jsonify({"error": "not a directory"}), 400
        if not (target / "INTENT.md").exists():
            return jsonify({"error": "not a polis (no INTENT.md)"}), 400
        # `ail edit` launches the authoring chat UI on an existing
        # polis (same surface as `ail init` for new ones). `ail up` was
        # the wrong call here — it serves the deployed app and the user
        # loses the edit surface (field test 2026-04-27).
        log_path = _spawn_log_path("edit", port)
        try:
            with open(log_path, "wb") as logf:
                proc = subprocess.Popen(
                    [sys.executable, "-m", "ail", "edit", str(target),
                     "--port", str(port), "--no-open"],
                    stdout=logf, stderr=subprocess.STDOUT,
                )
            _register_spawned(proc, port, "edit")
        except Exception as e:
            return jsonify({"error": f"spawn failed: {type(e).__name__}: {e}"}), 500
        return jsonify({
            "ok": True,
            "chat_url": f"http://127.0.0.1:{port}/",
            "port": port,
            "log_path": str(log_path),
        })

    @app.route("/check-port")
    def check_port():
        """Probe a localhost port — used by the frontend to wait for a
        spawned `ail up` / `ail init` to become reachable before opening
        the browser tab. Returns {alive: bool}."""
        try:
            probe_port = int(request.args.get("port", "0"))
        except ValueError:
            return jsonify({"error": "bad port"}), 400
        if not (1 <= probe_port <= 65535):
            return jsonify({"error": "port out of range"}), 400
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.5)
        alive = False
        try:
            s.connect(("127.0.0.1", probe_port))
            alive = True
        except OSError:
            alive = False
        finally:
            s.close()
        return jsonify({"alive": alive, "port": probe_port})

    @app.route("/spawn-log")
    def spawn_log():
        """Tail the most recent spawn log so the frontend can surface
        a clear failure message when `ail up` couldn't bind / authenticate."""
        path = request.args.get("path", "").strip()
        try:
            p = Path(path).expanduser().resolve()
        except Exception:
            return jsonify({"error": "bad path"}), 400
        # Defense: only allow paths under our log dir
        log_root = (Path.home() / ".ail" / "logs").resolve()
        try:
            p.relative_to(log_root)
        except ValueError:
            return jsonify({"error": "log path outside ~/.ail/logs"}), 400
        if not p.is_file():
            return jsonify({"tail": "(log not found yet)"}), 200
        try:
            data = p.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            return jsonify({"error": str(e)}), 500
        # Tail to keep response small
        tail = data[-4000:] if len(data) > 4000 else data
        return jsonify({"tail": tail, "size": len(data)})

    @app.route("/admin/stop", methods=["POST"])
    def admin_stop():
        """Terminate the home server itself. Called via sendBeacon when
        the user closes the browser tab — non-developer mental model is
        'closing the browser closes everything'. atexit reaper then
        SIGTERMs spawned children, so no zombies remain."""
        import threading, os as _os, signal as _signal, time as _time
        def _suicide():
            _time.sleep(0.2)
            try:
                _os.kill(_os.getpid(), _signal.SIGTERM)
            except OSError:
                pass
        threading.Thread(target=_suicide, daemon=True).start()
        return jsonify({"ok": True})

    @app.route("/env-status")
    def env_status():
        return jsonify({
            "vars": [
                {**g, "set": bool(os.environ.get(g["var"]))}
                for g in _ENV_GUIDE
            ],
        })

    return app


# Layer B: track spawned children so home shutdown reaps them.
# Non-developer model: closing `ail home` should leave nothing
# orphaned. Each entry: (pid, port, kind). On atexit we send SIGTERM,
# wait briefly, then SIGKILL stragglers.
_SPAWNED: list[dict] = []


def _register_spawned(proc, port: int, kind: str) -> None:
    _SPAWNED.append({"pid": proc.pid, "port": port, "kind": kind})


def _reap_spawned() -> None:
    import os as _os
    import signal as _signal
    import time as _time
    for entry in list(_SPAWNED):
        pid = entry.get("pid")
        if not pid:
            continue
        try:
            _os.kill(pid, _signal.SIGTERM)
        except OSError:
            continue
    # Brief grace, then SIGKILL anything that's still around.
    _time.sleep(0.3)
    for entry in list(_SPAWNED):
        pid = entry.get("pid")
        if not pid:
            continue
        try:
            _os.kill(pid, _signal.SIGKILL)
        except OSError:
            pass


# Install once. Catches both clean exit (Ctrl+C → atexit) and abrupt
# (SIGTERM via shell). Idempotent — atexit hooks run once.
import atexit as _atexit
_atexit.register(_reap_spawned)


def _spawn_log_path(kind: str, port: int) -> Path:
    """Return a fresh log file path for a child `ail up` / `ail init`.
    Lives under ~/.ail/logs/<kind>-<port>-<YYYYMMDD-HHMMSS>.log so the
    frontend can fetch the tail when the child fails silently."""
    import time
    log_dir = Path.home() / ".ail" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    return log_dir / f"{kind}-{port}-{stamp}.log"


def _next_chat_port() -> int:
    """Find a free port for the new chat UI, preferring 8080+."""
    import socket
    for port in range(8080, 8100):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return 0  # let OS pick


def _render_index_html(start_root: Path) -> str:
    return _PAGE.replace("__START_PATH__", str(start_root))


_PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>AIL — your places</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif; background: #fafaf8; color: #222; max-width: 920px; margin: 0 auto; padding: 2rem 1rem; }
header { border-bottom: 2px solid #222; padding-bottom: 1rem; margin-bottom: 2rem; }
h1 { font-size: 1.7rem; letter-spacing: .03em; }
header p { color: #666; font-size: .9rem; margin-top: .3rem; }
.crumbs { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: .9rem; color: #555; padding: .6rem .8rem; background: #fff; border: 1px solid #ddd; margin-bottom: 1rem; word-break: break-all; }
.crumbs button { font-family: inherit; font-size: .85rem; background: none; border: 1px solid #ccc; padding: .15rem .5rem; cursor: pointer; margin-left: .5rem; }
.crumbs button:hover { background: #eee; }
.actions { display: flex; gap: .6rem; margin-bottom: 1rem; flex-wrap: wrap; }
.actions button { font-family: inherit; font-size: .9rem; background: #222; color: #fafaf8; border: 0; padding: .55rem 1rem; cursor: pointer; }
.actions button.secondary { background: #fff; color: #222; border: 1px solid #999; }
.actions button:hover { background: #444; }
.actions button.secondary:hover { background: #eee; }
.actions button.open-here { background: #265c26; }
.actions button.open-here:hover { background: #1a3f1a; }
.tree { border: 1px solid #ddd; background: #fff; max-height: 460px; overflow-y: auto; }
.entry { display: flex; align-items: center; padding: .55rem .8rem; border-bottom: 1px solid #f0f0f0; cursor: pointer; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: .9rem; }
.entry:hover { background: #f6f6f0; }
.entry.dir { color: #222; font-weight: 600; }
.entry.file { color: #888; cursor: default; }
.entry.polis { background: #fff8e1; }
.entry .badge { font-size: .7rem; background: #265c26; color: #fff; padding: .1rem .45rem; margin-left: .5rem; letter-spacing: .04em; border-radius: 2px; }
.entry .icon { width: 1.4rem; }
details.help { margin-top: .8rem; }
details.help summary { cursor: pointer; padding: .5rem .8rem; background: #f0eee0; font-size: .85rem; }
details.help div { padding: 1rem .8rem; background: #fff; border: 1px solid #ddd; border-top: 0; font-size: .85rem; line-height: 1.5; }
.env-row { display: grid; grid-template-columns: 1.2fr auto 2fr; gap: .8rem; padding: .5rem 0; border-bottom: 1px dashed #ddd; align-items: start; }
.env-row .var { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-weight: 600; }
.env-row .pill { font-size: .7rem; padding: .15rem .5rem; border-radius: 2px; align-self: center; }
.env-row .pill.set { background: #265c26; color: #fff; }
.env-row .pill.unset { background: #f0eee0; color: #666; }
.env-row .why { color: #555; font-size: .85rem; }
.env-row a { color: #265c26; }
.modal-bg { position: fixed; inset: 0; background: rgba(0,0,0,.4); display: none; align-items: center; justify-content: center; z-index: 100; }
.modal-bg.show { display: flex; }
.modal { background: #fff; padding: 1.5rem; max-width: 500px; width: 90%; border: 2px solid #222; }
.modal h2 { margin-bottom: 1rem; font-size: 1.2rem; }
.modal label { display: block; font-size: .8rem; color: #555; margin: .8rem 0 .3rem; text-transform: uppercase; letter-spacing: .04em; }
.modal input { width: 100%; padding: .5rem; border: 1px solid #999; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: .95rem; }
.modal .row { display: flex; gap: .6rem; margin-top: 1.2rem; justify-content: flex-end; }
.modal button { font-family: inherit; padding: .55rem 1rem; cursor: pointer; border: 0; }
.modal button.primary { background: #222; color: #fff; }
.modal button.cancel { background: #eee; color: #222; }
.status { margin-top: 1rem; padding: .8rem; font-size: .9rem; display: none; }
.status.show { display: block; }
.status.ok { background: #e8f5e8; color: #265c26; border-left: 3px solid #265c26; }
.status.err { background: #fbe9e9; color: #8a2727; border-left: 3px solid #8a2727; }
footer { margin-top: 3rem; padding-top: 1rem; border-top: 1px solid #ddd; font-size: .8rem; color: #aaa; text-align: center; }
</style>
</head><body>
<header><h1>AIL — your places</h1>
<p>Browse a folder, then create a polis (AIL project) inside it.</p></header>

<div class="crumbs"><span id="cwd">__START_PATH__</span>
<button id="up-btn">↑ parent</button>
<button id="home-btn">⌂ home</button></div>

<div class="actions">
<button id="create-btn">+ Create polis here</button>
<button id="open-btn" class="open-here secondary" style="display:none">→ Open polis here</button>
</div>

<div class="tree" id="tree"></div>

<div class="status" id="status"></div>

<details class="help"><summary>Environment / API keys</summary><div id="env-body">loading…</div></details>

<div class="modal-bg" id="modal-bg"><div class="modal">
<h2>Create polis</h2>
<label>Project name</label>
<input type="text" id="polis-name" placeholder="my-bot" autocomplete="off">
<div class="row">
<button class="cancel" id="cancel-btn">Cancel</button>
<button class="primary" id="confirm-btn">Create &amp; open chat</button>
</div></div></div>

<footer>AIL home · v1.62.0</footer>

<script>
const cwdEl = document.getElementById('cwd');
const treeEl = document.getElementById('tree');
const statusEl = document.getElementById('status');
const openBtn = document.getElementById('open-btn');

function showStatus(kind, msg, asHTML=false) {
  statusEl.className = 'status show ' + kind;
  if (asHTML) statusEl.innerHTML = msg; else statusEl.textContent = msg;
}

// window.open after an await/setTimeout loses the user-gesture token,
// so Chrome/Safari may block it as a popup. Detect (return value null
// or .closed immediately) and fall back to an explicit clickable link
// + a gentle nudge to allow popups for this origin.
function escapeHtml(s) {
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
          .replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}
function openTab(url) {
  let win = null;
  try { win = window.open(url, '_blank'); } catch (e) { win = null; }
  if (!win || win.closed || typeof win.closed === 'undefined') {
    const safe = escapeHtml(url);
    showStatus('err',
      '🛈 브라우저가 새 탭을 막았어요 (popup blocker). ' +
      '주소창 오른쪽 차단 아이콘에서 이 사이트의 팝업을 허용해 주세요.<br><br>' +
      '지금 열기 → <a href="' + safe + '" target="_blank" rel="noopener">' + safe + '</a>',
      true);
    return false;
  }
  return true;
}

async function loadTree(path) {
  const r = await fetch('/tree?path=' + encodeURIComponent(path));
  const j = await r.json();
  if (!r.ok) { showStatus('err', j.error || 'failed to list'); return; }
  cwdEl.textContent = j.path;
  cwdEl.dataset.parent = j.parent || '';
  cwdEl.dataset.isPolis = j.is_polis ? '1' : '';
  openBtn.style.display = j.is_polis ? '' : 'none';
  treeEl.innerHTML = '';
  for (const e of j.entries) {
    const d = document.createElement('div');
    d.className = 'entry ' + (e.is_dir ? 'dir' : 'file') + (e.is_polis ? ' polis' : '');
    d.innerHTML = '<span class="icon">' + (e.is_dir ? '📁' : '📄') + '</span>' +
                  '<span>' + e.name + '</span>' +
                  (e.is_polis ? '<span class="badge">POLIS</span>' : '');
    if (e.is_dir) d.onclick = () => loadTree(e.path);
    treeEl.appendChild(d);
  }
}

document.getElementById('up-btn').onclick = () => {
  const p = cwdEl.dataset.parent;
  if (p) loadTree(p);
};
document.getElementById('home-btn').onclick = () => loadTree('~');

document.getElementById('create-btn').onclick = () => {
  document.getElementById('polis-name').value = '';
  document.getElementById('modal-bg').classList.add('show');
  document.getElementById('polis-name').focus();
};
document.getElementById('cancel-btn').onclick = () => {
  document.getElementById('modal-bg').classList.remove('show');
};
async function doCreatePolis(parent, name) {
  showStatus('ok', 'Spawning new polis…');
  const r = await fetch('/create-polis', {
    method: 'POST', headers: {'Content-Type':'application/json'},
    body: JSON.stringify({parent, name})
  });
  const j = await r.json();
  if (r.ok) {
    showStatus('ok', 'Polis at ' + j.path + ' — opening chat at ' + j.chat_url + ' …');
    setTimeout(() => { openTab(j.chat_url); }, 1500);
    return;
  }
  if (j.error_code === 'name_exists') {
    // Strong consent dialog. AIL has no destructive primitive — UI
    // moves the existing dir to ~/.ail/.Trashcan/<ts>-<name>/ on
    // explicit confirm. User can recover from .Trashcan manually.
    const msg = '⚠ 같은 이름의 폴리스가 이미 있어요:\n\n  ' + j.existing_path +
                '\n\n이 디렉터리를 휴지통(~/.ail/.Trashcan/)으로 옮긴 뒤 새 폴리스를 만들까요?\n' +
                '\n• 삭제가 아니라 *이동*입니다 — 나중에 .Trashcan에서 복원 가능\n' +
                '• AIL은 데이터를 영구 삭제하지 않아요 (HEAAL 원칙)\n' +
                '\n계속하려면 [확인], 취소하려면 [취소]를 누르세요.';
    if (!window.confirm(msg)) {
      showStatus('err', '취소됨 — 기존 폴리스는 그대로 있어요.');
      return;
    }
    showStatus('ok', '휴지통으로 이동 중…');
    const tr = await fetch('/trash-polis', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({path: j.existing_path, confirm: true})
    });
    const tj = await tr.json();
    if (!tr.ok) {
      showStatus('err', '휴지통 이동 실패: ' + (tj.error || tr.status));
      return;
    }
    showStatus('ok', '이동 완료 → ' + tj.moved_to + ' · 새 폴리스 생성 중…');
    // Retry create now that the path is free
    return await doCreatePolis(parent, name);
  }
  showStatus('err', j.error || 'create failed');
}

document.getElementById('confirm-btn').onclick = async () => {
  const name = document.getElementById('polis-name').value.trim();
  if (!name) return;
  document.getElementById('modal-bg').classList.remove('show');
  await doCreatePolis(cwdEl.textContent, name);
};
// Poll the spawned chat server until it accepts a connection, then
// open the tab. Pre-fix opened the tab after a blind 1.5s timer — if
// `ail up` took longer (typical first-run with adapter init), the new
// tab landed on connection-refused. If startup never completes, fetch
// the tail of the spawn log and surface it.
async function waitAndOpen(port, log_path) {
  const start = Date.now();
  const max_ms = 30000;
  let attempt = 0;
  while (Date.now() - start < max_ms) {
    attempt++;
    const elapsed = Math.floor((Date.now() - start) / 1000);
    showStatus('ok', '폴리스 부팅 중… (' + elapsed + 's, 시도 ' + attempt + ')');
    try {
      const r = await fetch('/check-port?port=' + port);
      const j = await r.json();
      if (j.alive) {
        const url = 'http://127.0.0.1:' + port + '/';
        showStatus('ok', '준비됨 → ' + url);
        openTab(url);
        return;
      }
    } catch (e) { /* keep polling */ }
    await new Promise(res => setTimeout(res, 700));
  }
  // Timeout — fetch and show the log tail
  let tail = '(no log)';
  if (log_path) {
    try {
      const lr = await fetch('/spawn-log?path=' + encodeURIComponent(log_path));
      const lj = await lr.json();
      tail = lj.tail || lj.error || '(empty)';
    } catch (e) { tail = '(log fetch failed: ' + e.message + ')'; }
  }
  showStatus('err',
    '30초 안에 폴리스가 안 떴어요. 로그 마지막 부분:\n\n' +
    tail.slice(-2000) +
    '\n\n전체 로그: ' + (log_path || '(없음)'),
    true);
}

openBtn.onclick = async () => {
  showStatus('ok', '`ail up` 띄우는 중 — ' + cwdEl.textContent);
  const r = await fetch('/open-polis', {
    method: 'POST', headers: {'Content-Type':'application/json'},
    body: JSON.stringify({path: cwdEl.textContent})
  });
  const j = await r.json();
  if (!r.ok) { showStatus('err', j.error || 'open failed'); return; }
  await waitAndOpen(j.port, j.log_path);
};

async function loadEnv() {
  const r = await fetch('/env-status');
  const j = await r.json();
  const body = document.getElementById('env-body');
  body.innerHTML = j.vars.map(v => `
    <div class="env-row">
      <div><div class="var">${v.var}</div><div style="font-size:.8rem;color:#666">${v.label}</div></div>
      <div class="pill ${v.set ? 'set' : 'unset'}">${v.set ? 'set' : 'unset'}</div>
      <div class="why">${v.why} <br><a href="${v.where}" target="_blank">→ get key</a></div>
    </div>`).join('');
}

loadTree('__START_PATH__');
loadEnv();

// Non-developer mental model: closing the browser tab should close
// the `ail` command running in the terminal too. sendBeacon survives
// the unload — no response is read but /admin/stop SIGTERMs the
// home process, atexit then reaps spawned children. ?keep=1 disables.
if (!new URLSearchParams(location.search).has('keep')) {
  window.addEventListener('pagehide', () => {
    try {
      navigator.sendBeacon('/admin/stop',
        new Blob([''], {type: 'text/plain'}));
    } catch (e) {}
  });
}
</script>
</body></html>
"""


def serve_home(start_root: Path | None = None,
               port: int = 8079,
               host: str = "127.0.0.1") -> int:
    """Start the home browser. Returns when killed."""
    import logging
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    if start_root is None:
        start_root = Path.home()
    app = _make_app(start_root)
    print(f"[ail home] serving on http://{host}:{port}/", flush=True)
    print(f"[ail home] start dir: {start_root}", flush=True)
    print(f"[ail home] (Ctrl+C to stop)\n", flush=True)
    try:
        app.run(host=host, port=port, debug=False, use_reloader=False)
    except KeyboardInterrupt:
        return 0
    return 0
