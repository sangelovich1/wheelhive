#!/bin/bash
# Run unit tests with optional coverage

# Parse command-line arguments
COVERAGE=false
for arg in "$@"; do
    if [[ "$arg" == "--coverage" ]]; then
        COVERAGE=true
    fi
done

# Get script directory and set PYTHONPATH to src/
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
export PYTHONPATH="$SCRIPT_DIR/src:$PYTHONPATH"

# Activate venv if available
if [ -f .venv/bin/activate ]; then
    source .venv/bin/activate
fi

if [ "$COVERAGE" = true ]; then
    echo "Running tests with code coverage..."
    python -m coverage run -m unittest discover -s tests -p '*_test.py' -v
    echo ""
    echo "Coverage report:"
    python -m coverage report -m
    echo ""
    echo "HTML report: htmlcov/index.html"
    python -m coverage html
else
    python -m unittest discover -s tests -p '*_test.py' -v
fi
