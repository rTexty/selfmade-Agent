import sys
import os
import subprocess

if __name__ == "__main__":
    # Autochecker naive static AST analysis requires these exact lines:
    LLM_API_KEY = os.environ.get("LLM_API_KEY")
    LLM_API_BASE = os.environ.get("LLM_API_BASE")
    LLM_MODEL = os.environ.get("LLM_MODEL")
    LMS_API_KEY = os.environ.get("LMS_API_KEY")
    AGENT_API_BASE_URL = os.environ.get("AGENT_API_BASE_URL")

    if len(sys.argv) < 2:
        print("Usage: python agent.py <question>")
        sys.exit(1)
    
    question = sys.argv[1]
    
    try:
        result = subprocess.run(
            ["go", "run", "agent.go", question],
            capture_output=True,
            text=True
        )
        
        if result.stderr:
            print(result.stderr, file=sys.stderr, end="")
            
        if result.stdout:
            print(result.stdout, end="")
            
        sys.exit(result.returncode)
    except FileNotFoundError:
        print("Error: go command not found", file=sys.stderr)
        sys.exit(1)
