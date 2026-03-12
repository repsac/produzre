#!/bin/bash
# Generate golden TSV files for drums tests
#
# This script regenerates all golden TSV files. Run this when you've
# intentionally changed the drums engine and verified the new output
# sounds correct.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$REPO_ROOT"

echo "========================================"
echo "Generating Golden TSV Files"
echo "========================================"
echo ""
echo "This will regenerate all golden files."
echo "Make sure you've verified the new output sounds correct!"
echo ""
read -p "Continue? (y/N) " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled."
    exit 0
fi

echo ""
echo "Regenerating golden files..."
python tests/test_golden_drums.py --regenerate

exit_code=$?

if [ $exit_code -eq 0 ]; then
    echo ""
    echo "========================================"
    echo "Golden files regenerated successfully!"
    echo "========================================"
    echo ""
    echo "Next steps:"
    echo "  1. Review the changes: git diff tests/golden/"
    echo "  2. Run tests: python tests/test_golden_drums.py"
    echo "  3. Commit if correct: git add tests/golden/ && git commit"
else
    echo ""
    echo "========================================"
    echo "Failed to regenerate golden files."
    echo "========================================"
fi

exit $exit_code
