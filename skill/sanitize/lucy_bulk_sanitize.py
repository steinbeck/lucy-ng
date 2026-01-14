#!/usr/bin/env python3
"""
Lucy Bulk Sanitize - Redact compound identifiers from Bruker NMR datasets.

This tool performs bulk text replacement across all text files in a dataset,
based on identifiers discovered by AI review.

Usage:
    # Single replacement
    python lucy_bulk_sanitize.py <path> --redact "Indigo"

    # Multiple replacements
    python lucy_bulk_sanitize.py <path> --redact "Indigo" --redact "CAS 482-89-3"

    # From a manifest file (one identifier per line)
    python lucy_bulk_sanitize.py <path> --manifest identifiers.txt

    # Custom replacement (default is "Unknown")
    python lucy_bulk_sanitize.py <path> --redact "Indigo" --replace-with "[REDACTED]"

    # Dry run (show what would be changed)
    python lucy_bulk_sanitize.py <path> --redact "Indigo" --dry-run

    # Delete files matching patterns
    python lucy_bulk_sanitize.py <path> --delete "*.mol" --delete "audita.txt"

Features:
    - Safe: Never modifies binary NMR data files
    - Thorough: Searches all text files recursively
    - Reported: Shows exactly what was changed
    - Case-insensitive option available
"""

import os
import sys
import re
import argparse
from pathlib import Path
from typing import List, Tuple, Optional, Set
from dataclasses import dataclass
import fnmatch


# Binary files to never modify (same as extractor)
BINARY_PATTERNS = {
    'fid', 'ser',
    '1r', '1i', '2rr', '2ri', '2ir', '2ii',
    '3rrr', '3rri', '3rir', '3rii',
    '3irr', '3iri', '3iir', '3iii',
}

BINARY_EXTENSIONS = {'.pdf', '.png', '.jpg', '.jpeg', '.gif', '.tiff', '.bmp'}


@dataclass
class Replacement:
    """Record of a replacement made."""
    filepath: str
    original: str
    replacement: str
    count: int
    line_numbers: List[int]


def is_binary_file(filepath: Path) -> bool:
    """Check if a file is binary (should not be modified)."""
    name = filepath.name.lower()

    if name in BINARY_PATTERNS:
        return True

    if filepath.suffix.lower() in BINARY_EXTENSIONS:
        return True

    try:
        with open(filepath, 'rb') as f:
            chunk = f.read(1024)
            if b'\x00' in chunk:
                return True
    except:
        return True

    return False


def read_file_safely(filepath: Path) -> Tuple[Optional[str], str]:
    """Read file with encoding detection. Returns (content, encoding)."""
    encodings = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']

    for encoding in encodings:
        try:
            with open(filepath, 'r', encoding=encoding) as f:
                content = f.read()
                return content, encoding
        except (UnicodeDecodeError, UnicodeError):
            continue
        except Exception:
            return None, ''

    return None, ''


def find_occurrences(content: str, pattern: str, case_insensitive: bool = False) -> List[int]:
    """Find all line numbers where pattern occurs."""
    lines = content.split('\n')
    matches = []

    flags = re.IGNORECASE if case_insensitive else 0
    regex = re.compile(re.escape(pattern), flags)

    for i, line in enumerate(lines, 1):
        if regex.search(line):
            matches.append(i)

    return matches


def replace_in_content(content: str, pattern: str, replacement: str,
                       case_insensitive: bool = False) -> Tuple[str, int]:
    """Replace pattern in content. Returns (new_content, count)."""
    flags = re.IGNORECASE if case_insensitive else 0
    regex = re.compile(re.escape(pattern), flags)

    new_content, count = regex.subn(replacement, content)
    return new_content, count


def sanitize_file(filepath: Path, patterns: List[str], replacement: str,
                  case_insensitive: bool, dry_run: bool) -> List[Replacement]:
    """Sanitize a single file. Returns list of replacements made."""
    if is_binary_file(filepath):
        return []

    content, encoding = read_file_safely(filepath)
    if content is None:
        return []

    replacements = []
    modified_content = content
    any_changes = False

    for pattern in patterns:
        line_numbers = find_occurrences(modified_content, pattern, case_insensitive)

        if line_numbers:
            new_content, count = replace_in_content(
                modified_content, pattern, replacement, case_insensitive
            )

            if count > 0:
                replacements.append(Replacement(
                    filepath=str(filepath),
                    original=pattern,
                    replacement=replacement,
                    count=count,
                    line_numbers=line_numbers
                ))
                modified_content = new_content
                any_changes = True

    if any_changes and not dry_run:
        try:
            with open(filepath, 'w', encoding=encoding) as f:
                f.write(modified_content)
        except Exception as e:
            print(f"  Warning: Could not write {filepath}: {e}", file=sys.stderr)

    return replacements


def delete_files(dataset_path: Path, patterns: List[str], dry_run: bool) -> List[str]:
    """Delete files matching patterns. Returns list of deleted files."""
    deleted = []

    for filepath in dataset_path.rglob('*'):
        if not filepath.is_file():
            continue

        for pattern in patterns:
            if fnmatch.fnmatch(filepath.name, pattern):
                deleted.append(str(filepath.relative_to(dataset_path)))
                if not dry_run:
                    try:
                        filepath.unlink()
                    except Exception as e:
                        print(f"  Warning: Could not delete {filepath}: {e}",
                              file=sys.stderr)
                break

    return deleted


def load_manifest(manifest_path: Path) -> List[str]:
    """Load identifiers from a manifest file (one per line)."""
    patterns = []
    with open(manifest_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                patterns.append(line)
    return patterns


def main():
    parser = argparse.ArgumentParser(
        description='Bulk sanitize Bruker NMR datasets',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Redact a compound name
    %(prog)s ./dataset --redact "Caffeine"

    # Redact multiple identifiers
    %(prog)s ./dataset --redact "Indigo" --redact "CAS 482-89-3" --redact "Classics_Indigo"

    # Use a manifest file
    %(prog)s ./dataset --manifest identifiers_to_redact.txt

    # Delete structure files
    %(prog)s ./dataset --delete "*.mol" --delete "*.sdf"

    # Preview changes without applying
    %(prog)s ./dataset --redact "Indigo" --dry-run

    # Case-insensitive replacement
    %(prog)s ./dataset --redact "indigo" --ignore-case

This tool is designed to work with the AI-assisted sanitization workflow:
1. Run lucy_text_extractor.py to review all text content
2. AI identifies compound names and identifiers
3. Run this tool to redact those identifiers
4. Run extractor again to verify sanitization
        """
    )

    parser.add_argument('path', help='Path to Bruker dataset')
    parser.add_argument('--redact', '-r', action='append', default=[],
                        help='String to redact (can specify multiple times)')
    parser.add_argument('--manifest', '-m',
                        help='File containing identifiers to redact (one per line)')
    parser.add_argument('--replace-with', default='Unknown',
                        help='Replacement string (default: "Unknown")')
    parser.add_argument('--delete', '-d', action='append', default=[],
                        help='File pattern to delete (e.g., "*.mol")')
    parser.add_argument('--ignore-case', '-i', action='store_true',
                        help='Case-insensitive matching')
    parser.add_argument('--dry-run', '-n', action='store_true',
                        help='Show what would be done without making changes')

    args = parser.parse_args()

    dataset_path = Path(args.path)
    if not dataset_path.exists():
        print(f"Error: Path does not exist: {dataset_path}", file=sys.stderr)
        return 1

    # Collect all patterns to redact
    patterns = list(args.redact)
    if args.manifest:
        manifest_path = Path(args.manifest)
        if not manifest_path.exists():
            print(f"Error: Manifest file not found: {manifest_path}", file=sys.stderr)
            return 1
        patterns.extend(load_manifest(manifest_path))

    if not patterns and not args.delete:
        print("Error: No patterns to redact. Use --redact or --manifest", file=sys.stderr)
        return 1

    if args.dry_run:
        print("=" * 60)
        print("DRY RUN - No changes will be made")
        print("=" * 60)

    print(f"\nDataset: {dataset_path.absolute()}")
    print(f"Patterns to redact: {patterns}")
    print(f"Replacement: '{args.replace_with}'")
    if args.delete:
        print(f"Files to delete: {args.delete}")
    print()

    # Perform text replacements
    all_replacements: List[Replacement] = []

    if patterns:
        print("Scanning text files...")
        for filepath in sorted(dataset_path.rglob('*')):
            if filepath.is_file():
                replacements = sanitize_file(
                    filepath, patterns, args.replace_with,
                    args.ignore_case, args.dry_run
                )
                all_replacements.extend(replacements)

    # Delete files
    deleted_files: List[str] = []
    if args.delete:
        print("\nDeleting files...")
        deleted_files = delete_files(dataset_path, args.delete, args.dry_run)

    # Report results
    print("\n" + "=" * 60)
    print("SANITIZATION REPORT")
    print("=" * 60)

    if all_replacements:
        print("\nText Replacements:")
        # Group by pattern
        by_pattern = {}
        for r in all_replacements:
            if r.original not in by_pattern:
                by_pattern[r.original] = []
            by_pattern[r.original].append(r)

        for pattern, replacements in by_pattern.items():
            total = sum(r.count for r in replacements)
            print(f"\n  '{pattern}' → '{args.replace_with}'")
            print(f"  Total occurrences replaced: {total}")
            print(f"  Files affected:")
            for r in replacements:
                rel_path = Path(r.filepath).relative_to(dataset_path)
                print(f"    - {rel_path} ({r.count}x, lines: {r.line_numbers[:5]}{'...' if len(r.line_numbers) > 5 else ''})")
    else:
        if patterns:
            print("\nNo text replacements made (patterns not found)")

    if deleted_files:
        print(f"\nFiles Deleted ({len(deleted_files)}):")
        for f in deleted_files:
            print(f"  - {f}")
    elif args.delete:
        print("\nNo files matched deletion patterns")

    print("\n" + "=" * 60)

    if args.dry_run:
        print("DRY RUN COMPLETE - No changes were made")
        print("Remove --dry-run flag to apply changes")
    else:
        print("SANITIZATION COMPLETE")
        print("\nNext steps:")
        print("1. Run lucy_text_extractor.py again to verify no identifiers remain")
        print("2. Use a fresh AI instance for CASE analysis")
        print("3. Provide molecular formula separately (simulating HRMS)")

    return 0


if __name__ == '__main__':
    sys.exit(main())
