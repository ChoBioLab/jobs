#!/usr/bin/env bash
# minerva-connect.sh — open the tunnel to the Minerva vLLM server.
# Usage:  ./minerva-connect.sh [EXEC_HOST]
# Keep this terminal open while using OpenCode. Ctrl-C to close.
set -euo pipefail

NODE="${1:-}"

# If no node was given, ask LSF where the vLLM job is running.
if [ -z "$NODE" ]; then
  NODE=$(ssh minerva "bjobs -w 2>/dev/null | grep -w vllm-qwen | grep -w RUN" |
    head -1 | awk '{print $7}' | sed 's/.*\*//')
fi

if [ -z "$NODE" ]; then
  echo "ERROR: no RUNNING vllm-qwen job found." >&2
  echo "Ask an operator to start the server, then try again." >&2
  echo "(If auto-detect failed, pass the node: ./minerva-connect.sh lg05e17)" >&2
  exit 1
fi

echo "vLLM server node: $NODE"

# Authenticate to the login node once (Sinai password + Azure MFA).
ssh -MNf -o ControlPersist=8h minerva

# Two-hop tunnel:  laptop:8000 -> login:8000 -> compute node:8000
# The login->node leg MUST run ON the login node, hence the nested ssh.
echo "Opening tunnel (leave this window open) ..."
ssh -t -L 8000:localhost:8000 minerva \
  "ssh -L 8000:localhost:8000 tastac01@$NODE"
