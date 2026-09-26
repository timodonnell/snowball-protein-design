#!/usr/bin/env python3
"""Render wire archives as a browsable HTML report of the exact conversations.

The wire archive stays authoritative: this only re-presents it. Message bodies
are copied verbatim from the recorded request and response, never reformatted,
re-indented or truncated, so what the page shows is what crossed the wire.

System prompts repeat across calls and are large, so each distinct one is stored
once per page and injected when a call is expanded; its SHA-256 is printed on
every call that uses it, and identical hashes mean identical bytes.
"""
import argparse
from collections import Counter
from datetime import datetime
import hashlib
import html
import json
from pathlib import Path

TITLES = {"qwen": "Qwen3.6-27B-FP8", "snowball": "Snowball-67B-A2B", "glm": "GLM-5.3"}

CSS = """
:root{--bg:#fbfbfa;--fg:#1c1b1a;--mut:#6b6864;--line:#e3e0db;--card:#fff;
--accent:#315b8a;--ok:#2f7d5d;--warn:#b4571f;--bad:#b23b2e;--code:#f4f2ee}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){
--bg:#16161a;--fg:#e8e6e3;--mut:#9b9793;--line:#2e2e34;--card:#1d1d22;
--accent:#8ab4e8;--ok:#6fc79b;--warn:#e0a065;--bad:#e08a7e;--code:#232329}}
:root[data-theme=dark]{--bg:#16161a;--fg:#e8e6e3;--mut:#9b9793;--line:#2e2e34;
--card:#1d1d22;--accent:#8ab4e8;--ok:#6fc79b;--warn:#e0a065;--bad:#e08a7e;--code:#232329}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
font:15px/1.6 ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
.wrap{max-width:1040px;margin:0 auto;padding:32px 16px 96px}
h1{font-size:1.7rem;line-height:1.25;margin:0 0 4px}
h2{font-size:1.2rem;margin:36px 0 10px;padding-top:14px;border-top:1px solid var(--line)}
h3{font-size:1rem;margin:22px 0 6px}
a{color:var(--accent)}
.sub{color:var(--mut);margin:0 0 20px}
.note{background:var(--card);border:1px solid var(--line);border-left:3px solid var(--accent);
padding:12px 14px;border-radius:6px;margin:16px 0}
table{border-collapse:collapse;width:100%;margin:14px 0;font-size:.9rem;display:block;overflow-x:auto}
th,td{border-bottom:1px solid var(--line);padding:7px 10px;text-align:left;white-space:nowrap}
th{color:var(--mut);font-weight:600}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}
pre{background:var(--code);border:1px solid var(--line);border-radius:6px;padding:12px;
overflow-x:auto;font:12.5px/1.55 ui-monospace,SFMono-Regular,Menlo,monospace;
white-space:pre-wrap;word-break:break-word;max-height:30em;margin:8px 0}
pre.tall{max-height:60em}
code{background:var(--code);padding:1px 5px;border-radius:4px;
font:12.5px ui-monospace,SFMono-Regular,Menlo,monospace}
details{background:var(--card);border:1px solid var(--line);border-radius:8px;
margin:8px 0;padding:0 12px}
details[open]{padding-bottom:10px}
summary{cursor:pointer;padding:9px 0;font-weight:600;font-size:.92rem;list-style:none}
summary::-webkit-details-marker{display:none}
summary:before{content:"▸ ";color:var(--mut)}
details[open]>summary:before{content:"▾ "}
.call{border:1px solid var(--line);border-radius:10px;background:var(--card);
margin:16px 0;padding:14px}
.call>h3{margin-top:0;display:flex;gap:10px;align-items:baseline;flex-wrap:wrap}
.meta{display:flex;flex-wrap:wrap;gap:6px 14px;color:var(--mut);font-size:.82rem;
margin:2px 0 10px;font-variant-numeric:tabular-nums}
.tag{display:inline-block;border:1px solid var(--line);border-radius:999px;
padding:1px 9px;font-size:.75rem;font-weight:600;color:var(--mut);white-space:nowrap}
.tag.ok{color:var(--ok);border-color:var(--ok)}
.tag.warn{color:var(--warn);border-color:var(--warn)}
.tag.bad{color:var(--bad);border-color:var(--bad)}
.lbl{color:var(--mut);font-size:.78rem;text-transform:uppercase;letter-spacing:.05em;
margin:12px 0 2px;font-weight:600}
.nav{display:flex;flex-wrap:wrap;gap:8px;margin:18px 0}
.nav a{border:1px solid var(--line);background:var(--card);border-radius:8px;
padding:8px 12px;text-decoration:none;font-size:.9rem}
.toolbar{position:sticky;top:0;background:var(--bg);padding:10px 0;z-index:5;
border-bottom:1px solid var(--line);margin-bottom:10px;display:flex;gap:8px;flex-wrap:wrap}
.toolbar input,.toolbar select,.toolbar button{font:inherit;font-size:.88rem;padding:6px 9px;
border:1px solid var(--line);border-radius:6px;background:var(--card);color:var(--fg)}
.toolbar input{flex:1;min-width:150px}
.hidden{display:none}
footer{color:var(--mut);font-size:.82rem;margin-top:40px;border-top:1px solid var(--line);
padding-top:14px}
@media (max-width:640px){.wrap{padding:20px 16px 72px}h1{font-size:1.4rem}}
"""

JS = """
function fillSys(el){
  if(el.dataset.filled) return;
  var h=el.dataset.sys, pre=el.querySelector('pre');
  pre.textContent = (window.SYS && window.SYS[h]) || '[system prompt unavailable]';
  el.dataset.filled='1';
}
document.addEventListener('toggle', function(e){
  var t=e.target;
  if(t.tagName==='DETAILS' && t.open && t.dataset.sys) fillSys(t);
}, true);
function applyFilter(){
  var q=(document.getElementById('q').value||'').toLowerCase();
  var role=document.getElementById('role').value;
  var n=0;
  document.querySelectorAll('.call').forEach(function(c){
    var okRole = (role==='all' || c.dataset.role===role);
    var okQ = (!q || c.dataset.search.indexOf(q)>=0);
    var show = okRole && okQ;
    c.classList.toggle('hidden', !show);
    if(show) n++;
  });
  document.getElementById('count').textContent = n+' shown';
}
function expandAll(v){document.querySelectorAll('.call details').forEach(function(d){
  d.open=v; if(v&&d.dataset.sys) fillSys(d);});}
"""


def esc(text):
    return html.escape(text if isinstance(text, str) else json.dumps(text, indent=2))


def js_literal(obj):
    # Keep a literal "</script>" inside prompt text from closing the tag.
    return json.dumps(obj).replace("</", "<\\/")


def role_of(messages):
    system = next((m.get("content", "") for m in messages if m.get("role") == "system"), "")
    if "You are the Planner" in system:
        return "planner"
    return "supervisor" if "Supervisor" in system else "other"


def read_calls(wire: Path, split=None):
    calls = []
    for path in sorted(wire.glob("*.json")):
        record = json.loads(path.read_text())
        if record["method"] != "POST" or not record["path"].endswith("/chat/completions"):
            continue
        request = record["request"].get("json") or {}
        messages = request.get("messages") or []
        started = datetime.fromisoformat(record["started_at"])
        calls.append(dict(record=record, request=request, messages=messages,
                          role=role_of(messages), file=path.name,
                          phase="campaign" if (split and started >= split) else
                                ("fixed" if split else "all")))
    return calls


def usage_of(response):
    usage = response.get("usage") or {}
    return dict(prompt=usage.get("prompt_tokens"), completion=usage.get("completion_tokens"),
                reasoning=(usage.get("completion_tokens_details") or {}).get("reasoning_tokens"),
                cached=(usage.get("prompt_tokens_details") or {}).get("cached_tokens"))


def render_call(index, call, systems):
    record, request, messages = call["record"], call["request"], call["messages"]
    response = (record.get("response") or {}).get("json") or {}
    choice = next(iter(response.get("choices") or []), {})
    message = choice.get("message") or {}
    content = message.get("content") or ""
    reasoning = message.get("reasoning") or message.get("reasoning_content") or ""
    usage = usage_of(response)
    state, finish = record["state"], choice.get("finish_reason")

    if state != "completed":
        badge = f'<span class="tag bad">{esc(state)}</span>'
    elif finish == "length":
        badge = '<span class="tag bad">truncated (length)</span>'
    elif not content:
        badge = '<span class="tag bad">no content</span>'
    elif content.lstrip().startswith("{"):
        badge = '<span class="tag ok">bare JSON</span>'
    elif content.lstrip().startswith("```"):
        badge = '<span class="tag warn">fenced JSON</span>'
    else:
        badge = '<span class="tag warn">prose-wrapped</span>'

    system = next((m.get("content", "") for m in messages if m.get("role") == "system"), "")
    system_hash = hashlib.sha256(system.encode()).hexdigest()
    systems[system_hash] = system
    others = [m for m in messages if m.get("role") != "system"]

    bits = [f'started {record["started_at"]}',
            f'model {esc(str(request.get("model")))}',
            f'temperature {request.get("temperature")}',
            f'max_completion_tokens {request.get("max_completion_tokens")}',
            f'HTTP {record.get("status")}',
            f'latency {record.get("latency_s"):.2f}s' if record.get("latency_s") else "latency n/a",
            f'finish {finish}']
    if usage["prompt"] is not None:
        token_bits = f'tokens in {usage["prompt"]} / out {usage["completion"]}'
        if usage["reasoning"] is not None:
            token_bits += f' (reasoning {usage["reasoning"]})'
        if usage["cached"] is not None:
            token_bits += f', cached prompt {usage["cached"]}'
        bits.append(token_bits)
    else:
        bits.append("tokens not reported")

    parts = [f'<div class="call" data-role="{call["role"]}" '
             f'data-search="{esc((content[:1200] + " " + system_hash[:12] + " " + call["file"]).lower())}">',
             f'<h3><span>#{index:03d} {call["role"]}</span>{badge}'
             f'<span class="tag">{call["phase"]}</span></h3>',
             '<div class="meta">' + "".join(f"<span>{b}</span>" for b in bits) + "</div>"]

    if record.get("injected_extra_body"):
        parts.append('<div class="note"><strong>Recorder-injected body key.</strong> '
                     'The pinned controller did not send this; the recorder added it because the '
                     'client cannot express it. Both bodies are kept in the archive.<br>'
                     f'<code>{esc(json.dumps(record["injected_extra_body"]))}</code></div>')
    if record.get("cancellation_reason"):
        parts.append(f'<div class="note"><strong>Cancelled.</strong> '
                     f'{esc(record["cancellation_reason"])} No upstream HTTP response exists.</div>')

    parts.append(f'<details data-sys="{system_hash}"><summary>system prompt '
                 f'({len(system):,} chars, sha256 {system_hash[:12]})</summary>'
                 f'<pre class="tall"></pre></details>')
    for message_in in others:
        body = message_in.get("content")
        body = body if isinstance(body, str) else json.dumps(body, indent=2)
        parts.append(f'<details><summary>{esc(message_in.get("role", "?"))} message '
                     f'({len(body):,} chars)</summary><pre class="tall">{esc(body)}</pre></details>')
    if reasoning:
        parts.append(f'<div class="lbl">assistant reasoning ({len(reasoning):,} chars)</div>'
                     f'<pre>{esc(reasoning)}</pre>')
    if content:
        parts.append(f'<div class="lbl">assistant response ({len(content):,} chars, verbatim)</div>'
                     f'<pre>{esc(content)}</pre>')
    else:
        error = response.get("error")
        parts.append('<div class="lbl">no assistant message</div>'
                     f'<pre>{esc(json.dumps(error, indent=2) if error else "state=" + state)}</pre>')
    parts.append(f'<div class="meta"><span>wire record <code>{esc(call["file"])}</code></span></div>')
    parts.append("</div>")
    return "\n".join(parts)


def page(title, description, body, systems=None):
    store = f'<script>window.SYS={js_literal(systems or {})};</script>'
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'><text y='14' font-size='14'>%F0%9F%A7%AC</text></svg>">
<style>{CSS}</style></head>
<body><div class="wrap">{body}</div>{store}<script>{JS}</script></body></html>
"""


def summarize(calls):
    done = [c for c in calls if c["record"]["state"] == "completed"]
    def content(c):
        choice = next(iter(((c["record"].get("response") or {}).get("json") or {}).get("choices") or []), {})
        return (choice.get("message") or {}).get("content") or "", choice.get("finish_reason")
    bare = sum(1 for c in done if content(c)[0].lstrip().startswith("{"))
    fenced = sum(1 for c in done if content(c)[0].lstrip().startswith("```"))
    empty = sum(1 for c in done if not content(c)[0])
    prose = len(done) - bare - fenced - empty
    return dict(calls=len(calls), completed=len(done),
                cancelled=sum(1 for c in calls if c["record"]["state"] != "completed"),
                bare_json=bare, fenced=fenced, prose=prose, empty=empty,
                truncated=sum(1 for c in done if content(c)[1] == "length"),
                roles=dict(Counter(c["role"] for c in calls)))


def arm_page(name, label, calls, out: Path, first_index=1, pager=""):
    systems, rendered = {}, []
    for i, call in enumerate(calls, first_index):
        rendered.append(render_call(i, call, systems))
    stats = summarize(calls)
    body = [f'<p><a href="index.html">← all arms</a></p>',
            f"<h1>{esc(label)}</h1>",
            f'<p class="sub">{stats["calls"]} chat completions, verbatim from the wire archive. '
            f'{len(systems)} distinct system prompt(s), stored once and shown by SHA-256.</p>',
            pager,
            '<div class="toolbar">',
            '<input id="q" placeholder="filter by response text, wire file or system hash" oninput="applyFilter()">',
            '<select id="role" onchange="applyFilter()"><option value="all">all roles</option>'
            '<option value="planner">planner</option><option value="supervisor">supervisor</option></select>',
            '<button onclick="expandAll(true)">expand all</button>',
            '<button onclick="expandAll(false)">collapse all</button>',
            f'<span class="tag" id="count">{stats["calls"]} shown</span></div>',
            "\n".join(rendered),
            pager,
            '<footer>Bodies are byte-for-byte as recorded. Expanding a system prompt injects the '
            'stored copy for its hash. Filtering applies to this page only.</footer>']
    out.write_text(page(f"{label} transcripts", f"Recorded {label} calls in the PD-L1 pilot.",
                        "\n".join(body), systems))
    return stats


def chunked_pages(arm, label, calls, output: Path, stem, per_page):
    """Split one phase across pages so no single file is unwieldy to load."""
    groups = [calls[i:i + per_page] for i in range(0, len(calls), per_page)] or [[]]
    names = [f"{stem}.html" if i == 0 else f"{stem}-{i + 1}.html" for i in range(len(groups))]
    made = []
    for i, (group, name) in enumerate(zip(groups, names)):
        pager = ""
        if len(groups) > 1:
            links = "".join(
                f'<a href="{other}">calls {j * per_page + 1}–{j * per_page + len(groups[j])}</a>'
                if j != i else
                f'<a href="{other}" style="font-weight:700">calls {j * per_page + 1}–'
                f'{j * per_page + len(groups[j])}</a>'
                for j, other in enumerate(names))
            pager = f'<div class="nav">{links}</div>'
        title = label if len(groups) == 1 else f"{label} ({i + 1} of {len(groups)})"
        stats = arm_page(arm, title, group, output / name,
                         first_index=i * per_page + 1, pager=pager)
        made.append((title, name, stats))
    return made


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifacts", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--arms", nargs="+", default=["qwen", "snowball", "glm"])
    parser.add_argument("--replays", nargs="+", default=[])
    parser.add_argument("--per-page", type=int, default=20,
                        help="Calls per page; large prompts make single-file pages slow to load.")
    parser.add_argument("--note", help="Caveat shown on the index, e.g. an arm still running.")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    index_rows, pages = [], []

    for arm in args.arms:
        wire = args.artifacts / arm / "wire"
        if not wire.is_dir():
            continue
        split_file = args.artifacts / arm / "campaign-start-time.txt"
        split = None
        if split_file.exists():
            split = datetime.fromisoformat(split_file.read_text().strip().replace("Z", "+00:00"))
        calls = read_calls(wire, split)
        label = TITLES.get(arm, arm)
        for phase, suffix in [("fixed", "fixed"), ("campaign", "campaign")]:
            subset = [c for c in calls if c["phase"] == phase]
            if not subset:
                continue
            heading = (f"{label} — fixed-evidence checks" if phase == "fixed"
                       else f"{label} — live campaign")
            pages += chunked_pages(arm, heading, subset, args.output,
                                   f"{arm}-{suffix}", args.per_page)
        if not split:
            pages += chunked_pages(arm, label, calls, args.output, arm, args.per_page)
        index_rows.append((label, summarize(calls)))

    for replay in args.replays:
        wire = args.artifacts / replay / "wire"
        if not wire.is_dir():
            continue
        pages += chunked_pages(replay, replay, read_calls(wire), args.output,
                               replay, args.per_page)

    stamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
    head = ["<h1>What the model actually saw and said</h1>",
            '<p class="sub">Every Planner and Supervisor call in the PD-L1 pilot, copied verbatim '
            'from the recording proxy: the exact prompt bytes the pinned T-REX controller sent, and '
            'the exact bytes the model returned.</p>',
            (f'<div class="note"><strong>Note.</strong> {esc(args.note)}</div>' if args.note else ""),
            '<div class="note">Each arm runs the same controller against the same target, seed and '
            'action families. A conversation here is always a <strong>single stateless turn</strong>: '
            'one large system prompt defining the role and output schema, one user message carrying '
            'the current evidence as JSON, and one response that must itself be JSON. There is no '
            'multi-turn chat — the controller re-sends the whole state every tick.</div>',
            "<h2>Pages</h2>", '<div class="nav">'
            + "".join(f'<a href="{name}">{esc(title)}</a>' for title, name, _ in pages) + "</div>",
            "<h2>Response shape, by arm</h2>",
            '<table><tr><th>Arm</th><th class="num">Calls</th><th class="num">Cancelled</th>'
            '<th class="num">Bare JSON</th><th class="num">Fenced</th><th class="num">Prose</th>'
            '<th class="num">Empty</th><th class="num">Truncated</th></tr>']
    for label, s in index_rows:
        head.append(f'<tr><td>{esc(label)}</td><td class="num">{s["calls"]}</td>'
                    f'<td class="num">{s["cancelled"]}</td><td class="num">{s["bare_json"]}</td>'
                    f'<td class="num">{s["fenced"]}</td><td class="num">{s["prose"]}</td>'
                    f'<td class="num">{s["empty"]}</td><td class="num">{s["truncated"]}</td></tr>')
    head += ["</table>",
             '<p class="sub">Counts cover completed HTTP responses; cancelled calls returned no body '
             'at all. "Fenced" means a valid object wrapped in a Markdown code fence, which the '
             "controller's extractor recovers. \"Prose\" means the object had to be found inside "
             "surrounding text.</p>",
             '<h2>How to read a call</h2>',
             '<p>Every call shows its sampling settings, transport outcome, token usage and the '
             'SHA-256 of its system prompt. Identical hashes mean identical prompt bytes, which is '
             'how the fixed-evidence checks are matched across arms. Expand a section to see the '
             'full text; nothing is abridged.</p>',
             f'<footer>Generated {esc(stamp)} from the wire archives under '
             '<code>artifacts/</code> by <code>scripts/make_transcript_report.py</code>. '
             'The archives remain authoritative; regenerating reproduces these pages.</footer>']
    (args.output / "index.html").write_text(
        page("PD-L1 pilot transcripts", "Exact prompts and responses for every model call in the "
             "PD-L1 design pilot.", "\n".join(head)))
    print(f"wrote {len(pages) + 1} pages to {args.output}")


if __name__ == "__main__":
    main()
