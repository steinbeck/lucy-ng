"""MCP server for lucy-ng NMR processing tools.

Exposes NMR processing and structure elucidation tools to AI agents
via the Model Context Protocol (MCP).
"""

from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from lucy_ng.analysis import SymmetryAnalyzer
from lucy_ng.cli.dereplicate import _find_database_path, _is_sqlite_database
from lucy_ng.database import DatabaseQueryService
from lucy_ng.dereplication import CoconutLoader, DereplicationService, NMRShiftDBLoader
from lucy_ng.lsd import LSDInputGenerator, LSDRunner
from lucy_ng.lsd.parser import LSDOutputParser
from lucy_ng.prediction import C13Predictor
from lucy_ng.processing import AdaptivePeakPicker, DEPTGuidedPicker, HMBCGuidedPicker
from lucy_ng.ranking import SolutionRanker
from lucy_ng.readers import BrukerReader

# Create MCP server instance
mcp = FastMCP(
    name="lucy-ng",
    instructions="AI-powered Computer-Assisted Structure Elucidation for NMR data. "
    "Use these tools to read NMR spectra, pick peaks, analyze symmetry, "
    "dereplicate against databases, predict 13C shifts from structure, "
    "and generate LSD input for structure elucidation.",
)


# =============================================================================
# Spectrum Reading Tools
# =============================================================================


@mcp.tool()
def read_spectrum_1d(path: str) -> dict:
    """Read a Bruker 1D NMR spectrum and return metadata.

    Args:
        path: Path to Bruker experiment directory (e.g., "data/Ibuprofen/2")

    Returns:
        Dictionary with nucleus, frequency, points, ppm_range, and metadata
    """
    try:
        spectrum = BrukerReader.read_1d(path)
        return {
            "success": True,
            "nucleus": spectrum.nucleus,
            "frequency": spectrum.frequency,
            "solvent": spectrum.solvent,
            "points": len(spectrum.data),
            "ppm_min": float(spectrum.ppm_scale.min()),
            "ppm_max": float(spectrum.ppm_scale.max()),
            "metadata": spectrum.metadata,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def read_spectrum_2d(path: str) -> dict:
    """Read a Bruker 2D NMR spectrum and return metadata.

    Args:
        path: Path to Bruker experiment directory (e.g., "data/Ibuprofen/6")

    Returns:
        Dictionary with experiment_type, nuclei, frequency, shape, and ppm ranges
    """
    try:
        spectrum = BrukerReader.read_2d(path)
        return {
            "success": True,
            "experiment_type": spectrum.experiment_type,
            "f1_nucleus": spectrum.f1_nucleus,
            "f2_nucleus": spectrum.f2_nucleus,
            "frequency": spectrum.frequency,
            "shape": list(spectrum.data.shape),
            "f1_ppm_min": float(spectrum.f1_ppm_scale.min()),
            "f1_ppm_max": float(spectrum.f1_ppm_scale.max()),
            "f2_ppm_min": float(spectrum.f2_ppm_scale.min()),
            "f2_ppm_max": float(spectrum.f2_ppm_scale.max()),
            "metadata": spectrum.metadata,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# =============================================================================
# Peak Picking Tools
# =============================================================================


@mcp.tool()
def pick_peaks_1d(path: str, threshold: float | None = None) -> dict:
    """Pick peaks from a 1D NMR spectrum.

    Uses threshold-based peak picking with noise estimation.

    Args:
        path: Path to Bruker 1D experiment directory
        threshold: Intensity threshold as fraction of max (0.0-1.0). Default 0.05.

    Returns:
        Dictionary with peak count and list of peaks (ppm, intensity)
    """
    try:
        spectrum = BrukerReader.read_1d(path)
        if threshold is None:
            threshold = 0.05
        peaks = AdaptivePeakPicker.pick_peaks(spectrum, threshold=threshold)
        return {
            "success": True,
            "count": len(peaks.peaks),
            "nucleus": spectrum.nucleus,
            "peaks": [
                {"ppm": float(p.position), "intensity": float(p.intensity)}
                for p in peaks.peaks
            ],
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def pick_hsqc_peaks(
    hsqc_path: str,
    dept135_path: str,
    dept90_path: str | None = None,
) -> dict:
    """Pick HSQC peaks using DEPT-guided algorithm.

    Uses DEPT-135 as ground truth for protonated carbons. Adaptively lowers
    HSQC threshold until all DEPT carbons are matched. This ensures all
    real correlations are found while minimizing noise.

    Args:
        hsqc_path: Path to HSQC experiment directory
        dept135_path: Path to DEPT-135 experiment directory
        dept90_path: Optional path to DEPT-90 for CH/CH3 disambiguation

    Returns:
        Dictionary with peaks, carbon multiplicities (CH, CH2, CH3), and statistics
    """
    try:
        hsqc = BrukerReader.read_2d(hsqc_path)
        dept135 = BrukerReader.read_1d(dept135_path)

        if dept90_path:
            dept90 = BrukerReader.read_1d(dept90_path)
            result = DEPTGuidedPicker.pick_hsqc_peaks_with_dept90(hsqc, dept135, dept90)
        else:
            result = DEPTGuidedPicker.pick_hsqc_peaks(hsqc, dept135)

        return {
            "success": True,
            "dept_peaks_count": len(result.dept_peaks.peaks),
            "hsqc_peaks_count": len(result.peaks.peaks),
            "threshold_used": result.threshold_used,
            "iterations": result.iterations,
            "all_carbons_found": result.all_carbons_found,
            "carbon_multiplicities": result.carbon_multiplicities,
            "peaks": [
                {
                    "carbon_ppm": float(p.f1_position),
                    "proton_ppm": float(p.f2_position),
                    "intensity": float(p.intensity),
                    "multiplicity": result.carbon_multiplicities.get(
                        round(p.f1_position, 1)
                    ),
                }
                for p in result.peaks.peaks
            ],
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def pick_hmbc_peaks(
    hmbc_path: str,
    c13_path: str,
    hsqc_path: str,
    dept135_path: str | None = None,
) -> dict:
    """Pick HMBC peaks using guided algorithm.

    Filters HMBC peaks by requiring:
    1. Carbon (F1) position matches a known carbon from 13C or DEPT spectrum
    2. Proton (F2) position matches a proton from HSQC

    This removes noise peaks that would create false LSD constraints.

    Args:
        hmbc_path: Path to HMBC experiment directory
        c13_path: Path to 13C experiment directory
        hsqc_path: Path to HSQC experiment directory
        dept135_path: Optional DEPT-135 for additional carbon positions

    Returns:
        Dictionary with validated peaks and rejection statistics
    """
    try:
        hmbc = BrukerReader.read_2d(hmbc_path)
        c13 = BrukerReader.read_1d(c13_path)
        hsqc = BrukerReader.read_2d(hsqc_path)
        dept135 = BrukerReader.read_1d(dept135_path) if dept135_path else None

        result = HMBCGuidedPicker.pick_hmbc_peaks_from_spectra(
            hmbc=hmbc, carbon_spectrum=c13, hsqc=hsqc, dept135=dept135
        )

        return {
            "success": True,
            "reference_carbons": len(result.carbon_positions),
            "reference_protons": len(result.proton_positions),
            "raw_peak_count": result.raw_peak_count,
            "validated_count": result.validated_count,
            "rejected_count": result.rejected_count,
            "peaks": [
                {
                    "carbon_ppm": float(p.f1_position),
                    "proton_ppm": float(p.f2_position),
                    "intensity": float(p.intensity),
                }
                for p in result.peaks.peaks
            ],
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# =============================================================================
# Analysis Tools
# =============================================================================


@mcp.tool()
def analyze_symmetry(
    molecular_formula: str,
    hsqc_path: str,
    dept135_path: str,
) -> dict:
    """Analyze molecular symmetry from spectroscopic data.

    Compares expected atom counts from molecular formula with observed
    NMR signals to detect equivalent atoms due to symmetry. This is
    critical for correct LSD input generation.

    Common symmetry patterns:
    - Para-disubstituted benzene: 2 equivalent CH carbons (2 pairs)
    - Isopropyl group: 2 equivalent CH3 carbons
    - tert-Butyl group: 3 equivalent CH3 carbons

    Args:
        molecular_formula: Molecular formula (e.g., "C13H18O2")
        hsqc_path: Path to HSQC experiment directory
        dept135_path: Path to DEPT-135 experiment directory

    Returns:
        Dictionary with symmetry analysis including:
        - signal_count vs expected_carbons
        - hydrogen budget (expected vs observed)
        - intensity analysis for potential equivalents
        - interpretation hints for AI reasoning
    """
    try:
        hsqc = BrukerReader.read_2d(hsqc_path)
        dept135 = BrukerReader.read_1d(dept135_path)
        dept_result = DEPTGuidedPicker.pick_hsqc_peaks(hsqc, dept135)

        result = SymmetryAnalyzer.analyze(molecular_formula, dept_result, hsqc)

        return {
            "success": True,
            "molecular_formula": result.molecular_formula,
            "signal_count": result.signal_count,
            "expected_carbons": result.expected_carbons,
            "missing_carbons": result.missing_carbons,
            "has_symmetry": result.has_symmetry,
            "hydrogen_budget": {
                "expected_h": result.hydrogen_budget.expected_h,
                "total_accounted": result.hydrogen_budget.total_accounted,
                "missing_h": result.hydrogen_budget.missing_h,
                "has_equivalents": result.hydrogen_budget.has_equivalents,
            },
            "intensity_report": {
                "peak_count": len(result.intensity_report.peaks),
                "has_potential_equivalents": result.intensity_report.has_potential_equivalents,
                "high_intensity_peaks": [
                    {
                        "carbon_ppm": float(p.carbon_shift),
                        "proton_ppm": float(p.proton_shift),
                        "multiplicity": p.multiplicity,
                        "relative_intensity": float(p.relative_intensity),
                        "is_potential_equivalent": p.is_potential_equivalent,
                    }
                    for p in result.intensity_report.peaks
                    if p.is_potential_equivalent
                ],
            },
            "summary": result.summary(),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# =============================================================================
# Dereplication Tools
# =============================================================================


@mcp.tool()
def dereplicate_c13(
    c13_path: str,
    molecular_formula: str,
    database_path: str | None = None,
    top_n: int = 5,
    match_threshold: float = 0.7,
) -> dict:
    """Dereplicate 13C spectrum against reference database.

    Matches observed 13C peaks against reference spectra filtered by
    molecular formula. Uses SQLite database by default (~928K compounds)
    for fast O(1) lookup. Falls back to SD file scanning if database
    unavailable.

    Database auto-detection order:
    1. Explicit database_path if provided
    2. LUCY_DATABASE environment variable
    3. data/reference/compounds.db (default location)
    4. SD files (COCONUT, then NMRShiftDB)

    Args:
        c13_path: Path to 13C Bruker experiment directory
        molecular_formula: Target molecular formula (e.g., "C13H18O2")
        database_path: Optional path to database (.db) or SD file (.sd/.sdf)
        top_n: Number of top matches to return (default: 5)
        match_threshold: Score threshold for is_match (default: 0.7)

    Returns:
        Dictionary with candidates found, match scores, top matches,
        and database_type indicating which backend was used
    """
    # Loader can be DatabaseQueryService, NMRShiftDBLoader, or CoconutLoader
    loader: Any = None
    db_query_service: DatabaseQueryService | None = None
    database_type: str = "unknown"
    compound_count: int | None = None

    try:
        # Check for SQLite database FIRST
        if database_path is not None and _is_sqlite_database(database_path):
            # Explicit SQLite database path provided
            db_query_service = DatabaseQueryService(database_path)
            db_query_service.open()
            compound_count = db_query_service.get_compound_count()
            loader = db_query_service
            database_type = "sqlite"
            db_name = Path(database_path).name
        elif database_path is None:
            # No explicit path - try SQLite database first
            db_path = _find_database_path()
            if db_path is not None:
                db_query_service = DatabaseQueryService(db_path)
                db_query_service.open()
                compound_count = db_query_service.get_compound_count()
                loader = db_query_service
                database_type = "sqlite"
                db_name = db_path.name

        # Fall back to SD files if no database found/loaded
        if loader is None:
            is_coconut = False
            sd_database: str | None = database_path

            if sd_database is None:
                # Try default SD file locations
                search_paths = [
                    (Path("data/reference/coconut_predicted.sd"), True),
                    (Path("data/reference/nmrshiftdb2withsignals.sd"), False),
                    (Path.home() / ".lucy" / "coconut_predicted.sd", True),
                    (Path.home() / ".lucy" / "nmrshiftdb.sd", False),
                ]
                for p, coconut_flag in search_paths:
                    if p.exists():
                        sd_database = str(p)
                        is_coconut = coconut_flag
                        break

            if sd_database is None:
                return {
                    "success": False,
                    "error": "No reference database found. "
                    "Run 'lucy database download' to get the database.",
                }

            # Determine database type if path was provided
            if database_path is not None:
                is_coconut = "coconut" in Path(sd_database).name.lower()

            # Create SD file loader
            if is_coconut:
                loader = CoconutLoader(sd_database)
                database_type = "coconut_sd"
            else:
                loader = NMRShiftDBLoader(sd_database)
                loader.load()
                database_type = "nmrshiftdb_sd"

            db_name = Path(sd_database).name

        # Run dereplication
        spectrum = BrukerReader.read_1d(c13_path)
        service = DereplicationService(loader)
        result = service.dereplicate_from_spectrum(
            spectrum=spectrum,
            molecular_formula=molecular_formula,
            top_n=top_n,
            match_threshold=match_threshold,
        )

        response = {
            "success": True,
            "database": db_name,
            "database_type": database_type,
            "molecular_formula": result.molecular_formula,
            "expected_carbons": result.expected_carbons,
            "observed_peaks": result.observed_peaks,
            "candidates_found": result.candidates_found,
            "best_score": result.best_score,
            "is_match": result.is_match,
            "match_mode": result.match_mode.value,
            "top_matches": [
                {
                    "name": m.entry.name,
                    "formula": m.entry.molecular_formula,
                    "inchi": m.entry.inchi,
                    "score": m.score,
                    "matched_peaks": m.matched_peaks,
                    "unmatched_observed": len(m.unmatched_observed),
                    "unmatched_reference": len(m.unmatched_reference),
                }
                for m in result.top_matches
            ],
        }

        # Add compound count if available (SQLite databases)
        if compound_count is not None:
            response["compound_count"] = compound_count

        return response

    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        # Clean up database connection if using SQLite
        if db_query_service is not None:
            db_query_service.close()


# =============================================================================
# LSD Integration Tools
# =============================================================================


@mcp.tool()
def check_lsd_availability() -> dict:
    """Check if LSD solver is installed and available.

    Returns:
        Dictionary with availability status, path, and version
    """
    available = LSDRunner.is_available()
    result = {
        "success": True,
        "available": available,
    }

    if available:
        runner = LSDRunner()
        result["path"] = str(runner.lsd_path)
        version = LSDRunner.get_version()
        if version:
            result["version"] = version

    return result


@mcp.tool()
def generate_lsd_input(
    data_dir: str,
    molecular_formula: str,
    output_file: str | None = None,
) -> dict:
    """Generate LSD input file from NMR data directory.

    Reads NMR spectra from a Bruker data directory and generates
    an LSD input file with atom definitions and correlations.

    Required spectra:
    - DEPT-135 (or 13C) for carbon atoms
    - HSQC for direct C-H correlations

    Optional spectra:
    - HMBC for long-range correlations (strongly recommended)
    - DEPT-90 for CH/CH3 disambiguation
    - COSY for H-H correlations

    Args:
        data_dir: Path to compound directory containing Bruker experiments
        molecular_formula: Molecular formula (e.g., "C13H18O2")
        output_file: Optional path for output .lsd file

    Returns:
        Dictionary with generated LSD input content and file path
    """
    try:
        data_path = Path(data_dir)
        if not data_path.exists():
            return {"success": False, "error": f"Data directory not found: {data_dir}"}

        # Find experiment directories
        experiments = {}
        for exp_dir in sorted(data_path.iterdir()):
            if exp_dir.is_dir() and exp_dir.name.isdigit():
                try:
                    # Try to read as 2D first, then 1D
                    try:
                        spec2d = BrukerReader.read_2d(str(exp_dir))
                        experiments[spec2d.experiment_type.upper()] = exp_dir
                    except Exception:
                        # Fall back to 1D
                        spec1d = BrukerReader.read_1d(str(exp_dir))
                        # Distinguish DEPT from regular 13C
                        pulse_prog = spec1d.metadata.get("pulse_program", "").lower()
                        if "dept135" in pulse_prog or "dept-135" in pulse_prog:
                            experiments["DEPT135"] = exp_dir
                        elif "dept90" in pulse_prog or "dept-90" in pulse_prog:
                            experiments["DEPT90"] = exp_dir
                        elif "dept" in pulse_prog:
                            # Generic DEPT, assume 135
                            experiments["DEPT135"] = exp_dir
                        elif spec1d.nucleus == "13C":
                            experiments["13C"] = exp_dir
                        elif spec1d.nucleus == "1H":
                            experiments["1H"] = exp_dir
                except Exception:
                    continue

        # Check required spectra
        dept_path = experiments.get("DEPT135") or experiments.get("13C")
        hsqc_path = experiments.get("HSQC")

        if not dept_path:
            return {"success": False, "error": "No DEPT-135 or 13C spectrum found"}
        if not hsqc_path:
            return {"success": False, "error": "No HSQC spectrum found"}

        # Load spectra
        hsqc = BrukerReader.read_2d(str(hsqc_path))
        dept135 = BrukerReader.read_1d(str(dept_path))

        # Pick HSQC peaks with DEPT guidance
        dept90_path = experiments.get("DEPT90")
        if dept90_path:
            dept90 = BrukerReader.read_1d(str(dept90_path))
            dept_result = DEPTGuidedPicker.pick_hsqc_peaks_with_dept90(hsqc, dept135, dept90)
        else:
            dept_result = DEPTGuidedPicker.pick_hsqc_peaks(hsqc, dept135)

        # Load optional HMBC
        hmbc_peaks = None
        hmbc_path = experiments.get("HMBC")
        c13_path = experiments.get("13C")
        if hmbc_path and c13_path:
            hmbc = BrukerReader.read_2d(str(hmbc_path))
            c13 = BrukerReader.read_1d(str(c13_path))
            hmbc_result = HMBCGuidedPicker.pick_hmbc_peaks_from_spectra(
                hmbc=hmbc, carbon_spectrum=c13, hsqc=hsqc, dept135=dept135
            )
            hmbc_peaks = hmbc_result.peaks

        # Generate LSD problem
        problem = LSDInputGenerator.from_dept_result(
            dept_result=dept_result,
            hmbc_peaks=hmbc_peaks,
            molecular_formula=molecular_formula,
            name=data_path.name,
        )

        # Generate content
        content = LSDInputGenerator.generate(problem)

        # Write to file if requested
        written_path = None
        if output_file:
            output_path = Path(output_file)
            output_path.write_text(content)
            written_path = str(output_path)

        return {
            "success": True,
            "molecular_formula": molecular_formula,
            "atom_count": len(problem.atoms),
            "correlation_count": len(problem.correlations),
            "constraint_count": len(problem.constraints),
            "experiments_found": list(experiments.keys()),
            "output_file": written_path,
            "content": content,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def run_lsd(
    input_file: str,
    timeout: int = 60,
    output_dir: str | None = None,
) -> dict:
    """Execute LSD solver on an input file.

    Runs the LSD (Logic for Structure Determination) solver on the
    provided input file and returns the results.

    Args:
        input_file: Path to LSD input file (.lsd)
        timeout: Maximum execution time in seconds (default: 60)
        output_dir: Optional directory for output files

    Returns:
        Dictionary with solution count, success status, and solution contents
    """
    try:
        if not LSDRunner.is_available():
            return {
                "success": False,
                "error": "LSD solver not found. Install LSD and ensure it's in PATH.",
            }

        input_path = Path(input_file)
        if not input_path.exists():
            return {"success": False, "error": f"Input file not found: {input_file}"}

        runner = LSDRunner()
        out_dir = Path(output_dir) if output_dir else None

        result = runner.run_file(
            input_file=input_path,
            output_dir=out_dir,
            timeout=timeout,
        )

        return {
            "success": result.success,
            "solution_count": result.solution_count,
            "return_code": result.return_code,
            "output_dir": str(result.output_dir) if result.output_dir else None,
            "output_files": [str(f) for f in result.output_files],
            "solutions": result.solutions[:10],  # Limit to first 10 solutions
            "stdout": result.stdout[:1000] if result.stdout else "",
            "stderr": result.stderr[:1000] if result.stderr else "",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def _get_default_hose_table() -> Path | None:
    """Find the default HOSE lookup table."""
    import lucy_ng

    package_dir = Path(lucy_ng.__file__).parent

    # Check project data directory (development install)
    # package_dir = .../lucy-ng/src/lucy_ng → project_root = .../lucy-ng
    project_root = package_dir.parent.parent
    project_table = project_root / "data" / "reference" / "hose_nmrshiftdb.json.gz"
    if project_table.exists():
        return project_table

    # Check package data (pip install)
    package_table = package_dir / "data" / "hose_nmrshiftdb.json.gz"
    if package_table.exists():
        return package_table

    # Check user home directory
    home_table = Path.home() / ".lucy" / "hose_nmrshiftdb.json.gz"
    if home_table.exists():
        return home_table

    # Fallback to current working directory (legacy)
    cwd_table = Path("data/reference/hose_nmrshiftdb.json.gz")
    if cwd_table.exists():
        return cwd_table

    return None


@mcp.tool()
def rank_lsd_solutions(
    smiles_file: str,
    experimental_shifts: list[float],
    top_n: int = 10,
    tolerance: float = 3.0,
    table_path: str | None = None,
) -> dict:
    """Rank LSD solutions by comparing predicted vs experimental 13C shifts.

    Uses local HOSE-based prediction to estimate 13C shifts for each LSD
    solution structure, then ranks by Mean Absolute Error (MAE) against
    the experimental spectrum.

    This is the key tool for reducing LSD solution space - solutions with
    predicted shifts matching the experimental spectrum rank higher.

    Args:
        smiles_file: Path to file containing SMILES (one per line), typically outlsd output
        experimental_shifts: List of experimental 13C peak positions in ppm
        top_n: Number of top results to return (default: 10)
        tolerance: Max ppm difference for shift matching (default: 3.0)
        table_path: Optional path to HOSE lookup table (uses default if not set)

    Returns:
        Dictionary with ranked solutions including:
        - mae: Mean Absolute Error in ppm (lower = better match)
        - matched_count: Number of carbons matched to experimental peaks
        - prediction_rate: Fraction of carbons successfully predicted
    """
    try:
        # Find table path
        t_path: Path | None = None
        if table_path:
            t_path = Path(table_path)
            if not t_path.exists():
                return {"success": False, "error": f"Table not found: {table_path}"}
        else:
            t_path = _get_default_hose_table()
            if t_path is None:
                return {
                    "success": False,
                    "error": "No HOSE lookup table found. Build with: "
                    "lucy predict build-table --source nmrshiftdb",
                }

        # Load solutions from SMILES file
        smiles_path = Path(smiles_file)
        if not smiles_path.exists():
            return {"success": False, "error": f"SMILES file not found: {smiles_file}"}

        solutions = LSDOutputParser.parse_smiles_file(smiles_path)
        if not solutions:
            return {"success": False, "error": "No SMILES found in file"}

        # Create ranker
        ranker = SolutionRanker.from_table_file(
            table_path=str(t_path),
            tolerance=tolerance,
        )

        # Rank solutions
        result = ranker.rank(solutions, experimental_shifts, top_n=top_n)

        return {
            "success": True,
            "total_solutions": result.total_solutions,
            "ranked_count": result.ranked_count,
            "skipped_count": result.skipped_count,
            "experimental_shifts": result.experimental_shifts,
            "tolerance": result.tolerance,
            "solutions": [
                {
                    "rank": i + 1,
                    "solution_index": sol.solution_index,
                    "smiles": sol.smiles,
                    "mae": round(sol.mae, 3),
                    "matched_count": sol.matched_count,
                    "total_carbons": sol.total_carbons,
                    "prediction_rate": round(sol.prediction_rate, 3),
                    "match_rate": round(sol.match_rate, 3),
                }
                for i, sol in enumerate(result.solutions)
            ],
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# =============================================================================
# Prediction Tools
# =============================================================================


# Cache for lookup table to avoid reloading
_prediction_cache: dict[str, C13Predictor] = {}


def _get_predictor(table_path: str | None = None) -> C13Predictor | None:
    """Get or create a predictor instance, caching the lookup table."""
    # Find table path
    if table_path is None:
        search_paths = [
            Path("data/reference/hose_lookup.json.gz"),
            Path.home() / ".lucy" / "hose_lookup.json.gz",
            Path("hose_lookup.json.gz"),
            Path("hose_lookup.json"),
        ]
        for p in search_paths:
            if p.exists():
                table_path = str(p)
                break

    if table_path is None:
        return None

    # Check cache
    if table_path in _prediction_cache:
        return _prediction_cache[table_path]

    # Load and cache
    try:
        predictor = C13Predictor.from_table_file(Path(table_path))
        _prediction_cache[table_path] = predictor
        return predictor
    except Exception:
        return None


@mcp.tool()
def predict_c13_shifts(
    smiles: str,
    table_path: str | None = None,
    max_radius: int = 6,
) -> dict:
    """Predict 13C NMR chemical shifts for a molecule from its structure.

    Uses HOSE (Hierarchically Ordered Spherical Environment) codes to
    look up chemical shifts in a reference database built from COCONUT.
    Falls back to shorter HOSE radii when exact matches aren't found.

    This tool is useful for:
    - Ranking LSD solutions by comparing predicted vs experimental shifts
    - Validating proposed structures
    - Estimating shifts for structure elucidation

    Args:
        smiles: Molecule structure in SMILES format
        table_path: Optional path to HOSE lookup table (uses default if not set)
        max_radius: Maximum HOSE radius for lookup (default: 6)

    Returns:
        Dictionary with predictions for each carbon including:
        - shift: predicted chemical shift in ppm
        - confidence: prediction confidence (0-1)
        - radius_used: HOSE radius at which match was found
        - match_count: number of reference matches
    """
    predictor = _get_predictor(table_path)
    if predictor is None:
        return {
            "success": False,
            "error": "No HOSE lookup table found. Build one with: "
            "lucy predict build-table <coconut.sd>",
        }

    try:
        result = predictor.predict_from_smiles(smiles)

        return {
            "success": True,
            "smiles": result.smiles,
            "carbon_count": result.carbon_count,
            "success_count": result.success_count,
            "success_rate": result.success_rate,
            "predictions": [
                {
                    "atom_index": p.atom_index,
                    "shift": round(p.shift, 2),
                    "confidence": p.confidence,
                    "radius_used": p.radius_used,
                    "match_count": p.match_count,
                    "std_dev": round(p.std_dev, 2),
                    "range": [round(p.min_shift, 2), round(p.max_shift, 2)],
                }
                for p in result.get_shifts_sorted()
            ],
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# =============================================================================
# NMRXiv Tools
# =============================================================================


@mcp.tool()
def fetch_nmrxiv_dataset(
    identifier: str,
    output_dir: str | None = None,
    study_id: str | None = None,
    download_all: bool = False,
) -> dict:
    """Fetch NMR dataset from NMRXiv repository.

    Downloads NMR spectra from NMRXiv (https://nmrxiv.org) to a local directory.
    The downloaded data preserves Bruker folder structure and can be directly
    used with lucy's spectrum reading commands.

    Args:
        identifier: NMRXiv DOI or ID. Supported formats:
            - DOI: "10.57992/NMRXIV.P10.S69" or "10.57992/NMRXIV.P10"
            - Project ID: "P10"
            - URL: "https://nmrxiv.org/P10"
        output_dir: Directory to save downloaded files (default: current directory)
        study_id: Specific study ID to download (overrides DOI study)
        download_all: If True, download all studies even if DOI specifies one

    Returns:
        Dictionary with:
        - project_id: The project identifier
        - project_name: Project title
        - doi: Project DOI if available
        - output_path: Path where files were saved
        - studies_downloaded: List of study IDs downloaded
        - total_datasets: Number of datasets downloaded
        - total_files: Total number of files downloaded
        - total_size_mb: Total download size in MB
    """
    from lucy_ng.nmrxiv import NMRXivClient, NMRXivError

    try:
        with NMRXivClient() as client:
            result = client.download(
                identifier=identifier,
                output_dir=output_dir or ".",
                study_id=study_id,
                download_all=download_all,
                progress=False,  # No progress bar for MCP
            )

            return {
                "success": True,
                "project_id": result.project_id,
                "project_name": result.project_name,
                "doi": result.doi,
                "output_path": result.output_path,
                "studies_downloaded": result.studies_downloaded,
                "total_datasets": result.total_datasets,
                "total_files": result.total_files,
                "total_size_mb": round(result.total_size_mb, 2),
            }
    except NMRXivError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": f"Unexpected error: {e}"}


def main() -> None:
    """Run the MCP server with stdio transport."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
