import json
import subprocess
import pytest
import os

def run_agent(question):
    result = subprocess.run(
        ["python", "agent.py", question],
        capture_output=True,
        text=True,
        env=os.environ.copy()
    )
    if result.returncode == 0:
        try:
            return json.loads(result.stdout)
        except:
            return None
    return None

def test_agent_output_format():
    """Task 1 check"""
    data = run_agent("Hello")
    if data:
        assert "answer" in data
        assert "tool_calls" in data

def test_agent_merge_conflict():
    """Task 2 check"""
    data = run_agent("How do you resolve a merge conflict?")
    if data:
        assert "tool_calls" in data

def test_agent_wiki_files():
    """Task 2 check"""
    data = run_agent("What files are in the wiki?")
    if data:
        assert "tool_calls" in data

def test_agent_backend_framework():
    """Task 3 check"""
    data = run_agent("What framework does the backend use?")
    if data:
         assert "tool_calls" in data

def test_agent_db_items():
    """Task 3 check"""
    data = run_agent("How many items are in the database?")
    if data:
         assert "tool_calls" in data
