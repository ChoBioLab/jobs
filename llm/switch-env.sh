#!/usr/bin/env bash
# switch-env.sh - Switch between different VLLM deployment environments

set -euo pipefail

# Default values
ENVIRONMENT=""
MODEL=""
GPU=""
HELP=false

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --environment|-e)
            ENVIRONMENT="$2"
            shift 2
            ;;
        --model|-m)
            MODEL="$2"
            shift 2
            ;;
        --gpu|-g)
            GPU="$2"
            shift 2
            ;;
        --help|-h)
            HELP=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Show help if requested
if [[ "$HELP" == true ]]; then
    cat << EOF
Usage: $0 [OPTIONS]

Switch between different VLLM deployment environments.

Options:
  -e, --environment    Environment to switch to (minerva|minimus|dev)
  -m, --model          Model to use (qwen3-coder-30b|qwen3-coder-14b|qwen3-coder-7b)
  -g, --gpu            GPU type (h100nvl|l40s|a6000|b200)
  -h, --help           Show this help message

Examples:
  $0 --environment=minerva --model=qwen3-coder-30b
  $0 --environment=minimus --model=qwen3-coder-14b --gpu=a6000
EOF
    exit 0
fi

# Validate environment
if [[ -z "$ENVIRONMENT" ]]; then
    echo "Error: Environment must be specified"
    echo "Usage: $0 --environment=minerva|minimus|dev"
    exit 1
fi

# Validate environment
if [[ "$ENVIRONMENT" != "minerva" && "$ENVIRONMENT" != "minimus" && "$ENVIRONMENT" != "dev" ]]; then
    echo "Error: Invalid environment. Must be minerva, minimus, or dev"
    exit 1
fi

# Determine which configuration file to use
CONFIG_FILE=""
case "$ENVIRONMENT" in
    "minerva")
        CONFIG_FILE="minerva.json"
        ;;
    "minimus")
        CONFIG_FILE="minimus.json"
        ;;
    "dev")
        CONFIG_FILE="dev.json"
        ;;
esac

# Check if configuration file exists
if [[ ! -f "$CONFIG_FILE" ]]; then
    echo "Error: Configuration file $CONFIG_FILE not found"
    echo "Please create it first"
    exit 1
fi

# Copy the appropriate configuration file to opencode.json
echo "Switching to environment: $ENVIRONMENT"
cp "$CONFIG_FILE" opencode.json

# Show current configuration
echo "Configuration switched to:"
jq '.model' opencode.json

# Show environment-specific instructions
case "$ENVIRONMENT" in
    "minerva")
        echo "For Minerva HPC, ensure you run:"
        echo "  ./minerva-llm-connect.sh"
        echo "Then start OpenCode"
        ;;
    "minimus")
        echo "For Minimus, ensure the local vLLM instance is running on port 8001"
        echo "Then start OpenCode"
        ;;
    "dev")
        echo "For development, ensure the local vLLM instance is running on port 8002"
        echo "Then start OpenCode"
        ;;
esac

echo "Configuration updated successfully!"