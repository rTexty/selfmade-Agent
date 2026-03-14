# Agent Documentation

## Architecture
The agent is a fully native Python CLI application (`agent.py`) without Go dependencies. It satisfies the strict AST autochecker natively and avoids subprocess wrapping overhead.

## Features
- **Task 1**: Basic functionality. Connects to `chat/completions` API via `.env.agent.secret`.
- **Task 2**: `read_file` and `list_files` agentic loops, executing safely to avoid path traversal.
- **Task 3**: Dynamic communication to `AGENT_API_BASE_URL` with `LMS_API_KEY` injected using a `query_api` tool capable of issuing standard HTTP request logic to help correct system states. It successfully runs through `run_eval.py`.

## Lessons Learned
Migrating to Python simplifies code alignment with the educational tests mapping and prevents AST bypass hacks. Using urllib keeps dependency weight low.

## Testing
Run benchmarks using:
```bash
uv run run_eval.py
pytest test_agent.py
```
