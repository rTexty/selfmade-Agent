# Task 2: Documentation Agent (Golang)

## Objective
Enhance the basic agent with an agentic loop to allow it to read local project files using tools (`read_file` and `list_files`). Limit execution to a maximum of 10 tool calls per question. Add security checks to prevent reading files outside the project root (`../` traversal).

## Tools
- `read_file(path string)`: Reads a file and returns its content.
- `list_files(path string)`: Lists directory contents.

## Agentic Loop
1. Agent sends prompt + system message (or instructions) with tools definitions to the LLM.
2. If LLM returns tool calls, execute them.
3. Append results to conversation format (`role: tool` or similar matching messages format).
4. Iterate until LLM answers the question, hit 10 iterations max.
5. Final output includes `source` (link/reference or text showing where it got the answer), `answer`, and the tracked list of `tool_calls`.

## Output JSON
```json
{
  "answer": "...",
  "source": "wiki/...",
  "tool_calls": [
    { "name": "read_file", "arguments": { "path": "wiki/api.md" } }
  ]
}
```

## Security Constraints
Ensure `path` is sanitized before passing to `os.ReadFile` or `os.ReadDir`. It must strictly reside within the current working directory boundary.

## Testing
- `agent_test.go`: Add tests hitting the boundary checks (dir traversal).
- Integration test ensuring tools loop executes correctly.

