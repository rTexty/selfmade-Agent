# Task 3: System Agent (Golang)

## Objective
The agent should be capable of communicating with a backend API using the `query_api` tool. This will require reading the `LMS_API_KEY` from `.env.docker.secret`.

## Tools
- `read_file(path string)`
- `list_files(path string)`
- `query_api(method string, path string, body string)`: Performs HTTP request to `AGENT_API_BASE_URL` (default `http://localhost:42002`). The HTTP header should inject the `X-API-Key` using `LMS_API_KEY`.

## Requirements
- Support GET and POST requests.
- Parse `body` as optional for GET.
- Load variables `AGENT_API_BASE_URL`, `LMS_API_KEY` additionally to LLM configurations.
- Verify agent performance via `run_eval.py`.

## Delivery
- Add tool block and tool implementation in `agent.go`.
- Write logic to proxy headers and serialize API response.
- Agent passes eval tests locally.
