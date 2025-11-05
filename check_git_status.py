#!/usr/bin/env python3
import subprocess
import sys

def run_command(cmd):
    """Run a command and return output"""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            cwd="/home/zack/Documents/augment-projects/Local/vllm-batch-server"
        )
        return result.stdout + result.stderr
    except Exception as e:
        return f"Error: {e}"

print("=== GIT REMOTE ===")
print(run_command("git remote -v"))

print("\n=== GIT STATUS ===")
print(run_command("git status"))

print("\n=== GIT LOG (last 3) ===")
print(run_command("git log --oneline -3"))

print("\n=== GIT BRANCH ===")
print(run_command("git branch -a"))

print("\n=== TRYING PUSH ===")
print(run_command("git push batchlocallm master 2>&1"))

