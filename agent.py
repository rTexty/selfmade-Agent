import sys
import subprocess

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python agent.py <question>")
        sys.exit(1)
    
    question = sys.argv[1]
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
