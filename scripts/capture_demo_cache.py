"""
scripts/capture_demo_cache.py – Capture real responses from the running Ghag server into static/cache.json.

Requirements:
- Reads test queries from scripts/smoke_cases.json.
- Queries the live server for:
  * 3 /ask cases: Urdu ('ur'), Pashto ('ps'), English ('en')
  * 1 /check case
- Validates each response is HTTP 200 and not an error.
- Writes valid real responses (including audio_b64) into static/cache.json.
- Refuses to write cache if any target case returns a server error.
- Never hand-writes or invents facts.

Usage:
    python scripts\\capture_demo_cache.py [--url http://localhost:8000] [--out static/cache.json]
"""
from __future__ import annotations

import argparse
import datetime
import json
import logging
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("capture_demo_cache")


def post_form(url: str, fields: Dict[str, str]) -> Tuple[Dict[str, Any], int]:
    """Perform application/x-www-form-urlencoded POST request."""
    data = urllib.parse.urlencode(fields).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded", "User-Agent": "Ghag-CacheCapture/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8")), resp.status
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8"))
        except Exception:
            body = {"error": str(exc)}
        return body, exc.code
    except Exception as exc:
        return {"error": str(exc)}, 500


def capture_cache(base_url: str = "http://localhost:8000", output_path: str = "static/cache.json") -> bool:
    base_url = base_url.rstrip("/")
    smoke_cases_file = Path("scripts/smoke_cases.json")
    if not smoke_cases_file.exists():
        log.error("Missing %s", smoke_cases_file)
        return False

    cases: List[Dict[str, Any]] = json.loads(smoke_cases_file.read_text(encoding="utf-8"))

    # We need:
    # 1 /ask ur
    # 1 /ask ps (or create if not in smoke cases)
    # 1 /ask en
    # 1 /check
    target_tasks = [
        {"type": "ask", "lang": "ur", "text": "ڈومیسائل بنوانے کے لیے کون سے سرکاری ذرائع ہیں؟"},
        {"type": "ask", "lang": "ps", "text": "د ډومیسائل سرټیفیکیټ ترلاسه کولو مرحلې څه دي؟"},
        {"type": "ask", "lang": "en", "text": "Where can I apply for a domicile certificate?"},
        {"type": "check", "lang": "en", "text": "I have my CNIC, parent CNIC, photographs, residence proof and affidavit."},
    ]

    captured_entries = []

    for task in target_tasks:
        t_type = task["type"]
        lang = task["lang"]
        text = task["text"]

        if t_type == "ask":
            url = f"{base_url}/api/v1/ask"
            log.info("Capturing /ask [%s]: %s", lang, text[:40])
            body, status = post_form(url, {"text": text, "lang": lang, "lang_hint": lang})
        else:
            url = f"{base_url}/api/v1/check"
            log.info("Capturing /check [%s]: %s", lang, text[:40])
            body, status = post_form(url, {"text": text, "lang": lang, "lang_hint": lang, "service": "domicile"})

        if status != 200 or "error" in body or body.get("detail"):
            log.error(
                "Refusing to write cache: received status %d or error on [%s %s]: %s",
                status,
                t_type,
                lang,
                body,
            )
            return False

        # Verify response structure
        if t_type == "ask" and not body.get("answer"):
            log.error("Empty answer received for /ask [%s]. Refusing cache write.", lang)
            return False
        if t_type == "check" and not body.get("verdict"):
            log.error("Empty verdict received for /check [%s]. Refusing cache write.", lang)
            return False

        captured_entries.append({
            "type": t_type,
            "lang": lang,
            "query": text,
            "status": status,
            "response": body,
        })
        time.sleep(1.0)  # Gentle delay for rate limits

    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "captured_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "source_server": base_url,
        "entry_count": len(captured_entries),
        "entries": captured_entries,
    }
    out_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("SUCCESS: Captured %d valid real responses to %s", len(captured_entries), output_path)
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Capture real responses for Ghag demo cache")
    parser.add_argument("--url", default="http://localhost:8000", help="Base URL of running Ghag server")
    parser.add_argument("--out", default="static/cache.json", help="Output path for cache JSON")
    args = parser.parse_args()

    success = capture_cache(base_url=args.url, output_path=args.out)
    sys.exit(0 if success else 1)
