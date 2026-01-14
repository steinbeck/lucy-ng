---
name: lucy-ng:sanitize
description: AI-assisted sanitization of Bruker NMR datasets for blind CASE studies. Removes compound identity from metadata while preserving spectroscopic data for valid CASE evaluation.
---

# lucy-ng:sanitize

AI-assisted sanitization of Bruker NMR datasets for blind CASE studies.

---

## Purpose

This command removes compound identity information from NMR datasets while preserving spectroscopic data. This enables valid evaluation of AI-based Computer-Assisted Structure Elucidation (CASE) systems.

**Why this matters:** Public NMR datasets (nmrXiv, metabolomics repositories) contain compound names in metadata. If an AI discovers this information during CASE, it invalidates the evaluation because the AI is confirming a known answer rather than solving the structure from spectroscopic data.

---

## Prerequisites

The sanitization tools should be in the dataset directory or accessible. If not present, create them using the embedded code below.

---

## Workflow

### Step 1: Setup Tools

Check if the helper tools exist. If not, create them:

```bash
# Check for tools
ls lucy_text_extractor.py lucy_bulk_sanitize.py 2>/dev/null || echo "Tools not found"
```

If tools are missing, create them using the code in the "Helper Tools Code" section below.

### Step 2: Extract All Text Content

Run the text extractor to see all text content in the dataset:

```bash
python lucy_text_extractor.py <dataset_path>
```

This outputs:
- All file paths (which may contain compound names)
- Content of title files
- Content of peaklist.xml files
- Acquisition parameters
- Audit logs
- Any other text files

### Step 3: Identify Compound Identifiers (AI Task)

**This is where your AI understanding is critical.**

Review the extractor output and identify ALL of the following:

1. **Compound names**: Chemical names, trade names, trivial names
   - Examples: "Caffeine", "Indigo", "Ibuprofen", "Aspirin"
   - Also partial names: "Classics_Indigo" -> "Indigo"

2. **Database identifiers**:
   - CAS numbers: "CAS 482-89-3"
   - PubChem IDs: "CID 12345"
   - ChEBI IDs: "CHEBI:12345"
   - InChIKeys

3. **Dataset/sample naming patterns**:
   - nmrXiv patterns: "Classics_CompoundName"
   - Lab naming: "JD_caffeine_01"
   - Systematic names

4. **Paths containing compound info**:
   - `/data/Indigo/1/`
   - `C:\Users\lab\Caffeine\`

5. **Any other revealing information**:
   - Literature references with compound names
   - Comments mentioning the compound

**Create a sanitization manifest** - a list of all strings to redact:

```
# Example manifest (identifiers.txt)
Caffeine
caffeine
CAFFEINE
Classics_Caffeine
CAS 58-08-2
```

### Step 4: Execute Sanitization

Use the bulk sanitize tool:

```bash
# From manifest file
python lucy_bulk_sanitize.py <dataset_path> --manifest identifiers.txt --delete "*.mol" --delete "*.sdf" --delete "audita.txt" --delete "auditp.txt"

# Or specify patterns directly
python lucy_bulk_sanitize.py <dataset_path> \
    --redact "CompoundName" \
    --redact "Classics_CompoundName" \
    --redact "CAS 12-34-5" \
    --delete "*.mol" \
    --delete "audita.txt"
```

**Always delete:**
- `*.mol`, `*.sdf`, `*.cdx`, `*.cml` (structure files)
- `audita.txt`, `auditp.txt` (audit logs with timestamps and user info)

### Step 5: Verify Sanitization

Run the extractor again:

```bash
python lucy_text_extractor.py <dataset_path>
```

Review the output and confirm:
- [ ] No compound names remain
- [ ] No database identifiers remain
- [ ] Title files show only experiment type (1H, 13C, HSQC, etc.)
- [ ] No structure files remain
- [ ] No audit files remain

If any identifiers remain, repeat steps 4-5.

### Step 6: Document and Handoff

Create a sanitization report:

```markdown
## Sanitization Complete

Dataset: <path>
Date: <date>

### Identifiers Removed
- [list all redacted strings]

### Files Deleted
- [list deleted files]

### Verification
- Text extraction reviewed: Yes
- No compound names found: Yes
- Structure files removed: Yes

### For CASE Analysis
- Start a NEW AI session (to clear memory of this sanitization)
- Provide molecular formula: [user must supply from HRMS]
- Do not mention compound identity to the AI
```

---

## Helper Tools Code

### lucy_text_extractor.py

If the tool doesn't exist, create it with this code:

```python
#!/usr/bin/env python3
"""Extract all text content from Bruker NMR datasets for AI review."""

import os
import sys
import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional

BINARY_PATTERNS = {
    'fid', 'ser', '1r', '1i', '2rr', '2ri', '2ir', '2ii',
    '3rrr', '3rri', '3rir', '3rii', '3irr', '3iri', '3iir', '3iii',
}
BINARY_EXTENSIONS = {'.pdf', '.png', '.jpg', '.jpeg', '.gif', '.tiff', '.bmp'}

def is_binary_file(filepath: Path) -> bool:
    name = filepath.name.lower()
    if name in BINARY_PATTERNS:
        return True
    if filepath.suffix.lower() in BINARY_EXTENSIONS:
        return True
    try:
        with open(filepath, 'rb') as f:
            if b'\x00' in f.read(1024):
                return True
    except:
        return True
    return False

def read_file_safely(filepath: Path) -> Optional[str]:
    for encoding in ['utf-8', 'latin-1', 'cp1252']:
        try:
            with open(filepath, 'r', encoding=encoding) as f:
                return f.read()
        except (UnicodeDecodeError, UnicodeError):
            continue
    return None

def main():
    if len(sys.argv) < 2:
        print("Usage: python lucy_text_extractor.py <dataset_path>")
        return 1

    dataset_path = Path(sys.argv[1])
    print("=" * 80)
    print("TEXT CONTENT FOR AI REVIEW")
    print("=" * 80)
    print(f"\nDataset: {dataset_path.absolute()}")
    print(f"Directory name: {dataset_path.name}\n")

    print("-" * 80)
    print("FILE PATHS")
    print("-" * 80)
    for fp in sorted(dataset_path.rglob('*')):
        if fp.is_file() and not is_binary_file(fp):
            print(f"  {fp.relative_to(dataset_path)}")

    print("\n" + "-" * 80)
    print("FILE CONTENTS")
    print("-" * 80)

    for filepath in sorted(dataset_path.rglob('*')):
        if not filepath.is_file() or is_binary_file(filepath):
            continue
        content = read_file_safely(filepath)
        if content:
            print(f"\n>>> {filepath.relative_to(dataset_path)}")
            print("-" * 40)
            if len(content) > 3000:
                content = content[:3000] + "\n[...truncated...]"
            print(content)

    print("\n" + "=" * 80)
    print("Review above for compound names, CAS numbers, database IDs, etc.")
    return 0

if __name__ == '__main__':
    sys.exit(main())
```

### lucy_bulk_sanitize.py

```python
#!/usr/bin/env python3
"""Bulk sanitize Bruker NMR datasets."""

import os
import sys
import re
import argparse
from pathlib import Path
import fnmatch

BINARY_PATTERNS = {
    'fid', 'ser', '1r', '1i', '2rr', '2ri', '2ir', '2ii',
}

def is_binary_file(filepath: Path) -> bool:
    if filepath.name.lower() in BINARY_PATTERNS:
        return True
    try:
        with open(filepath, 'rb') as f:
            if b'\x00' in f.read(1024):
                return True
    except:
        return True
    return False

def sanitize_file(filepath: Path, patterns: list, replacement: str) -> int:
    if is_binary_file(filepath):
        return 0
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except:
        try:
            with open(filepath, 'r', encoding='latin-1') as f:
                content = f.read()
        except:
            return 0

    total = 0
    for pattern in patterns:
        new_content, count = re.subn(re.escape(pattern), replacement, content, flags=re.IGNORECASE)
        if count > 0:
            content = new_content
            total += count

    if total > 0:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
    return total

def main():
    parser = argparse.ArgumentParser(description='Bulk sanitize NMR datasets')
    parser.add_argument('path', help='Dataset path')
    parser.add_argument('--redact', '-r', action='append', default=[])
    parser.add_argument('--manifest', '-m', help='File with patterns (one per line)')
    parser.add_argument('--replace-with', default='Unknown')
    parser.add_argument('--delete', '-d', action='append', default=[])
    args = parser.parse_args()

    dataset = Path(args.path)
    patterns = list(args.redact)
    if args.manifest:
        with open(args.manifest) as f:
            patterns.extend(line.strip() for line in f if line.strip() and not line.startswith('#'))

    # Delete files
    for filepath in dataset.rglob('*'):
        if filepath.is_file():
            for pattern in args.delete:
                if fnmatch.fnmatch(filepath.name, pattern):
                    print(f"Deleting: {filepath.relative_to(dataset)}")
                    filepath.unlink()
                    break

    # Replace patterns
    if patterns:
        print(f"\nRedacting: {patterns}")
        for filepath in dataset.rglob('*'):
            if filepath.is_file():
                count = sanitize_file(filepath, patterns, args.replace_with)
                if count:
                    print(f"  {filepath.relative_to(dataset)}: {count} replacements")

    print("\nSanitization complete!")
    return 0

if __name__ == '__main__':
    sys.exit(main())
```

---

## Important Notes

1. **Binary NMR data is never modified** - The tools automatically skip fid, 1r, 2rr, etc.

2. **Case sensitivity** - Search for multiple case variants:
   - "Caffeine", "caffeine", "CAFFEINE"
   - Or use `--ignore-case` flag

3. **Directory names** - If the directory itself is named after the compound (e.g., `Indigo/`), you may need to rename it manually.

4. **Fresh AI session required** - After sanitization, start a NEW AI session for CASE analysis. The sanitizing AI has "seen" the compound name and cannot perform unbiased structure elucidation.

5. **Molecular formula** - Must be provided by the user to the CASE AI, simulating HRMS data. Never extract from metadata.

---

## Quick Reference

```bash
# Full sanitization workflow
python lucy_text_extractor.py ./dataset > review.txt
# [AI reviews review.txt and creates identifiers.txt]
python lucy_bulk_sanitize.py ./dataset -m identifiers.txt -d "*.mol" -d "audita.txt"
python lucy_text_extractor.py ./dataset  # Verify

# Shortcut for common patterns
python lucy_bulk_sanitize.py ./dataset \
    -r "CompoundName" \
    -d "*.mol" -d "*.sdf" -d "*.cdx" \
    -d "audita.txt" -d "auditp.txt"
```
