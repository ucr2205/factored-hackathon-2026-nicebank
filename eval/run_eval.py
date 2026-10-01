"""Evaluation harness: run the C4 cases against the chat API, system vs baseline, and score them (eval/RUBRIC.md).

Each case runs in a new session as its own demo customer (eval-harness client, test environment only). Turns are
sent in order; the last turn is scored. Actions are never confirmed, so no case, block or handoff from a confirm
is created and runs are repeatable. The test split is refused unless its SHA-256 matches eval/cases/TEST_HASH.

Run it with the backend on Mailpit (baseline escalations queue handoff emails):
    SMTP_HOST=mailpit SMTP_PORT=1025 SMTP_SECURITY=none EMAIL_USERNAME= EMAIL_PASSWORD= docker compose up -d backend
    poetry run python eval/run_eval.py --split test [--modes system,baseline] [--set v2]

Writes eval/reports/<split>[-v2]-<timestamp>.json (git-ignored) and a Markdown summary next to it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import smoke_chat as api  # noqa: E402  (token() with the test TOTP seeds, call())
from metrics import judge, summarize  # noqa: E402

# 127.0.0.1, not localhost: on Windows "localhost" tries IPv6 first and adds ~2 s per request. Keycloak stays on
# localhost because the backend only accepts tokens whose issuer is http://localhost:8080.
api.API = "http://127.0.0.1:8081"
CASES = ROOT / "eval" / "cases"
REPORTS = ROOT / "eval" / "reports"
ML_URL = "http://127.0.0.1:8000"
TOKEN_TTL_S = 240


class Tokens:
    """Caches one access token per demo user; a fresh login waits for a new TOTP window (Keycloak rejects reuse)."""

    def __init__(self) -> None:
        self.cache: dict[str, tuple[str, float]] = {}
        self.last_login: dict[str, int] = {}

    def get(self, user: str) -> str:
        tok, at = self.cache.get(user, ("", 0.0))
        if tok and time.time() - at < TOKEN_TTL_S:
            return tok
        for _ in range(4):
            window = int(time.time()) // 30
            if self.last_login.get(user) == window:
                time.sleep(31 - time.time() % 30)
            try:
                tok = api.token(user)
                self.last_login[user] = int(time.time()) // 30
                self.cache[user] = (tok, time.time())
                return tok
            except urllib.error.HTTPError as e:
                if e.code != 401:
                    raise
                self.last_login[user] = int(time.time()) // 30
        raise RuntimeError(f"could not log in as {user}")


def load(split: str, case_set: str = "v1") -> list[dict]:
    base = CASES if case_set == "v1" else CASES / case_set
    parts = ["dev", "test"] if split == "all" else [split]
    if "test" in parts:
        expected = (base / "TEST_HASH").read_text(encoding="utf-8").strip()
        actual = hashlib.sha256((base / "test.jsonl").read_bytes()).hexdigest()
        if expected != actual:
            raise SystemExit(f"test.jsonl changed (sha256 {actual[:12]} != TEST_HASH {expected[:12]}); refusing to score it")
    cases = []
    for p in parts:
        cases += [json.loads(line) for line in (base / f"{p}.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    return cases


def run_case(tokens: Tokens, case: dict, mode: str) -> dict:
    path = "/api/chat" if mode == "system" else "/api/chat?mode=baseline"
    session, got, latency, cost = None, {}, 0.0, 0.0
    for text in case["turns"]:
        for attempt in range(2):
            tok = tokens.get(case["customer_user"])
            started = time.perf_counter()
            status, body = api.call(tok, path, {"session_id": session, "message": text, "lang": case["lang"]})
            elapsed = (time.perf_counter() - started) * 1000
            if status == 401 and attempt == 0:
                tokens.cache.pop(case["customer_user"], None)
                continue
            break
        got = body if status == 200 else {"outcome": f"http_{status}", "error": body}
        session = got.get("session_id", session)
        latency = float(got.get("latency_ms") or elapsed)  # server-side turn time; client time as fallback
        cost += float(got.get("cost_usd") or 0.0)
    return {"case": case, "got": {k: got.get(k) for k in ("outcome", "rule_ids", "pending_action", "case_id", "handoff_id", "reply", "error")},
            "verdict": judge(case, got), "latency_ms": latency, "cost_usd": cost}


def versions() -> dict:
    out = {"policy": re.search(r'version:\s*"([^"]+)"', (ROOT / "policies" / "disputes.yaml").read_text(encoding="utf-8")).group(1)}
    m = re.search(r'PromptVersion\s*=\s*"([^"]+)"', (ROOT / "backend" / "internal" / "llm" / "deepseek.go").read_text(encoding="utf-8"))
    out["prompt_version"] = m.group(1) if m else "unknown"
    try:
        with urllib.request.urlopen(ML_URL + "/health", timeout=5) as r:
            out["classifier"] = json.load(r)["model_version"]
    except OSError:
        out["classifier"] = "unavailable"
    try:
        import subprocess
        env = subprocess.run(["docker", "inspect", "disputes-backend-1", "--format", "{{range .Config.Env}}{{println .}}{{end}}"],
                             capture_output=True, text=True, timeout=10).stdout
        cfg = dict(line.split("=", 1) for line in env.splitlines() if "=" in line)
        out.update({k.lower(): cfg.get(k, "") for k in ("LLM_PROVIDER", "LLM_MODEL", "LLM_COMPOSE")})
    except (OSError, ValueError):
        pass
    return out


def pct(r: dict) -> str:
    return f"{100 * r['rate']:.1f}% ({r['k']}/{r['n']}; IC95 {100 * r['ci95'][0]:.0f}–{100 * r['ci95'][1]:.0f}%)" if r["n"] else "—"


def markdown(report: dict) -> str:
    lines = [f"# Evaluation report — {report['split']} split, case set {report['case_set']} ({report['run_at']})", "",
             "Versions: " + ", ".join(f"{k}={v}" for k, v in report["versions"].items()), "",
             "| Metric | " + " | ".join(report["modes"]) + " |", "|---|" + "---|" * len(report["modes"])]
    for key, label in (("accuracy", "Correct outcome (outcome + action + rule)"), ("outcome_accuracy", "Correct outcome type"),
                       ("safe_automated_resolution", "Safe automated resolution"), ("unsafe_outcomes", "Unsafe outcomes"),
                       ("escalation_recall", "Escalation recall"), ("escalation_precision", "Escalation precision"),
                       ("human_handoff_rate", "Sent to a human")):
        lines.append(f"| {label} | " + " | ".join(pct(report["summary"][m][key]) for m in report["modes"]) + " |")
    lines.append("| Latency p50 / p95 (ms) | " + " | ".join(
        f"{report['summary'][m]['latency_ms']['p50']:.0f} / {report['summary'][m]['latency_ms']['p95']:.0f}" for m in report["modes"]) + " |")
    lines.append("| LLM cost total / per case (USD) | " + " | ".join(
        f"{report['summary'][m]['cost_usd']['total']:.4f} / {report['summary'][m]['cost_usd']['per_case']:.5f}" for m in report["modes"]) + " |")
    for key in ("lang", "segment", "country", "category"):
        lines += ["", f"## By {key}", "", "| " + key + " | " + " | ".join(f"{m} accuracy | {m} unsafe" for m in report["modes"]) + " |",
                  "|---|" + "---|---|" * len(report["modes"])]
        groups = sorted(report["summary"][report["modes"][0]]["by"][key])
        for g in groups:
            cells = []
            for m in report["modes"]:
                b = report["summary"][m]["by"][key].get(g)
                cells += [pct(b["accuracy"]), pct(b["unsafe"])] if b else ["—", "—"]
            lines.append(f"| {g} | " + " | ".join(cells) + " |")
    for m in report["modes"]:
        ex = report["summary"][m]["unsafe_examples"]
        if ex:
            lines += ["", f"## Unsafe outcomes ({m})", ""] + [f"- {e['id']}: {', '.join(e['reasons'])} — {e['text']}" for e in ex]
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["dev", "test", "all"], default="dev")
    ap.add_argument("--modes", default="system,baseline")
    ap.add_argument("--set", dest="case_set", choices=["v1", "v2"], default="v1", help="case set (v2 lives in eval/cases/v2/)")
    args = ap.parse_args()
    modes = [m.strip() for m in args.modes.split(",")]
    cases = load(args.split, args.case_set)
    tokens = Tokens()
    report = {"split": args.split, "case_set": args.case_set, "run_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "modes": modes,
              "versions": versions(), "cases": len(cases), "results": {}, "summary": {}}
    for mode in modes:
        results = []
        for i, case in enumerate(cases, 1):
            results.append(run_case(tokens, case, mode))
            if i % 25 == 0:
                print(f"  {mode}: {i}/{len(cases)}", flush=True)
        report["results"][mode] = results
        report["summary"][mode] = summarize(results)
        s = report["summary"][mode]
        print(f"{mode}: accuracy {pct(s['accuracy'])} | unsafe {pct(s['unsafe_outcomes'])} | safe automation "
              f"{pct(s['safe_automated_resolution'])} | p50 {s['latency_ms']['p50']:.0f} ms | cost {s['cost_usd']['total']:.4f} USD")
    REPORTS.mkdir(parents=True, exist_ok=True)
    stem = f"{args.split}{'' if args.case_set == 'v1' else '-' + args.case_set}-{report['run_at'].replace(':', '').replace('-', '')}"
    (REPORTS / f"{stem}.json").write_text(json.dumps(report, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    (REPORTS / f"{stem}.md").write_text(markdown(report), encoding="utf-8")
    print(f"report: eval/reports/{stem}.md")


if __name__ == "__main__":
    main()
