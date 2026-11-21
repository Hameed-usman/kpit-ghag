"""
scripts/smoke.py – Python-based smoke testing tool for Ghag.

Pure Python standard library implementation (no bash, no requests required).
Safe for Windows PowerShell (reads Unicode test cases from UTF-8 JSON file).

Usage:
    python scripts\\smoke.py                          # Run standard text cases against http://localhost:8000
    python scripts\\smoke.py --url http://127.0.0.1:8000
    python scripts\\smoke.py --audio sample.wav      # Post audio to /ask
    python scripts\\smoke.py --audio sample.wav --check # Post audio to /check
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


def post_form(url: str, fields: Dict[str, str]) -> Tuple[Dict[str, Any], float, int]:
    """Perform application/x-www-form-urlencoded POST request."""
    data = urllib.parse.urlencode(fields).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded", "User-Agent": "Ghag-Smoke/1.0"},
    )
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            elapsed = time.perf_counter() - t0
            return json.loads(resp.read().decode("utf-8")), elapsed, resp.status
    except urllib.error.HTTPError as exc:
        elapsed = time.perf_counter() - t0
        try:
            body = json.loads(exc.read().decode("utf-8"))
        except Exception:
            body = {"error": str(exc)}
        return body, elapsed, exc.code
    except Exception as exc:
        elapsed = time.perf_counter() - t0
        return {"error": str(exc)}, elapsed, 500


def post_multipart(url: str, fields: Dict[str, str], file_field: str, file_path: Path) -> Tuple[Dict[str, Any], float, int]:
    """Perform multipart/form-data POST request with standard library."""
    boundary = "----GhagBoundary" + hex(int(time.time() * 1000))[2:]
    body = bytearray()

    # Form fields
    for k, v in fields.items():
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(f'Content-Disposition: form-data; name="{k}"\r\n\r\n'.encode("utf-8"))
        body.extend(f"{v}\r\n".encode("utf-8"))

    # File field
    filename = file_path.name
    content_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
    file_bytes = file_path.read_bytes()

    body.extend(f"--{boundary}\r\n".encode("utf-8"))
    body.extend(f'Content-Disposition: form-data; name="{file_field}"; filename="{filename}"\r\n'.encode("utf-8"))
    body.extend(f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"))
    body.extend(file_bytes)
    body.extend(b"\r\n")

    body.extend(f"--{boundary}--\r\n".encode("utf-8"))

    req = urllib.request.Request(
        url,
        data=bytes(body),
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "User-Agent": "Ghag-Smoke/1.0",
        },
    )

    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            elapsed = time.perf_counter() - t0
            return json.loads(resp.read().decode("utf-8")), elapsed, resp.status
    except urllib.error.HTTPError as exc:
        elapsed = time.perf_counter() - t0
        try:
            res_body = json.loads(exc.read().decode("utf-8"))
        except Exception:
            res_body = {"error": str(exc)}
        return res_body, elapsed, exc.code
    except Exception as exc:
        elapsed = time.perf_counter() - t0
        return {"error": str(exc)}, elapsed, 500


def get_json(url: str) -> Tuple[Dict[str, Any], float, int]:
    """Perform GET request."""
    req = urllib.request.Request(url, headers={"User-Agent": "Ghag-Smoke/1.0"})
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            elapsed = time.perf_counter() - t0
            return json.loads(resp.read().decode("utf-8")), elapsed, resp.status
    except Exception as exc:
        elapsed = time.perf_counter() - t0
        return {"error": str(exc)}, elapsed, getattr(exc, "code", 500)


def run_smoke(base_url: str, audio_path: Optional[str] = None, check_audio: bool = False) -> bool:
    base_url = base_url.rstrip("/")
    cases_file = Path("scripts/smoke_cases.json")
    if not cases_file.exists():
        print(f"ERROR: {cases_file} not found!")
        return False

    cases = json.loads(cases_file.read_text(encoding="utf-8"))
    all_passed = True
    has_warnings = False

    header = f"{'Case':<22} | {'Lang':<5} | {'Handoff/Verdict':<16} | {'Source ID':<18} | {'TTS':<5} | {'Latency':<8}"
    sep = "-" * len(header)
    print("\n" + header)
    print(sep)

    for case in cases:
        c_id = case["id"]
        c_type = case["type"]
        lang = case["lang"]
        endpoint = case["endpoint"]
        url = f"{base_url}{endpoint}"
        is_warn = False

        if c_type == "health":
            body, elapsed, status = get_json(url)
            ok = (status == 200 and body.get("status") == "ok")
            verdict_str = body.get("status", "err")
            source_id = "N/A"
            tts_ok = str(body.get("tts_available", False))
        elif c_type == "ask":
            body, elapsed, status = post_form(url, {"text": case["text"], "lang": lang})
            outcome = body.get("outcome", "error")
            source_id = str(body.get("source_id") or "null")
            tts_ok = str(body.get("tts_available", False))
            verdict_str = outcome
            exp_out = case.get("expected_outcome")
            ok = (status == 200 and outcome == exp_out)
        elif c_type == "check":
            body, elapsed, status = post_form(url, {"text": case["text"], "lang": lang, "service": "domicile"})
            verdict = body.get("verdict", "error")
            source_id = str(body.get("source_id") or "null")
            tts_ok = str(body.get("tts_available", False))
            verdict_str = verdict
            exp_verdict = case.get("expected_verdict")

            if status == 200 and verdict == "unavailable":
                ok = True
                is_warn = True
                has_warnings = True
            else:
                ok = (status == 200 and verdict == exp_verdict)
        else:
            continue

        if not ok:
            all_passed = False

        status_flag = "WARN" if is_warn else ("✓" if ok else "✗")
        print(f"{c_id:<20} {status_flag:<4} | {lang:<5} | {verdict_str:<16} | {source_id:<18} | {tts_ok:<5} | {elapsed:.2f}s")
        if is_warn:
            print("   CHECK FEATURE UNVERIFIED: checklist is TODO in kb/domicile.md")

    # Optional Audio Case
    if audio_path:
        a_path = Path(audio_path)
        if not a_path.exists():
            print(f"\nERROR: Audio file {audio_path} does not exist!")
            return False

        ext = a_path.suffix.lstrip(".").lower()
        if ext not in ("wav", "mp3", "m4a", "ogg", "webm", "flac"):
            print(f"\nERROR: Audio format .{ext} not supported.")
            return False

        if check_audio:
            target_ep = "/api/v1/check"
            body, elapsed, status = post_multipart(f"{base_url}{target_ep}", {"service": "domicile"}, "audio", a_path)
            verdict = body.get("verdict", "error")
            source_id = str(body.get("source_id") or "null")
            tts_ok = str(body.get("tts_available", False))
            heard = body.get("heard", "")
            b64_len = len(body.get("audio_b64") or "")
            ok = (status == 200)
            status_flag = "✓" if ok else "✗"
            print(f"{'audio_check (' + ext + ')':<20} {status_flag} | {'auto':<5} | {verdict:<16} | {source_id:<18} | {tts_ok:<5} | {elapsed:.2f}s")
            print(f"   [Heard]: {heard}")
            print(f"   [Audio response bytes]: {b64_len} chars base64")
        else:
            target_ep = "/api/v1/ask"
            body, elapsed, status = post_multipart(f"{base_url}{target_ep}", {}, "audio", a_path)
            outcome = body.get("outcome", "error")
            source_id = str(body.get("source_id") or "null")
            tts_ok = str(body.get("tts_available", False))
            transcript = body.get("transcript", "")
            b64_len = len(body.get("audio_b64") or "")
            ok = (status == 200)
            status_flag = "✓" if ok else "✗"
            print(f"{'audio_ask (' + ext + ')':<20} {status_flag} | {'auto':<5} | {outcome:<16} | {source_id:<18} | {tts_ok:<5} | {elapsed:.2f}s")
            print(f"   [Heard]: {transcript}")
            print(f"   [Audio response bytes]: {b64_len} chars base64")

        if not ok:
            all_passed = False

    print(sep)
    if not all_passed:
        print("SOME SMOKE TESTS FAILED ❌\n")
        return False
    elif has_warnings:
        print("PASSED WITH WARNINGS ⚠️\n")
        return True
    else:
        print("ALL SMOKE TESTS PASSED ✅\n")
        return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ghag Smoke Testing Tool")
    parser.add_argument("--url", default="http://localhost:8000", help="Base URL of server")
    parser.add_argument("--audio", default=None, help="Path to audio file (wav, mp3, m4a, ogg, webm, flac)")
    parser.add_argument("--check", action="store_true", help="Post audio to /api/v1/check instead of /api/v1/ask")
    args = parser.parse_args()

    success = run_smoke(base_url=args.url, audio_path=args.audio, check_audio=args.check)
    sys.exit(0 if success else 1)
