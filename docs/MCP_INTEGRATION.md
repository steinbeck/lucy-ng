# MCP Integration Guide

This guide explains how to integrate lucy-ng with AI agents using the Model Context Protocol (MCP).

## Table of Contents

- [What is MCP?](#what-is-mcp)
- [Available Tools](#available-tools)
- [Setup](#setup)
- [Claude Desktop Integration](#claude-desktop-integration)
- [Claude Code Integration](#claude-code-integration)
- [Programmatic Usage](#programmatic-usage)
- [Example Conversations](#example-conversations)
- [Troubleshooting](#troubleshooting)
- [AI Guide](#ai-guide)

## What is MCP?

The Model Context Protocol (MCP) is an open standard by Anthropic for connecting AI assistants to external tools and data sources. Lucy-ng implements an MCP server that exposes NMR processing and structure elucidation tools to AI agents.

### Benefits

- **Structured Interface**: AI agents receive structured data, not free-form text
- **Tool Discovery**: Agents automatically discover available capabilities
- **Error Handling**: Clear error responses enable agent recovery
- **Stateless Design**: Each tool call is independent

## Available Tools

Lucy-ng exposes 13 MCP tools:

### Spectrum Reading

| Tool | Description | Parameters |
|------|-------------|------------|
| `read_spectrum_1d` | Read 1D NMR spectrum metadata | `path` |
| `read_spectrum_2d` | Read 2D NMR spectrum metadata | `path` |

### Peak Picking

| Tool | Description | Parameters |
|------|-------------|------------|
| `pick_peaks_1d` | Pick peaks from 1D spectrum | `path`, `threshold` (optional) |
| `pick_hsqc_peaks` | DEPT-guided HSQC picking | `hsqc_path`, `dept135_path`, `dept90_path` (optional) |
| `pick_hmbc_peaks` | Guided HMBC picking | `hmbc_path`, `c13_path`, `hsqc_path`, `dept135_path` (optional) |

### Analysis

| Tool | Description | Parameters |
|------|-------------|------------|
| `analyze_symmetry` | Detect molecular symmetry | `molecular_formula`, `hsqc_path`, `dept135_path` |

### Dereplication

| Tool | Description | Parameters |
|------|-------------|------------|
| `dereplicate_c13` | Match against database | `c13_path`, `molecular_formula`, `database_path` (optional), `top_n`, `match_threshold` |

### LSD Integration

| Tool | Description | Parameters |
|------|-------------|------------|
| `check_lsd_availability` | Check if LSD is installed | (none) |
| `generate_lsd_input` | Generate LSD input file | `data_dir`, `molecular_formula`, `output_file` (optional) |
| `run_lsd` | Execute LSD solver | `input_file`, `timeout`, `output_dir` (optional) |
| `rank_lsd_solutions` | Rank solutions by 13C prediction | `smiles_file`, `experimental_shifts`, `tolerance`, `top_n` |

### Prediction

| Tool | Description | Parameters |
|------|-------------|------------|
| `predict_c13_shifts` | Predict 13C shifts from SMILES | `smiles`, `table_path` (optional), `max_radius` (optional) |

### Data Fetching

| Tool | Description | Parameters |
|------|-------------|------------|
| `fetch_nmrxiv_dataset` | Download NMR data from NMRXiv | `identifier`, `output_dir` (optional), `study_id` (optional), `download_all` |

## Setup

### Prerequisites

1. Install lucy-ng with MCP support:
   ```bash
   pip install lucy-ng[mcp]
   ```

2. Verify the MCP server is available:
   ```bash
   lucy-mcp --help
   ```

### Running the Server

The MCP server runs via stdio transport:

```bash
# Direct execution
lucy-mcp

# Or as module
python -m lucy_ng.mcp
```

The server waits for MCP protocol messages on stdin.

## Claude Desktop Integration

### Configuration

1. Locate your Claude Desktop config file:
   - **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - **Linux**: `~/.config/Claude/claude_desktop_config.json`
   - **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

2. Add the lucy-ng server configuration:

```json
{
  "mcpServers": {
    "lucy-ng": {
      "command": "lucy-mcp"
    }
  }
}
```

Or if running from source:

```json
{
  "mcpServers": {
    "lucy-ng": {
      "command": "python3",
      "args": ["-m", "lucy_ng.mcp"],
      "cwd": "/path/to/lucy-ng"
    }
  }
}
```

3. Restart Claude Desktop

### Verification

After restarting, Claude should have access to lucy-ng tools. Try:

> "What NMR analysis tools are available?"

Claude should list the lucy-ng tools.

### Example Usage

> "I have NMR data in data/Ibuprofen/. The molecular formula is C13H18O2. Can you identify the compound?"

Claude will use the tools to:
1. Read the spectra
2. Pick peaks
3. Check for database matches
4. Generate LSD input if needed

## Claude Code Integration

### Configuration

Add to your Claude Code MCP settings:

```json
{
  "mcpServers": {
    "lucy-ng": {
      "command": "lucy-mcp"
    }
  }
}
```

### Usage in Claude Code

Claude Code can use lucy-ng tools during conversations:

```
User: Analyze the NMR data in data/Ibuprofen and identify the compound (C13H18O2)

Claude Code: I'll use lucy-ng to analyze this data...
[Uses read_spectrum_1d, pick_hsqc_peaks, dereplicate_c13, etc.]
```

## Programmatic Usage

### Using MCP Client Library

```python
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def analyze_nmr():
    # Connect to lucy-ng server
    server_params = StdioServerParameters(
        command="lucy-mcp",
        args=[],
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize connection
            await session.initialize()

            # List available tools
            tools = await session.list_tools()
            print("Available tools:")
            for tool in tools.tools:
                print(f"  - {tool.name}: {tool.description}")

            # Read a spectrum
            result = await session.call_tool(
                "read_spectrum_1d",
                {"path": "data/Ibuprofen/2"}
            )
            print(f"\nSpectrum: {result}")

            # Pick peaks
            result = await session.call_tool(
                "pick_peaks_1d",
                {"path": "data/Ibuprofen/2", "threshold": 0.05}
            )
            print(f"\nPeaks found: {result['count']}")

            # Dereplication
            result = await session.call_tool(
                "dereplicate_c13",
                {
                    "c13_path": "data/Ibuprofen/2",
                    "molecular_formula": "C13H18O2",
                }
            )
            if result["is_match"]:
                print(f"\nMatch: {result['top_matches'][0]['name']}")

# Run
asyncio.run(analyze_nmr())
```

### MCP Inspector

Use the MCP inspector for interactive testing:

```bash
pip install mcp[cli]
mcp dev src/lucy_ng/mcp/server.py
```

This opens a web interface where you can:
- See all available tools
- Test tool calls interactively
- View request/response details

## Example Conversations

### Basic Analysis

**User:**
> Read the 13C spectrum at data/Ibuprofen/2 and pick the peaks.

**Claude uses:**
1. `read_spectrum_1d(path="data/Ibuprofen/2")` - Get spectrum info
2. `pick_peaks_1d(path="data/Ibuprofen/2")` - Pick peaks

**Response:**
> The 13C spectrum has 32768 data points covering -10 to 230 ppm at 125.76 MHz.
> I found 11 peaks ranging from 18.5 to 180.9 ppm.

### Full Structure Elucidation

**User:**
> I have NMR data for an unknown natural product in data/Unknown/. The molecular formula is C15H22O3. Can you identify it?

**Claude uses:**
1. `read_spectrum_2d(path="data/Unknown/6")` - Check for HSQC
2. `pick_hsqc_peaks(hsqc_path="data/Unknown/6", dept135_path="data/Unknown/3")` - Get HSQC peaks
3. `analyze_symmetry(molecular_formula="C15H22O3", ...)` - Check for symmetry
4. `dereplicate_c13(c13_path="data/Unknown/2", molecular_formula="C15H22O3")` - Database search
5. If no match: `generate_lsd_input(data_dir="data/Unknown", molecular_formula="C15H22O3")`
6. If LSD available: `run_lsd(input_file="unknown.lsd")`

**Response:**
> I analyzed the NMR data for C15H22O3:
>
> **HSQC Analysis:** Found 12 protonated carbons (3 CH3, 2 CH2, 7 CH)
>
> **Symmetry:** No symmetry detected - all 15 carbons are unique
>
> **Database Search:** No exact match in the database
>
> **LSD Results:** Generated 3 candidate structures. The most likely is...

### Symmetry Detection

**User:**
> The molecular formula is C12H16O2 but I only see 6 carbon signals. Why?

**Claude uses:**
1. `analyze_symmetry(molecular_formula="C12H16O2", ...)` - Analyze symmetry

**Response:**
> The compound shows molecular symmetry:
> - Expected carbons: 12
> - Observed signals: 6
> - Missing carbons: 6
>
> This is consistent with a symmetric molecule where pairs of carbons are equivalent.
> Possible motifs: para-disubstituted benzene (2 pairs of equivalent CH),
> or two equivalent alkyl chains.
>
> The hydrogen budget shows 16 expected vs 8 directly observed on unique carbons,
> consistent with each signal representing two equivalent positions.

### Solution Ranking

**User:**
> LSD generated 50 candidate structures. Which one is most likely correct?

**Claude uses:**
1. `rank_lsd_solutions(smiles_file="output/outlsd.out", experimental_shifts=[18.5, 22.4, ...], top_n=10)` - Rank by spectrum prediction

**Response:**
> I ranked the 50 LSD solutions by comparing predicted vs experimental 13C shifts:
>
> **Top candidates:**
> 1. Solution 23 (MAE: 1.8 ppm) - Best match
> 2. Solution 45 (MAE: 2.1 ppm)
> 3. Solution 12 (MAE: 2.4 ppm)
>
> Solution 23 shows excellent agreement between predicted and experimental shifts.
> The largest deviation is 3.2 ppm at 140 ppm (aromatic region).

### Shift Prediction

**User:**
> What 13C shifts would you expect for caffeine?

**Claude uses:**
1. `predict_c13_shifts(smiles="Cn1cnc2c1c(=O)n(c(=O)n2C)C")` - Predict from SMILES

**Response:**
> Predicted 13C shifts for caffeine (C8H10N4O2):
>
> | Carbon | Predicted (ppm) | Confidence |
> |--------|-----------------|------------|
> | C-2 | 151.8 | High |
> | C-4 | 148.5 | High |
> | C-5 | 107.2 | High |
> | C-6 | 155.1 | High |
> | N-CH3 | 27.8, 29.5, 33.4 | High |
>
> Predictions are based on HOSE code lookup with 6-sphere radius.

## Troubleshooting

### Server Not Starting

**Problem:** `lucy-mcp: command not found`

**Solution:**
```bash
# Verify installation
pip show lucy-ng | grep "Entry-points"

# Try running as module
python -m lucy_ng.mcp

# Reinstall with MCP extras
pip install --force-reinstall lucy-ng[mcp]
```

### Tools Not Appearing

**Problem:** Claude doesn't see lucy-ng tools

**Solutions:**
1. Restart Claude Desktop after config changes
2. Check config file syntax (valid JSON)
3. Verify server starts manually: `lucy-mcp`
4. Check Claude Desktop logs for errors

### Tool Errors

**Problem:** Tools return errors

**Solutions:**
1. Check file paths are absolute or relative to working directory
2. Ensure NMR data exists at specified path
3. Verify database file exists for dereplication
4. Check the error message in the response

### Database Timeout

**Problem:** Dereplication takes too long

**Solution:** COCONUT database queries take 1-2 minutes. This is normal for streaming through ~895K entries. For faster results, use NMRShiftDB:

```
dereplicate_c13(..., database_path="data/reference/nmrshiftdb2withsignals.sd")
```

### LSD Not Found

**Problem:** `run_lsd` returns "LSD not available"

**Solution:**
1. Install LSD from http://eos.univ-reims.fr/LSD/
2. Add to PATH: `export PATH="$PATH:/path/to/lsd"`
3. Or specify in the config's environment

### Connection Issues

**Problem:** MCP client can't connect

**Solutions:**
1. Ensure server uses stdio transport (default)
2. Check Python version >= 3.10
3. Verify mcp package is installed: `pip show mcp`

## Advanced Configuration

### Custom Working Directory

```json
{
  "mcpServers": {
    "lucy-ng": {
      "command": "lucy-mcp",
      "cwd": "/path/to/data/directory"
    }
  }
}
```

### Environment Variables

```json
{
  "mcpServers": {
    "lucy-ng": {
      "command": "lucy-mcp",
      "env": {
        "LUCY_DATA_DIR": "/path/to/data",
        "PATH": "/path/to/lsd:$PATH"
      }
    }
  }
}
```

### Multiple Instances

```json
{
  "mcpServers": {
    "lucy-ng-project1": {
      "command": "lucy-mcp",
      "cwd": "/path/to/project1"
    },
    "lucy-ng-project2": {
      "command": "lucy-mcp",
      "cwd": "/path/to/project2"
    }
  }
}
```

## AI Guide

For AI agents using lucy-ng, we provide a comprehensive guide covering:

- **Structure Elucidation Workflow**: Step-by-step process from dereplication to LSD solving
- **Scientific Background**: NMR experiment types, chemical shift regions, data interpretation
- **Critical Pitfalls**: Signal count vs. atom count, molecular symmetry, quaternary carbons, HMBC noise
- **Decision Trees**: When to proceed, how to handle symmetry, interpreting LSD results
- **Example Reasoning**: Worked examples showing proper analytical approach

See **[../CLAUDE.md](../CLAUDE.md)** for the complete guide.

This guide can be used as:
1. A reference document for AI agents during analysis
2. A system prompt or context for Claude Desktop/Claude Code
3. Training material for understanding the CASE workflow
