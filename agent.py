import sys
import os
import json
import urllib.request
import urllib.error
from urllib.error import HTTPError

def read_file(path: str) -> str:
    if ".." in path or path.startswith("/"):
        return "Error: Path traversal not allowed"
    full_path = os.path.join(os.getcwd(), path)
    if not os.path.exists(full_path) or not os.path.isfile(full_path):
        return f"Error: File {path} not found"
    try:
        with open(full_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {e}"

def list_files(path: str) -> str:
    if ".." in path or path.startswith("/"):
        return "Error: Path traversal not allowed"
    if path == ".":
        path = ""
    full_path = os.path.join(os.getcwd(), path)
    if not os.path.exists(full_path) or not os.path.isdir(full_path):
        return f"Error: Directory '{path}' not found"
    try:
        entries = os.listdir(full_path)
        return "\n".join(entries)
    except Exception as e:
        return f"Error listing directory: {e}"

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
        with urllib.request.urlopen(req) as response:
            resp_body = response.read().decode("utf-8")
            status = response.getcode()
            return json.dumps({"status_code": status, "body": resp_body})
    except HTTPError as e:
        resp_body = e.read().decode("utf-8")
        return json.dumps({"status_code": e.code, "body": resp_body})
    except Exception as e:
        return f"Error: {e}"

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a file from the project repository. Returns file contents as a string. Path must be relative from project root.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "relative path from project root"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files and directories at a given path. Returns newline-separated listing of entries. Path must be relative from project root.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "relative directory path from project root"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_api",
            "description": "Call the deployed backend API.",
            "parameters": {
                "type": "object",
                "properties": {
                    "method": {"type": "string", "description": "HTTP method (GET, POST, etc.)"},
                    "path": {"type": "string", "description": "API path (e.g., /items/)"},
                    "body": {"type": "string", "description": "JSON request body (optional)"}
                },
                "required": ["method", "path"]
            }
        }
    }
]

def main():
    if len(sys.argv) < 2:
        print("Usage: python agent.py <question>")
        sys.exit(1)

    question = sys.argv[1]

    LLM_API_KEY = os.environ.get("LLM_API_KEY")
    LLM_API_BASE = os.environ.get("LLM_API_BASE", "").rstrip("/")
    LLM_MODEL = os.environ.get("LLM_MODEL")

    sys_prompt = "You are a helpful programming assistant. You have tools: read_file, list_files, query_api. For documentation look in 'wiki/'. Answer the question based on the tools."

    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": question}
    ]

    exec_tool_calls_log = []
    
    url = f"{LLM_API_BASE}/chat/completions" if LLM_API_BASE else "https://api.openai.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LLM_API_KEY}"
    }

    content = ""
    source = None

    for step in range(10):
        req_data = {
            "model": LLM_MODEL,
            "messages": messages,
            "tools": TOOLS,
            "tool_choice": "auto"
        }
        
        req = urllib.request.Request(url, data=json.dumps(req_data).encode("utf-8"), headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req) as response:
                resp_json = json.loads(response.read().decode("utf-8"))
        except Exception as e:
            print(f"Error calling LLM APIs: {e}", file=sys.stderr)
            sys.exit(1)
            
        choice = resp_json.get("choices", [{}])[0].get("message", {})
        if not choice:
            break
            
        content = choice.get("content") or ""
        tool_calls = choice.get("tool_calls", [])
        
        choice_to_append = {"role": "assistant"}
        if choice.get("content"): choice_to_append["content"] = choice["content"]
        if tool_calls: choice_to_append["tool_calls"] = tool_calls
        if not choice.get("content"): choice_to_append["content"] = ""
        
        messages.append(choice_to_append)
        
        if not tool_calls:
            break
            
        for tc in tool_calls:
            func_name = tc.get("function", {}).get("name")
            args_str = tc.get("function", {}).get("arguments", "{}")
            
            try:
                args = json.loads(args_str)
            except:
                args = {}
                
            res_str = ""
            if func_name == "read_file":
                res_str = read_file(args.get("path", ""))
                # Track source
                if "wiki/" in args.get("path", ""):
                    source = args.get("path", "")
            elif func_name == "list_files":
                res_str = list_files(args.get("path", ""))
            elif func_name == "query_api":
                res_str = query_api(args.get("method", "GET"), args.get("path", "/"), args.get("body"))
            else:
                res_str = f"Error: unknown tool {func_name}"
                
            exec_tool_calls_log.append({
                "tool": func_name,
                "args": args,
                "result": res_str[:2000] # truncate
            })
            
            messages.append({
                "role": "tool",
                "tool_call_id": tc.get("id"),
                "name": func_name,
                "content": res_str
            })

    output = {
        "answer": content,
        "tool_calls": exec_tool_calls_log
    }
    
    if source:
        output["source"] = source
        
    print(json.dumps(output))

if __name__ == "__main__":
    main()
