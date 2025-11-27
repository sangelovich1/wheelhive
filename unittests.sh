#!/bin/bash

# Parse command-line arguments
COVERAGE=false
for arg in "$@"; do
    if [[ "$arg" == "--coverage" ]]; then
        COVERAGE=true
    fi
done

source .bot_venv/bin/activate

if [ "$COVERAGE" = true ]; then
    echo "Running tests with code coverage..."
    python -m coverage run -m unittest discover -s tests -p '*_test.py' -v 2>&1 | tee unittests.txt
    echo ""
    echo "Generating coverage report..."
    python -m coverage report -m
    echo ""
    echo "Generating HTML coverage report..."
    python -m coverage html
    echo "HTML coverage report generated in htmlcov/index.html"
else
    python -m unittest discover -s tests -p *_test.py -v 2>&1 | tee unittests.txt
fi
