#!/usr/bin/env python3
"""
Lucy Text Extractor - Extract all text content from Bruker NMR datasets for AI review.

This tool supports AI-assisted sanitization by presenting all text content
in a structured, reviewable format. The AI can then identify compound names
and other identifiers that need to be redacted.

Usage:
    python lucy_text_extractor.py <dataset_path>
    python lucy_text_extractor.py <dataset_path> --output report.txt
    python lucy_text_extractor.py <dataset_path> --json  # Machine-readable output

Output includes:
    - All text file contents, organized by file type
    - File paths (which may contain compound names)
    - Metadata from XML files
    - Parameter files (acqus, procs, etc.)

Binary files (fid, ser, 1r, 2rr, etc.) are automatically skipped.
"""

import os
import sys
import json
import argparse
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import re


# Known binary file patterns in Bruker datasets
BINARY_PATTERNS = {
    'fid', 'ser',                          # Raw FID data
    '1r', '1i', '2rr', '2ri', '2ir', '2ii',  # Processed real/imaginary
    '3rrr', '3rri', '3rir', '3rii',         # 3D data
    '3irr', '3iri', '3iir', '3iii',
}

# File extensions that are always binary
BINARY_EXTENSIONS = {'.pdf', '.png', '.jpg', '.jpeg', '.gif', '.tiff', '.bmp'}

# Known text file types in Bruker datasets
TEXT_FILE_CATEGORIES = {
    'title': 'Sample/Experiment Title',
    'acqus': 'Acquisition Parameters',
    'acqu2s': '2D Acquisition Parameters (F1)',
    'acqu3s': '3D Acquisition Parameters',
    'procs': 'Processing Parameters',
    'proc2s': '2D Processing Parameters',
    'pulseprogram': 'Pulse Program',
    'audita.txt': 'Acquisition Audit Log',
    'auditp.txt': 'Processing Audit Log',
    'peaklist.xml': 'Peak List (XML)',
    'integrals.txt': 'Integrals',
    'multiplet.txt': 'Multiplet Analysis',
}


def is_binary_file(filepath: Path) -> bool:
    """Check if a file is binary (should be skipped)."""
    name = filepath.name.lower()

    # Check known binary names
    if name in BINARY_PATTERNS:
        return True

    # Check extensions
    if filepath.suffix.lower() in BINARY_EXTENSIONS:
        return True

    # Check file content (look for null bytes)
    try:
        with open(filepath, 'rb') as f:
            chunk = f.read(1024)
            if b'\x00' in chunk:
                return True
    except:
        return True  # If we can't read it, skip it

    return False


def categorize_file(filepath: Path) -> str:
    """Categorize a file for organized output."""
    name = filepath.name

    if name in TEXT_FILE_CATEGORIES:
        return TEXT_FILE_CATEGORIES[name]
    elif name.endswith('.xml'):
        return 'XML File'
    elif name.endswith('.txt'):
        return 'Text File'
    elif name in ['acqus', 'acqu2s', 'acqu3s']:
        return 'Acquisition Parameters'
    elif name in ['procs', 'proc2s', 'proc3s']:
        return 'Processing Parameters'
    elif name == 'pulseprogram' or name == 'pulsprog':
        return 'Pulse Program'
    else:
        return 'Other Text'


def read_file_safely(filepath: Path) -> Optional[str]:
    """Read a file with multiple encoding fallbacks."""
    encodings = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']

    for encoding in encodings:
        try:
            with open(filepath, 'r', encoding=encoding) as f:
                return f.read()
        except (UnicodeDecodeError, UnicodeError):
            continue
        except Exception as e:
            return f"[Error reading file: {e}]"

    return "[Could not decode file with any known encoding]"


def extract_text_content(dataset_path: Path) -> Dict[str, List[dict]]:
    """
    Extract all text content from a Bruker dataset.

    Returns a dictionary organized by category, with each entry containing:
    - filepath: relative path to file
    - content: file content
    - size: file size in bytes
    """
    results = {}

    for filepath in sorted(dataset_path.rglob('*')):
        if not filepath.is_file():
            continue

        if is_binary_file(filepath):
            continue

        category = categorize_file(filepath)
        content = read_file_safely(filepath)

        if content is None:
            continue

        entry = {
            'filepath': str(filepath.relative_to(dataset_path)),
            'content': content,
            'size': filepath.stat().st_size,
        }

        if category not in results:
            results[category] = []
        results[category].append(entry)

    return results


def format_text_output(results: Dict[str, List[dict]], dataset_path: Path) -> str:
    """Format results for human/AI review."""
    lines = []

    lines.append("=" * 80)
    lines.append("LUCY TEXT EXTRACTOR - Content Report for AI Review")
    lines.append("=" * 80)
    lines.append(f"\nDataset: {dataset_path.absolute()}")
    lines.append(f"Directory name: {dataset_path.name}")
    lines.append("")

    # First, list all file paths (these might contain compound names!)
    lines.append("-" * 80)
    lines.append("FILE PATHS (check for compound names in paths)")
    lines.append("-" * 80)
    all_files = []
    for category, files in results.items():
        for f in files:
            all_files.append(f['filepath'])
    for fp in sorted(all_files):
        lines.append(f"  {fp}")
    lines.append("")

    # Then show content by category
    # Priority order for review
    priority_categories = [
        'Sample/Experiment Title',
        'Peak List (XML)',
        'Acquisition Audit Log',
        'Processing Audit Log',
        'Acquisition Parameters',
        'Processing Parameters',
    ]

    # Show priority categories first
    for category in priority_categories:
        if category in results:
            lines.append("-" * 80)
            lines.append(f"CATEGORY: {category}")
            lines.append("-" * 80)
            for entry in results[category]:
                lines.append(f"\n>>> File: {entry['filepath']}")
                lines.append(f">>> Size: {entry['size']} bytes")
                lines.append("")
                # Truncate very long files
                content = entry['content']
                if len(content) > 5000:
                    content = content[:5000] + "\n\n[... truncated, file continues ...]"
                lines.append(content)
                lines.append("")

    # Show remaining categories
    for category, files in sorted(results.items()):
        if category in priority_categories:
            continue

        lines.append("-" * 80)
        lines.append(f"CATEGORY: {category}")
        lines.append("-" * 80)
        for entry in files:
            lines.append(f"\n>>> File: {entry['filepath']}")
            lines.append(f">>> Size: {entry['size']} bytes")
            lines.append("")
            content = entry['content']
            if len(content) > 3000:
                content = content[:3000] + "\n\n[... truncated ...]"
            lines.append(content)
            lines.append("")

    lines.append("=" * 80)
    lines.append("END OF CONTENT REPORT")
    lines.append("=" * 80)
    lines.append("")
    lines.append("AI INSTRUCTIONS:")
    lines.append("Review the above content and identify:")
    lines.append("1. Compound names (chemical names, trade names, trivial names)")
    lines.append("2. Database identifiers (CAS numbers, PubChem IDs, ChEBI IDs)")
    lines.append("3. Sample/dataset names that reveal compound identity")
    lines.append("4. Any other information that could identify the compound")
    lines.append("")
    lines.append("Create a sanitization plan listing all strings to be redacted.")

    return "\n".join(lines)


def format_json_output(results: Dict[str, List[dict]], dataset_path: Path) -> str:
    """Format results as JSON for programmatic use."""
    output = {
        'dataset_path': str(dataset_path.absolute()),
        'directory_name': dataset_path.name,
        'categories': results,
        'all_filepaths': sorted([
            f['filepath']
            for files in results.values()
            for f in files
        ])
    }
    return json.dumps(output, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description='Extract text content from Bruker NMR datasets for AI review',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
This tool supports AI-assisted sanitization of NMR datasets.

The output presents all text content in a structured format that an AI
can review to identify compound names and other identifiers that need
to be redacted before blind CASE (Computer-Assisted Structure Elucidation).

Binary NMR data files (fid, 1r, 2rr, etc.) are automatically skipped.
        """
    )
    parser.add_argument('path', help='Path to Bruker dataset')
    parser.add_argument('--output', '-o', help='Output file (default: stdout)')
    parser.add_argument('--json', '-j', action='store_true',
                        help='Output as JSON instead of text')

    args = parser.parse_args()

    dataset_path = Path(args.path)
    if not dataset_path.exists():
        print(f"Error: Path does not exist: {dataset_path}", file=sys.stderr)
        return 1

    results = extract_text_content(dataset_path)

    if args.json:
        output = format_json_output(results, dataset_path)
    else:
        output = format_text_output(results, dataset_path)

    if args.output:
        Path(args.output).write_text(output)
        print(f"Report written to: {args.output}", file=sys.stderr)
    else:
        print(output)

    return 0


if __name__ == '__main__':
    sys.exit(main())
