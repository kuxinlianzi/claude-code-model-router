#!/bin/bash
# Model Router Environment Setup Script
# This script helps you set up the model router with your API key.

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "========================================"
echo "  Model Router Setup"
echo "========================================"
echo ""

# Check if config.yaml exists
if [ ! -f "config.yaml" ]; then
    echo -e "${YELLOW}Warning: config.yaml not found.${NC}"
    echo "Copying config.example.yaml to config.yaml..."
    cp config.example.yaml config.yaml
fi

# Read current API key from config
CURRENT_KEY=$(grep "^  api_key:" config.yaml | sed 's/.*api_key: *"\(.*\)"/\1/')

if [ -z "$CURRENT_KEY" ] || [ "$CURRENT_KEY" = "" ]; then
    echo -e "${RED}No API key configured!${NC}"
    echo ""
    read -p "Enter your DashScope API key: " API_KEY

    if [ -z "$API_KEY" ]; then
        echo -e "${RED}API key cannot be empty.${NC}"
        exit 1
    fi

    # Update config file using Python for proper YAML editing
    python3 << EOF
import yaml

with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)

config['dashscope']['api_key'] = '''$API_KEY'''

with open('config.yaml', 'w') as f:
    yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
EOF

    echo -e "${GREEN}✓ API key configured successfully!${NC}"
else
    echo -e "${YELLOW}Current configuration:${NC}"
    echo "  API key: ${CURRENT_KEY:0:8}**** (hidden)"
    echo ""
    read -p "Do you want to change the API key? (y/N): " CHANGE_KEY
    if [[ "$CHANGE_KEY" =~ ^[Yy]$ ]]; then
        read -p "Enter new DashScope API key: " API_KEY

        if [ -z "$API_KEY" ]; then
            echo -e "${RED}API key cannot be empty.${NC}"
            exit 1
        fi

        python3 << EOF
import yaml

with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)

config['dashscope']['api_key'] = '''$API_KEY'''

with open('config.yaml', 'w') as f:
    yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
EOF

        echo -e "${GREEN}✓ API key updated!${NC}"
    else
        echo -e "${GREEN}✓ Using existing API key${NC}"
    fi
fi

echo ""
echo "========================================"
echo "  Configuration Complete!"
echo "========================================"
echo ""
echo "Your next steps:"
echo "  1. Review config.yaml and adjust other settings if needed"
echo "  2. Install Ollama and pull a judge model:"
echo "     ollama pull qwen3.5:2b"
echo "  3. Start the service:"
echo "     ./start_llm.sh"
echo ""
echo "Important:"
echo "  - config.yaml is NOT tracked in git (contains secrets)"
echo "  - Use MODEL_ROUTER_* environment variables for CI/CD deployments"
echo ""
