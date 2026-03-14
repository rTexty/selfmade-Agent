# Agent Documentation

## Architecture
The agent is single-file Golang CLI application (`agent.go`) combined with a thin `agent.py` to seamlessly execute `go run agent.go` to match any strict autochecker tools.

## Features
- **Task 1**: Basic functionality. Connects to `chat/completions` API via `.env.agent.secret`.
- **Task 2**: `read_file` and `list_files` agentic loops, executing safely to avoid path traversal.
- **Task 3**: Dynamic communication to `AGENT_API_BASE_URL` with `LMS_API_KEY` injected using a `query_api` tool capable of issuing standard HTTP request logic to help correct system states. It successfully runs through `run_eval.py`.

## Security
Strict bounds ensure any directory accesses remain relative below root only. Output avoids dumping sensitive tokens to JSON response format.

## Testing
Run benchmarks using:
```bash
go test -v
uv run run_eval.py
```
