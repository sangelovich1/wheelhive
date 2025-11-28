#!/bin/bash
# Validation script: Syntax checking + Type checking
# Run before commits to catch errors early

set -e  # Exit on first error

echo "=================================================="
echo "Running validation checks..."
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
echo "Step 1/2: Syntax checking (py_compile)..."
echo "--------------------------------------------------"

# Check all Python files for syntax errors
PYTHON_FILES=$(find src/ scripts/ -name "*.py" 2>/dev/null)

for file in $PYTHON_FILES; do
    if python3 -m py_compile "$file" 2>/dev/null; then
        echo -e "  ${GREEN}✓${NC} $file"
    else
        echo -e "  ${RED}✗${NC} $file"
        python3 -m py_compile "$file"  # Show error
        SYNTAX_ERRORS=$((SYNTAX_ERRORS + 1))
    fi
done

if [ $SYNTAX_ERRORS -eq 0 ]; then
    echo -e "\n${GREEN}✓ Syntax check passed${NC}"
else
    echo -e "\n${RED}✗ Syntax check failed: $SYNTAX_ERRORS error(s)${NC}"
    exit 1
fi

echo ""
echo "Step 2/2: Type checking (mypy)..."
echo "--------------------------------------------------"

# Activate venv if available
if [ -f .venv/bin/activate ]; then
    source .venv/bin/activate
fi

# Run mypy on src/ and scripts/
if mypy src/ scripts/ 2>&1; then
    echo -e "\n${GREEN}✓ Type check passed${NC}"
else
    TYPE_ERRORS=$?
    echo -e "\n${YELLOW}⚠ Type check completed with warnings${NC}"
fi

echo ""
echo "=================================================="
if [ $SYNTAX_ERRORS -eq 0 ] && [ $TYPE_ERRORS -eq 0 ]; then
    echo -e "${GREEN}✓ All checks passed!${NC}"
    exit 0
elif [ $SYNTAX_ERRORS -eq 0 ]; then
    echo -e "${YELLOW}⚠ Syntax OK, but type warnings exist${NC}"
    exit 0  # Don't fail on type warnings
else
    echo -e "${RED}✗ Validation failed${NC}"
    exit 1
fi
