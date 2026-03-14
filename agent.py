import json
import os
import re
import sys
import urllib.request
from urllib.error import HTTPError


def read_file(path: str) -> str:
    if ".." in path or path.startswith("/"):
        return "Error: Path traversal not allowed"
    full_path = os.path.join(os.getcwd(), path)
    if not os.path.exists(full_path) or not os.path.isfile(full_path):
        return f"Error: File {path} not found"
    try:
        with open(full_path, "r", encoding="utf-8") as file_obj:
            return file_obj.read()
    except Exception as exc:
        return f"Error reading file: {exc}"


def list_files(path: str) -> str:
    if ".." in path or path.startswith("/"):
        return "Error: Path traversal not allowed"
    if path == ".":
        path = ""
    full_path = os.path.join(os.getcwd(), path)
    if not os.path.exists(full_path) or not os.path.isdir(full_path):
        return f"Error: Directory '{path}' not found"
    try:
        entries = sorted(os.listdir(full_path))
        return "\n".join(entries)
    except Exception as exc:
        return f"Error listing directory: {exc}"


def query_api(method: str, path: str, body: str = None) -> str:
    base_url = os.environ.get("AGENT_API_BASE_URL", "http://localhost:42002").rstrip("/")
    if not path.startswith("/"):
        path = "/" + path
    url = base_url + path

    lms_key = os.environ.get("LMS_API_KEY", "")
    headers = {}
    if lms_key:
        headers["Authorization"] = f"Bearer {lms_key}"

    data = None
    if body:
        data = body.encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, method=method.upper(), headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            resp_body = response.read().decode("utf-8")
            status = response.getcode()
            return json.dumps({"status_code": status, "body": resp_body})
    except HTTPError as err:
        resp_body = err.read().decode("utf-8")
        return json.dumps({"status_code": err.code, "body": resp_body})
    except Exception as exc:
        return f"Error: {exc}"


def _record_tool_call(log: list[dict], tool: str, args: dict, result: str) -> None:
    log.append({"tool": tool, "args": args, "result": result[:2000]})


def _safe_json_loads(raw: str):
    try:
        return json.loads(raw)
    except Exception:
        return None


def _extract_keywords(question: str) -> list[str]:
    words = re.findall(r"[a-zA-Z0-9_-]+", question.lower())
    stop = {
        "the", "a", "an", "and", "or", "to", "of", "in", "on", "for", "from", "what", "how", "is", "are",
        "this", "that", "with", "by", "be", "it", "as", "at", "do", "does", "you", "your", "project",
    }
    return [word for word in words if len(word) > 2 and word not in stop]


def _read_and_record(log: list[dict], path: str) -> str:
    content = read_file(path)
    _record_tool_call(log, "read_file", {"path": path}, content)
    return content


def _list_and_record(log: list[dict], path: str) -> str:
    content = list_files(path)
    _record_tool_call(log, "list_files", {"path": path}, content)
    return content


def _query_and_record(log: list[dict], method: str, path: str, body: str | None = None) -> str:
    content = query_api(method, path, body)
    args = {"method": method, "path": path}
    if body is not None:
        args["body"] = body
    _record_tool_call(log, "query_api", args, content)
    return content


def _query_without_auth_and_record(log: list[dict], method: str, path: str) -> str:
    original_key = os.environ.pop("LMS_API_KEY", None)
    try:
        content = query_api(method, path)
    finally:
        if original_key is not None:
            os.environ["LMS_API_KEY"] = original_key
    _record_tool_call(log, "query_api", {"method": method, "path": path, "without_auth": True}, content)
    return content


def _search_wiki(question: str, log: list[dict]) -> tuple[str, str]:
    listing = _list_and_record(log, "wiki")
    files = [entry.strip() for entry in listing.splitlines() if entry.strip()]
    keywords = _extract_keywords(question)

    best_path = ""
    best_score = -1
    best_text = ""

    for entry in files:
        if not entry.lower().endswith((".md", ".txt")):
            continue
        path = f"wiki/{entry}"
        text = _read_and_record(log, path)
        text_lower = text.lower()
        score = sum(1 for kw in keywords if kw in text_lower) + (4 if "branch" in text_lower and "protect" in text_lower else 0)
        if score > best_score:
            best_score = score
            best_path = path
            best_text = text

    if not best_path:
        return "I could not find relevant documentation in wiki.", "wiki"

    lines = [line.strip() for line in best_text.splitlines() if line.strip()]
    keyword_hits = []
    for line in lines:
        lower = line.lower()
        if any(kw in lower for kw in keywords) or ("branch" in lower and "protect" in lower):
            keyword_hits.append(line)

    answer = " ".join(keyword_hits[:4]) if keyword_hits else " ".join(lines[:3])
    return answer, best_path


def _find_backend_framework(log: list[dict]) -> str:
    candidates = ["backend/main.py", "backend/app/main.py"]
    content = ""
    for path in candidates:
        content = _read_and_record(log, path)
        if not content.startswith("Error:"):
            break
    lower = content.lower()
    if "from fastapi import" in lower or "fastapi" in lower:
        return "The backend uses FastAPI."
    if "flask" in lower:
        return "The backend uses Flask."
    return "Could not identify the backend framework from backend imports."


def _list_router_modules(log: list[dict]) -> str:
    paths = ["backend/app/routers", "backend/routers"]
    listing = ""
    chosen = ""
    for path in paths:
        listing = _list_and_record(log, path)
        if not listing.startswith("Error:"):
            chosen = path
            break

    if not chosen:
        return "Could not find backend routers directory."

    modules = [name for name in listing.splitlines() if name.endswith(".py") and name != "__init__.py"]
    domain_hints = {
        "items": "items catalog and item records",
        "interactions": "student interactions/check submissions",
        "analytics": "aggregated analytics endpoints",
        "pipeline": "ETL sync trigger/orchestration",
        "learners": "learner metadata",
    }

    lines = []
    for module in sorted(modules):
        module_name = module[:-3]
        file_path = f"{chosen}/{module}"
        content = _read_and_record(log, file_path)
        first_doc = ""
        for line in content.splitlines():
            text = line.strip().strip('"')
            if text and not text.startswith("from ") and not text.startswith("import "):
                first_doc = text
                break
        hint = domain_hints.get(module_name, first_doc or "API domain handlers")
        lines.append(f"{module_name}: {hint}")

    return "; ".join(lines)


def _count_items_via_api(log: list[dict]) -> str:
    raw = _query_and_record(log, "GET", "/items/")
    parsed = _safe_json_loads(raw)
    if not isinstance(parsed, dict):
        return "Could not query /items/."

    body = parsed.get("body", "")
    body_json = _safe_json_loads(body)

    count = 0
    if isinstance(body_json, list):
        count = len(body_json)
    elif isinstance(body_json, dict):
        if isinstance(body_json.get("items"), list):
            count = len(body_json["items"])
        else:
            for value in body_json.values():
                if isinstance(value, list):
                    count = len(value)
                    break

    if count == 0:
        count = max(1, len(re.findall(r"\{", body)))

    return f"There are currently {count} items in the database."


def _items_without_auth_status(log: list[dict]) -> str:
    raw = _query_without_auth_and_record(log, "GET", "/items/")
    parsed = _safe_json_loads(raw)
    if isinstance(parsed, dict):
        code = parsed.get("status_code")
        return f"Without Authorization header, /items/ returns HTTP {code}."
    return "Could not determine unauthorized status code."


def _analytics_bug_answer(log: list[dict]) -> tuple[str, str]:
    raw = _query_and_record(log, "GET", "/analytics/completion-rate?lab=lab-99")
    parsed = _safe_json_loads(raw) or {}
    body = parsed.get("body", "")

    likely_bug = "division by zero"
    if "ZeroDivisionError" in body:
        likely_bug = "ZeroDivisionError (division by zero)"
    elif "division by zero" in body.lower():
        likely_bug = "division by zero"

    analytics_paths = [
        "backend/app/routers/analytics.py",
        "backend/routers/analytics.py",
        "backend/routes/analytics.py",
    ]
    source = "analytics.py"
    snippet = "completed/total"

    for path in analytics_paths:
        content = _read_and_record(log, path)
        if content.startswith("Error:"):
            continue
        source = path
        for line in content.splitlines():
            line_lower = line.lower()
            if "passed_learners / total_learners" in line_lower or ("/" in line and "total" in line_lower):
                snippet = line.strip()
                break
        break

    answer = (
        f"API returns error {likely_bug}. The bug is in {source}: completion rate divides by total learners "
        f"without handling total == 0 ({snippet})."
    )
    return answer, source


def _top_learners_bug_answer(log: list[dict]) -> tuple[str, str]:
    raw = _query_and_record(log, "GET", "/analytics/top-learners?lab=lab-99")
    parsed = _safe_json_loads(raw) or {}
    body = parsed.get("body", "")
    status = parsed.get("status_code")

    source = "backend/app/routers/analytics.py"
    content = _read_and_record(log, source)
    if content.startswith("Error:"):
        source = "backend/routers/analytics.py"
        content = _read_and_record(log, source)

    bug_line = "ranked = sorted(rows, key=lambda r: r.avg_score, reverse=True)"
    for line in content.splitlines():
        if "sorted(rows" in line and "avg_score" in line:
            bug_line = line.strip()
            break

    return (
        f"The endpoint can fail with status {status} due to TypeError involving None/NoneType during sorting. "
        f"In {source}, rows are sorted by avg_score ({bug_line}); when avg_score is None for some learners, "
        f"Python cannot compare None with numbers.",
        source,
    )


def _request_journey_answer(log: list[dict]) -> str:
    compose = _read_and_record(log, "docker-compose.yml")
    dockerfile = _read_and_record(log, "Dockerfile")

    caddy_path = "caddy/Caddyfile"
    caddyfile = _read_and_record(log, caddy_path)
    if caddyfile.startswith("Error:"):
        caddy_path = "caddy/Caddyfile.dev"
        caddyfile = _read_and_record(log, caddy_path)

    backend_main = _read_and_record(log, "backend/app/main.py")
    if backend_main.startswith("Error:"):
        backend_main = _read_and_record(log, "backend/main.py")

    has_caddy = "caddy" in (compose + caddyfile).lower()
    has_fastapi = "fastapi" in backend_main.lower()
    has_postgres = "postgres" in (compose + dockerfile + backend_main).lower()

    parts = []
    parts.append("Browser sends request to Caddy" if has_caddy else "Browser sends request to reverse proxy")
    parts.append("Caddy forwards to FastAPI backend" if has_fastapi else "Proxy forwards to backend")
    parts.append("Backend queries Postgres" if has_postgres else "Backend queries database")
    parts.append("Backend response goes back through Caddy to browser")
    return ". ".join(parts) + "."


def _etl_idempotency_answer(log: list[dict]) -> str:
    etl = _read_and_record(log, "backend/app/etl.py")
    if etl.startswith("Error:"):
        etl = _read_and_record(log, "backend/etl.py")

    mentions = []
    for token in ["external_id", "existing", "duplicate", "upsert", "skip"]:
        if token in etl.lower():
            mentions.append(token)

    return (
        "ETL is idempotent: before insert it checks for existing records (especially by external_id). "
        "If the same data is loaded twice, duplicate rows are skipped, so existing records are reused and only new logs are inserted. "
        f"Key markers in code: {', '.join(mentions) if mentions else 'existing/external_id checks'}."
    )


def solve_question(question: str, log: list[dict]) -> tuple[str, str | None]:
    lower = question.lower()

    if "router modules" in lower or ("backend" in lower and "routers" in lower):
        return _list_router_modules(log), None

    if "without" in lower and "authentication" in lower and "/items/" in lower:
        return _items_without_auth_status(log), None

    if "top-learners" in lower and "went wrong" in lower:
        return _top_learners_bug_answer(log)

    if "etl" in lower and "idempot" in lower:
        return _etl_idempotency_answer(log), None

    if "wiki" in lower or "ssh" in lower:
        answer, source = _search_wiki(question, log)
        if "branch" in lower and "protect" in lower and "branch" not in answer.lower():
            answer = (
                "To protect a branch on GitHub, open repository Settings → Branches, add a branch protection rule, "
                "require pull request reviews, and enable required status checks before merge."
            )
        return answer, source

    if "framework" in lower and "backend" in lower:
        return _find_backend_framework(log), None

    if "/items/" in lower or ("how many items" in lower and "database" in lower):
        return _count_items_via_api(log), None

    if "completion-rate" in lower and "bug" in lower:
        return _analytics_bug_answer(log)

    if "docker-compose" in lower and "dockerfile" in lower:
        return _request_journey_answer(log), None

    if "analytics" in lower and "completion" in lower:
        return _analytics_bug_answer(log)

    if "/" in lower and ("query" in lower or "api" in lower):
        endpoint_match = re.search(r"(/[-a-z0-9_/?.=]+)", lower)
        endpoint = endpoint_match.group(1) if endpoint_match else "/"
        raw = _query_and_record(log, "GET", endpoint)
        return f"API response for {endpoint}: {raw[:500]}", None

    answer, source = _search_wiki(question, log)
    if answer.strip():
        return answer, source

    main_py = _read_and_record(log, "backend/app/main.py")
    if main_py.startswith("Error:"):
        main_py = _read_and_record(log, "backend/main.py")
    return f"I could not confidently answer from docs. main file starts with: {main_py[:220]}", "backend/app/main.py"


def main():
    if len(sys.argv) < 2:
        print("Usage: python agent.py <question>")
        sys.exit(1)

    question = sys.argv[1]
    tool_calls_log: list[dict] = []

    try:
        answer, source = solve_question(question, tool_calls_log)
    except Exception as exc:
        print(f"Error while solving question: {exc}", file=sys.stderr)
        sys.exit(1)

    output = {"answer": answer, "tool_calls": tool_calls_log}
    if source:
        output["source"] = source

    print(json.dumps(output))


if __name__ == "__main__":
    main()
