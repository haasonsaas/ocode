#!/usr/bin/env python3
"""
Pre-commit hook to check for invalid escape sequences.
Usage: python scripts/check_escapes.py [files...]
"""

import argparse
import sys
import warnings


def check_file(filepath):
    """Check a single file for invalid escape sequences."""
    issues = []

    # Capture warnings
    def capture_warning(message, category, filename, lineno, file=None, line=None):
        if category is SyntaxWarning and "invalid escape sequence" in str(message):
            issues.append((lineno, str(message)))

    original_showwarning = warnings.showwarning
    warnings.showwarning = capture_warning
    warnings.simplefilter("always", SyntaxWarning)

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        # Compile to trigger warnings
        compile(content, filepath, "exec")

    except SyntaxError:
        # Skip files with syntax errors (not our concern here)
        pass
    except (OSError, UnicodeDecodeError):
        # Skip files that can't be read or decoded
        pass
    finally:
        warnings.showwarning = original_showwarning

    return issues


def main():
    parser = argparse.ArgumentParser(description="Check for invalid escape sequences")
    parser.add_argument("files", nargs="*", help="Files to check")
    args = parser.parse_args()

    if not args.files:
        print("No files provided")
        return 0

    total_issues = 0

    for filepath in args.files:
        if not filepath.endswith(".py"):
            continue

        issues = check_file(filepath)
        if issues:
            print(f"{filepath}:")
            for line_num, message in issues:
                print(f"  Line {line_num}: {message}")
            total_issues += len(issues)

    if total_issues > 0:
        print(f"\n❌ Found {total_issues} invalid escape sequences")
        print("Fix these by using raw strings (r'...') for regex patterns")
        print("or properly escaping backslashes in regular strings")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
