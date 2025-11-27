#!/bin/bash
# Validation script: Syntax checking + Type checking
# Run before commits to catch errors early

set -e  # Exit on first error

echo "=================================================="
echo "🔍 Running validation checks..."
echo "=================================================="

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Track overall status
SYNTAX_ERRORS=0
TYPE_ERRORS=0

echo ""
echo "📝 Step 1/2: Syntax checking (py_compile)..."
echo "--------------------------------------------------"

# Check all Python files for syntax errors
# Priority: Entry points and core modules
PRIORITY_FILES=(
    "src/bot.py"
    "src/cli.py"
    "src/mcp/mcp_server.py"
)

OTHER_FILES=(
    $(find src/ -name "*.py" ! -name "*_test.py" ! -path "src/bot.py" ! -path "src/cli.py" ! -path "src/mcp/mcp_server.py")
    $(find scripts/ -name "*.py")
)

echo "Checking priority files first..."
for file in "${PRIORITY_FILES[@]}"; do
    if [ -f "$file" ]; then
        if python3 -m py_compile "$file" 2>/dev/null; then
            echo -e "  ${GREEN}✓${NC} $file"
        else
            echo -e "  ${RED}✗${NC} $file"
            python3 -m py_compile "$file"  # Show error
            SYNTAX_ERRORS=$((SYNTAX_ERRORS + 1))
        fi
    fi
done

echo ""
echo "Checking remaining files..."
for file in "${OTHER_FILES[@]}"; do
    if [ -f "$file" ]; then
        if python3 -m py_compile "$file" 2>/dev/null; then
            echo -e "  ${GREEN}✓${NC} $file"
        else
            echo -e "  ${RED}✗${NC} $file"
            python3 -m py_compile "$file"  # Show error
            SYNTAX_ERRORS=$((SYNTAX_ERRORS + 1))
        fi
    fi
done

if [ $SYNTAX_ERRORS -eq 0 ]; then
    echo -e "\n${GREEN}✓ Syntax check passed${NC}"
else
    echo -e "\n${RED}✗ Syntax check failed: $SYNTAX_ERRORS error(s)${NC}"
    exit 1
fi

echo ""
echo "🔬 Step 2/2: Type checking (mypy)..."
echo "--------------------------------------------------"

# Activate venv if available (mypy is installed there)
if [ -f .bot_venv/bin/activate ]; then
    source .bot_venv/bin/activate
fi

# Run mypy on src/ and scripts/
if mypy src/ scripts/ --no-error-summary 2>&1; then
    echo -e "\n${GREEN}✓ Type check passed${NC}"
else
    TYPE_ERRORS=$?
    echo -e "\n${YELLOW}⚠ Type check completed with warnings/errors${NC}"
    echo ""
    echo "Run 'mypy src/ scripts/' for detailed output"
fi

echo ""
echo "=================================================="
if [ $SYNTAX_ERRORS -eq 0 ] && [ $TYPE_ERRORS -eq 0 ]; then
    echo -e "${GREEN}✓ All checks passed!${NC}"
    exit 0
elif [ $SYNTAX_ERRORS -eq 0 ]; then
    echo -e "${YELLOW}⚠ Syntax OK, but type warnings exist${NC}"
    exit 0  # Don't fail on type warnings, just notify
else
    echo -e "${RED}✗ Validation failed${NC}"
    exit 1
fi
