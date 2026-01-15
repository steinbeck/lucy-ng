#!/usr/bin/env python3
"""Upload compounds database to Figshare with chunked/resumable uploads."""

import hashlib
import json
import os
import sys
from pathlib import Path

import requests

# Configuration
FIGSHARE_API = "https://api.figshare.com/v2"
FILE_PATH = Path("data/reference/compounds.db.gz")
CHUNK_SIZE = 10 * 1024 * 1024  # 10 MB chunks for reliability

METADATA = {
    "title": "lucy-ng Compound Database: NMR Chemical Shifts for Natural Products",
    "description": """Pre-built SQLite database for lucy-ng containing 13C NMR chemical shifts for natural product dereplication.

**Contents:**
- 928,443 compounds total
- COCONUT: 895,099 natural products with predicted 13C shifts
- NMRShiftDB: 33,344 compounds with experimental 13C shifts
- 111,493 unique molecular formulas indexed for fast lookup

**Usage:**
gunzip -k compounds.db.gz
lucy database info compounds.db

**File format:** SQLite database (gzip compressed)
- Uncompressed size: ~1.0 GB
- Compressed size: ~343 MB

**Related software:** https://github.com/steinbeck/lucy-ng
""",
    "keywords": [
        "NMR spectroscopy",
        "natural products",
        "chemical shifts",
        "13C NMR",
        "dereplication",
        "COCONUT",
        "NMRShiftDB",
        "structure elucidation"
    ],
    "categories": [54],  # Chemistry
    "license": 1,  # CC-BY
    "defined_type": "dataset",
}


def md5_checksum(filepath: Path) -> str:
    """Calculate MD5 checksum of file."""
    hash_md5 = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(CHUNK_SIZE), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def api_request(method, url, token, **kwargs):
    """Make API request with proper headers."""
    headers = {"Authorization": f"token {token}"}
    if "json" in kwargs:
        headers["Content-Type"] = "application/json"

    response = requests.request(method, url, headers=headers, **kwargs)
    return response


def main():
    token = os.environ.get("FIGSHARE_TOKEN")

    if len(sys.argv) > 1:
        token = sys.argv[1]

    if not token:
        print("Usage: python figshare_upload.py <FIGSHARE_TOKEN>")
        print("   or: export FIGSHARE_TOKEN='...' && python figshare_upload.py")
        print("\nGet token at: https://figshare.com/account/applications")
        sys.exit(1)

    if not FILE_PATH.exists():
        print(f"Error: File not found: {FILE_PATH}")
        sys.exit(1)

    file_size = FILE_PATH.stat().st_size

    print("=" * 60)
    print("Figshare Upload: lucy-ng Compound Database")
    print("=" * 60)
    print(f"File: {FILE_PATH.name} ({file_size / 1e6:.1f} MB)")
    print(f"Chunk size: {CHUNK_SIZE / 1e6:.0f} MB")

    # Step 1: Calculate MD5
    print("\n[1/5] Calculating MD5 checksum...")
    md5 = md5_checksum(FILE_PATH)
    print(f"  MD5: {md5}")

    # Step 2: Create article
    print("\n[2/5] Creating article...")
    r = api_request("POST", f"{FIGSHARE_API}/account/articles", token, json=METADATA)
    if r.status_code != 201:
        print(f"Error creating article: {r.status_code}")
        print(r.text)
        sys.exit(1)

    article_url = r.json()["location"]
    article_id = article_url.split("/")[-1]
    print(f"  Article ID: {article_id}")

    # Step 3: Initiate file upload
    print("\n[3/5] Initiating file upload...")
    file_info = {
        "name": FILE_PATH.name,
        "size": file_size,
        "md5": md5,
    }
    r = api_request("POST", f"{article_url}/files", token, json=file_info)
    if r.status_code != 201:
        print(f"Error initiating upload: {r.status_code}")
        print(r.text)
        sys.exit(1)

    file_url = r.json()["location"]
    print(f"  File registered")

    # Get upload URL and parts info
    r = api_request("GET", file_url, token)
    file_data = r.json()
    upload_url = file_data["upload_url"]

    # Get parts info
    r = requests.get(upload_url)
    parts = r.json()["parts"]
    print(f"  Parts to upload: {len(parts)}")

    # Step 4: Upload parts
    print("\n[4/5] Uploading parts...")
    with open(FILE_PATH, "rb") as f:
        for i, part in enumerate(parts):
            part_no = part["partNo"]
            start = part["startOffset"]
            end = part["endOffset"]
            size = end - start + 1

            # Check if already uploaded
            if part["status"] == "COMPLETE":
                print(f"  Part {part_no}/{len(parts)}: Already uploaded, skipping")
                continue

            print(f"  Part {part_no}/{len(parts)}: {size/1e6:.1f} MB ", end="", flush=True)

            f.seek(start)
            data = f.read(size)

            # Upload part
            r = requests.put(
                f"{upload_url}/{part_no}",
                data=data,
            )

            if r.status_code == 200:
                print("✓")
            else:
                print(f"✗ (status {r.status_code})")
                print(f"  Error: {r.text}")
                print(f"\n  Re-run the script to resume from this part.")
                sys.exit(1)

    # Step 5: Complete upload
    print("\n[5/5] Completing upload...")
    r = api_request("POST", file_url, token)
    if r.status_code != 202:
        print(f"Warning: Complete returned {r.status_code}")

    # Get article info
    r = api_request("GET", article_url, token)
    article = r.json()

    print("\n" + "=" * 60)
    print("SUCCESS!")
    print("=" * 60)
    print(f"\n  Article ID: {article_id}")
    print(f"  Private URL: https://figshare.com/account/articles/{article_id}")
    print(f"\n  To publish, visit the URL above and click 'Publish'")
    print(f"  This will generate a DOI.")


if __name__ == "__main__":
    main()
