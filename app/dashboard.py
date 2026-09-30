from __future__ import annotations

import json
import math
import os
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path
from typing import Any


LOG_PATH = Path(os.getenv("LOG_PATH", "data/logs.jsonl"))


def _timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _load_records(minutes: int) -> tuple[list[dict[str, Any]], datetime | None]:
    if not LOG_PATH.exists():
        return [], None

    records: list[dict[str, Any]] = []
    latest: datetime | None = None
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    for line in LOG_PATH.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(line)
        except (json.JSONDecodeError, TypeError):
            continue
        ts = _timestamp(record.get("ts"))
        if ts is None:
            continue
        latest = ts if latest is None or ts > latest else latest
        if ts >= cutoff:
            records.append(record)
    return records, latest


def _percentile(values: list[float], percentile: int) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(percentile / 100 * len(ordered)) - 1))
    return float(ordered[index])


def _number(value: float, decimals: int = 0) -> str:
    return f"{value:,.{decimals}f}"


def _status(ok: bool) -> str:
    label = "Within threshold" if ok else "Threshold breached"
    css = "status-ok" if ok else "status-bad"
    return f'<span class="status {css}">{label}</span>'


def _bullet(label: str, value: float, ceiling: float, unit: str, color: str = "cyan") -> str:
    width = min(100.0, value / ceiling * 100) if ceiling else 0.0
    return f"""
      <div class="bullet-row">
        <div class="bullet-meta"><span>{escape(label)}</span><strong>{_number(value)} {escape(unit)}</strong></div>
        <div class="bullet-track"><span class="bullet-fill {color}" style="width:{width:.2f}%"></span></div>
      </div>
    """


def _bars(points: list[tuple[str, float]], unit: str, color: str = "cyan") -> str:
    if not points:
        return '<div class="empty">No data in selected time range</div>'
    peak = max(value for _, value in points) or 1.0
    bars = []
    for label, value in points[-12:]:
        height = max(5.0, value / peak * 100)
        aria = escape(f"{label}: {_number(value, 4 if unit == 'USD' else 0)} {unit}")
        bars.append(
            f'<div class="spark-column" aria-label="{aria}">'
            f'<span class="spark-value">{_number(value, 3 if unit == "USD" else 0)}</span>'
            f'<span class="spark-bar {color}" style="height:{height:.2f}%"></span>'
            f'<span class="spark-label">{escape(label)}</span></div>'
        )
    return '<div class="spark" role="img" aria-label="Time series">' + "".join(bars) + "</div>"


def _minute_points(records: list[dict[str, Any]], event: str, field: str | None = None) -> list[tuple[str, float]]:
    buckets: dict[datetime, float] = defaultdict(float)
    for record in records:
        if record.get("event") != event:
            continue
        ts = _timestamp(record.get("ts"))
        if ts is None:
            continue
        key = ts.replace(second=0, microsecond=0)
        buckets[key] += float(record.get(field, 0) or 0) if field else 1.0
    return [(key.strftime("%H:%M"), value) for key, value in sorted(buckets.items())]


def render_dashboard(minutes: int = 60) -> str:
    minutes = max(5, min(minutes, 24 * 60))
    records, latest = _load_records(minutes)
    responses = [record for record in records if record.get("event") == "response_sent"]
    requests = [record for record in records if record.get("event") == "request_received"]
    failures = [record for record in records if record.get("event") == "request_failed"]

    latencies = [float(record["latency_ms"]) for record in responses if isinstance(record.get("latency_ms"), (int, float))]
    ttfts = [float(record["ttft_ms"]) for record in responses if isinstance(record.get("ttft_ms"), (int, float))]
    p50 = _percentile(latencies, 50)
    p95 = _percentile(latencies, 95)
    p99 = _percentile(latencies, 99)
    ttft_p95 = _percentile(ttfts, 95)

    traffic = _minute_points(records, "request_received")
    peak_rpm = max((value for _, value in traffic), default=0.0)
    error_rate = len(failures) / len(requests) * 100 if requests else 0.0
    error_types = Counter(str(record.get("error_type") or "unknown") for record in failures)
    tool_results = [record.get("tool_success") for record in records if isinstance(record.get("tool_success"), bool)]
    retrieval_success = sum(result is True for result in tool_results) / len(tool_results) * 100 if tool_results else 0.0

    total_cost = sum(float(record.get("cost_usd", 0) or 0) for record in responses)
    cost_points = _minute_points(records, "response_sent", "cost_usd")
    tokens_in = sum(int(record.get("tokens_in", 0) or 0) for record in responses)
    tokens_out = sum(int(record.get("tokens_out", 0) or 0) for record in responses)
    qualities = [float(record["quality_score"]) for record in responses if isinstance(record.get("quality_score"), (int, float))]
    quality_avg = sum(qualities) / len(qualities) if qualities else 0.0

    latest_text = latest.astimezone().strftime("%Y-%m-%d %H:%M:%S %Z") if latest else "No records"
    error_detail = ", ".join(f"{escape(name)}: {count}" for name, count in error_types.items()) or "No request failures"
    token_ceiling = max(50_000.0, float(tokens_in), float(tokens_out))

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="refresh" content="30">
  <title>K4-L3B Monitoring Dashboard</title>
  <style>
    :root {{ color-scheme: dark; --bg:#07111f; --panel:#0d1b2d; --panel2:#10233a; --text:#eef6ff; --muted:#8fa6bf; --line:#233a53; --cyan:#33d6ff; --blue:#6c8cff; --green:#45d69c; --amber:#ffbf5b; --red:#ff6b7a; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; min-width:1100px; background:radial-gradient(circle at 15% 0%, #132b47 0, var(--bg) 38%); color:var(--text); font-family:Inter,Segoe UI,Arial,sans-serif; }}
    .page {{ max-width:1800px; margin:0 auto; padding:24px 28px 30px; }}
    header {{ display:flex; align-items:flex-end; justify-content:space-between; gap:20px; margin-bottom:20px; }}
    h1 {{ margin:0 0 7px; font-size:25px; font-weight:600; letter-spacing:-.02em; }}
    .subtitle,.meta,.panel-sub,.foot {{ color:var(--muted); }}
    .subtitle {{ font-size:13px; }}
    .header-right {{ display:flex; align-items:center; gap:10px; }}
    .pill {{ padding:8px 12px; border:1px solid var(--line); border-radius:999px; background:#0a1727; font-size:12px; color:#bcd0e5; }}
    .live {{ color:var(--green); }}
    .grid {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:14px; }}
    .panel {{ min-height:285px; padding:18px; border:1px solid var(--line); border-radius:14px; background:linear-gradient(160deg,rgba(18,40,66,.96),rgba(10,25,42,.96)); box-shadow:0 12px 32px rgba(0,0,0,.2); overflow:hidden; }}
    .panel-head {{ display:flex; justify-content:space-between; align-items:flex-start; gap:12px; margin-bottom:14px; }}
    h2 {{ margin:0 0 4px; font-size:15px; font-weight:600; }}
    .panel-sub {{ font-size:11px; }}
    .status {{ white-space:nowrap; border-radius:999px; padding:5px 8px; font-size:10px; font-weight:600; }}
    .status-ok {{ color:var(--green); background:rgba(69,214,156,.11); }}
    .status-bad {{ color:var(--red); background:rgba(255,107,122,.12); }}
    .hero {{ display:flex; align-items:baseline; gap:8px; margin:4px 0 14px; }}
    .hero strong {{ font-size:35px; font-weight:600; letter-spacing:-.04em; }}
    .hero span {{ color:var(--muted); font-size:12px; }}
    .bullet-row {{ margin:11px 0; }}
    .bullet-meta {{ display:flex; justify-content:space-between; gap:12px; font-size:11px; margin-bottom:6px; color:#bed0e1; }}
    .bullet-meta strong {{ color:var(--text); font-weight:500; }}
    .bullet-track {{ height:7px; border-radius:7px; background:#1a3048; overflow:hidden; }}
    .bullet-fill {{ display:block; min-width:3px; height:100%; border-radius:inherit; }}
    .cyan {{ background:linear-gradient(90deg,#299ec3,var(--cyan)); }}
    .blue {{ background:linear-gradient(90deg,#536fd4,var(--blue)); }}
    .green {{ background:linear-gradient(90deg,#2fa474,var(--green)); }}
    .amber {{ background:linear-gradient(90deg,#cc8f32,var(--amber)); }}
    .red {{ background:linear-gradient(90deg,#ce485a,var(--red)); }}
    .spark {{ height:145px; display:flex; align-items:flex-end; gap:8px; padding:20px 4px 25px; border-bottom:1px solid var(--line); position:relative; }}
    .spark-column {{ height:100%; flex:1; min-width:12px; display:flex; justify-content:flex-end; align-items:center; flex-direction:column; position:relative; }}
    .spark-bar {{ width:min(28px,80%); min-height:5px; border-radius:4px 4px 1px 1px; }}
    .spark-value {{ color:#d8e8f7; font-size:9px; margin-bottom:4px; }}
    .spark-label {{ position:absolute; top:calc(100% + 7px); color:var(--muted); font-size:9px; white-space:nowrap; }}
    .split {{ display:grid; grid-template-columns:1fr 1fr; gap:10px; margin:12px 0; }}
    .mini {{ padding:12px; border-radius:10px; background:rgba(5,16,28,.48); }}
    .mini-label {{ color:var(--muted); font-size:10px; margin-bottom:5px; }}
    .mini-value {{ font-size:23px; font-weight:600; }}
    .gauge {{ height:12px; margin:18px 0 8px; border-radius:10px; background:linear-gradient(90deg,rgba(255,107,122,.35) 0 75%,rgba(69,214,156,.22) 75% 100%); position:relative; }}
    .gauge-marker {{ position:absolute; top:-6px; width:3px; height:24px; border-radius:2px; background:var(--text); box-shadow:0 0 10px rgba(238,246,255,.55); }}
    .gauge-threshold {{ position:absolute; left:75%; top:-3px; height:18px; border-left:1px dashed var(--amber); }}
    .gauge-labels {{ display:flex; justify-content:space-between; color:var(--muted); font-size:10px; }}
    .empty {{ height:145px; display:grid; place-items:center; color:var(--muted); font-size:12px; }}
    .foot {{ display:flex; justify-content:space-between; gap:20px; margin-top:14px; padding-top:12px; border-top:1px solid var(--line); font-size:10px; }}
    .source {{ color:#7ddcf5; }}
    @media (max-width:1250px) {{ .grid {{ grid-template-columns:repeat(2,minmax(0,1fr)); }} body {{ min-width:760px; }} }}
    @media print {{ body {{ background:var(--bg); }} .page {{ padding:12px; }} .panel {{ box-shadow:none; break-inside:avoid; }} }}
  </style>
</head>
<body>
  <main class="page">
    <header>
      <div>
        <h1>K4-L3B Monitoring &amp; LLMOps</h1>
        <div class="subtitle">Operational overview from structured application logs</div>
      </div>
      <div class="header-right">
        <span class="pill"><span class="live">●</span> Auto-refresh 30s</span>
        <span class="pill">Last {minutes} minutes</span>
        <span class="pill">{len(records)} records</span>
      </div>
    </header>

    <section class="grid">
      <article class="panel">
        <div class="panel-head"><div><h2>Latency percentiles &amp; TTFT</h2><div class="panel-sub">Response latency distribution</div></div>{_status(p95 <= 3000)}</div>
        <div class="hero"><strong>{_number(p95)}</strong><span>ms P95</span></div>
        {_bullet("Latency P50", p50, 3000, "ms")}
        {_bullet("Latency P95", p95, 3000, "ms", "blue")}
        {_bullet("Latency P99", p99, 3000, "ms", "amber")}
        {_bullet("TTFT P95", ttft_p95, 3000, "ms", "green")}
        <div class="foot"><span>Threshold: P95 ≤ 3,000 ms</span><span class="source">response_sent</span></div>
      </article>

      <article class="panel">
        <div class="panel-head"><div><h2>Request traffic</h2><div class="panel-sub">Requests grouped by minute</div></div>{_status(peak_rpm >= 1)}</div>
        <div class="hero"><strong>{_number(len(requests))}</strong><span>requests total · peak {_number(peak_rpm)} req/min</span></div>
        {_bars(traffic, "req/min")}
        <div class="foot"><span>Threshold: ≥ 1 request/min</span><span class="source">request_received</span></div>
      </article>

      <article class="panel">
        <div class="panel-head"><div><h2>Errors &amp; retrieval success</h2><div class="panel-sub">Availability and tool health</div></div>{_status(error_rate <= 2 and (retrieval_success >= 90 or not tool_results))}</div>
        <div class="split">
          <div class="mini"><div class="mini-label">Error rate</div><div class="mini-value">{_number(error_rate, 1)}%</div></div>
          <div class="mini"><div class="mini-label">Retrieval success</div><div class="mini-value">{_number(retrieval_success, 1)}%</div></div>
        </div>
        {_bullet("Error rate", error_rate, 100, "%", "red")}
        {_bullet("Retrieval success", retrieval_success, 100, "%", "green")}
        <div class="panel-sub">{error_detail}</div>
        <div class="foot"><span>Error ≤ 2% · Retrieval ≥ 90%</span><span class="source">request_failed / tool_success</span></div>
      </article>

      <article class="panel">
        <div class="panel-head"><div><h2>Cost over time</h2><div class="panel-sub">Estimated model cost by minute</div></div>{_status(total_cost <= 2.5)}</div>
        <div class="hero"><strong>${_number(total_cost, 4)}</strong><span>USD total</span></div>
        {_bars(cost_points, "USD", "green")}
        <div class="foot"><span>Threshold: total ≤ $2.50</span><span class="source">response_sent.cost_usd</span></div>
      </article>

      <article class="panel">
        <div class="panel-head"><div><h2>Input &amp; output tokens</h2><div class="panel-sub">Token consumption by direction</div></div>{_status(max(tokens_in, tokens_out) <= 50_000)}</div>
        <div class="hero"><strong>{tokens_in + tokens_out:,}</strong><span>tokens total</span></div>
        {_bullet("Input tokens", float(tokens_in), token_ceiling, "tokens", "blue")}
        {_bullet("Output tokens", float(tokens_out), token_ceiling, "tokens", "cyan")}
        <div class="split">
          <div class="mini"><div class="mini-label">Input</div><div class="mini-value">{tokens_in:,}</div></div>
          <div class="mini"><div class="mini-label">Output</div><div class="mini-value">{tokens_out:,}</div></div>
        </div>
        <div class="foot"><span>Guardrail: each field ≤ 50,000</span><span class="source">response_sent tokens</span></div>
      </article>

      <article class="panel">
        <div class="panel-head"><div><h2>Quality proxy</h2><div class="panel-sub">Mean heuristic answer quality</div></div>{_status(quality_avg >= .75)}</div>
        <div class="hero"><strong>{_number(quality_avg, 2)}</strong><span>average score / 1.00</span></div>
        <div class="gauge" role="img" aria-label="Quality score {_number(quality_avg, 2)}; threshold 0.75">
          <span class="gauge-threshold"></span><span class="gauge-marker" style="left:{min(100, quality_avg * 100):.2f}%"></span>
        </div>
        <div class="gauge-labels"><span>0.00</span><span>threshold 0.75</span><span>1.00</span></div>
        <div class="split">
          <div class="mini"><div class="mini-label">Samples</div><div class="mini-value">{len(qualities)}</div></div>
          <div class="mini"><div class="mini-label">Below threshold</div><div class="mini-value">{sum(value < .75 for value in qualities)}</div></div>
        </div>
        <div class="foot"><span>Threshold: mean ≥ 0.75</span><span class="source">response_sent.quality_score</span></div>
      </article>
    </section>

    <div class="foot"><span>Source: {escape(str(LOG_PATH))}</span><span>Latest record: {escape(latest_text)}</span></div>
  </main>
</body>
</html>"""
