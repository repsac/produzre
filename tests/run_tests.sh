#!/bin/bash
# Test runner for Produzre golden TSV tests

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$REPO_ROOT"

echo "========================================"
echo "Produzre Golden TSV Tests"
echo "========================================"
echo ""

# Run golden drums tests
python tests/test_golden_drums.py "$@"

exit_code=$?

if [ $exit_code -eq 0 ]; then
    echo ""
    echo "========================================"
    echo "All tests passed!"
    echo "========================================"
else
    echo ""
    echo "========================================"
    echo "Tests failed. See output above."
    echo "========================================"
fi

exit $exit_code
