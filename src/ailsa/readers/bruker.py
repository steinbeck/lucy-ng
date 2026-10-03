"""Bruker NMR file reader."""

from pathlib import Path
from typing import Any

import nmrglue as ng
import numpy as np

from ailsa.models import Spectrum1D, Spectrum2D


def _strip_brackets(value: str) -> str:
    """Strip angle brackets from Bruker parameter strings."""
    if value.startswith("<") and value.endswith(">"):
        return value[1:-1]
    return value


def _get_param(dic: dict[str, Any], key: str, default: Any = None) -> Any:
    """Safely get a parameter from acqus dictionary."""
    try:
        value = dic["acqus"][key]
        if isinstance(value, str):
            return _strip_brackets(value)
        return value
    except KeyError:
        return default


def _get_param_2d(dic: dict[str, Any], param_dict: str, key: str, default: Any = None) -> Any:
    """Safely get a parameter from a specific parameter dictionary (acqus or acqu2s).

    Args:
        dic: The full dictionary from nmrglue
        param_dict: Either 'acqus' (F2) or 'acqu2s' (F1)
        key: Parameter key to retrieve
        default: Default value if not found

    Returns:
        Parameter value or default
    """
    try:
        value = dic[param_dict][key]
        if isinstance(value, str):
            return _strip_brackets(value)
        return value
    except KeyError:
        return default


def _detect_experiment_type(pulse_program: str, f1_nucleus: str, f2_nucleus: str) -> str:
    """Detect 2D NMR experiment type from pulse program and nuclei.

    Args:
        pulse_program: Bruker pulse program name (e.g., 'hsqcedetgp', 'cosygpqf')
        f1_nucleus: F1 dimension nucleus (e.g., '13C', '1H')
        f2_nucleus: F2 dimension nucleus (e.g., '1H')

    Returns:
        Experiment type string: HSQC, HMBC, COSY, TOCSY, NOESY, or ROESY

    Raises:
        ValueError: If experiment type cannot be determined
    """
    pp_lower = pulse_program.lower()

    # Check for specific experiment types by pulse program pattern
    # Order matters: check HMBC before HSQC since some pulse programs contain both
    if "hmbc" in pp_lower:
        return "HMBC"
    # Long-range indicators in inv4 programs indicate HMBC (e.g., inv4gplplrndqf)
    # "lr" = long-range, "lplr" = low-pass long-range filter
    if "inv4" in pp_lower:
        if "lr" in pp_lower or "lplr" in pp_lower or "lrnd" in pp_lower:
            return "HMBC"
        return "HSQC"
    if "hsqc" in pp_lower:
        return "HSQC"
    # HMQC is a one-bond heteronuclear correlation, treated as HSQC for picking
    if "hmqc" in pp_lower:
        return "HSQC"
    if "cosy" in pp_lower:
        return "COSY"
    if "tocsy" in pp_lower or "mlev" in pp_lower or "dipsi" in pp_lower:
        return "TOCSY"
    if "noesy" in pp_lower:
        return "NOESY"
    if "roesy" in pp_lower:
        return "ROESY"

    # Fallback: determine from nuclei
    if f1_nucleus == f2_nucleus:
        raise ValueError(
            f"Cannot determine homonuclear experiment type from pulse program: {pulse_program}"
        )
    else:
        raise ValueError(
            f"Cannot determine heteronuclear experiment type from pulse program: {pulse_program}"
        )


def _get_2d_params(dic: dict[str, Any]) -> dict[str, Any]:
    """Extract parameters for both dimensions of a 2D experiment.

    Args:
        dic: The full dictionary from nmrglue containing acqus and acqu2s

    Returns:
        Dictionary with extracted parameters:
        - f1_nucleus, f1_frequency, f1_sw (from acqu2s)
        - f2_nucleus, f2_frequency, f2_sw (from acqus)
        - solvent, pulse_program, num_scans (from acqus)
    """
    return {
        # F2 dimension (direct, from acqus)
        "f2_nucleus": _get_param_2d(dic, "acqus", "NUC1"),
        "f2_frequency": _get_param_2d(dic, "acqus", "SFO1"),
        "f2_sw": _get_param_2d(dic, "acqus", "SW_h"),
        # F1 dimension (indirect, from acqu2s)
        "f1_nucleus": _get_param_2d(dic, "acqu2s", "NUC1"),
        "f1_frequency": _get_param_2d(dic, "acqu2s", "SFO1"),
        "f1_sw": _get_param_2d(dic, "acqu2s", "SW_h"),
        # General parameters
        "solvent": _get_param_2d(dic, "acqus", "SOLVENT"),
        "pulse_program": _get_param_2d(dic, "acqus", "PULPROG"),
        "num_scans": _get_param_2d(dic, "acqus", "NS"),
    }


class BrukerReader:
    """Reader for Bruker NMR data files."""

    @staticmethod
    def read_1d(experiment_dir: str | Path) -> Spectrum1D:
        """Read a Bruker 1D experiment directory and return Spectrum1D.

        Args:
            experiment_dir: Path to Bruker experiment directory (contains acqus, pdata/)

        Returns:
            Spectrum1D object with processed data and parameters

        Raises:
            FileNotFoundError: If experiment directory doesn't exist
            ValueError: If nucleus is not supported
        """
        experiment_dir = Path(experiment_dir)

        if not experiment_dir.exists():
            raise FileNotFoundError(f"Experiment directory not found: {experiment_dir}")

        # Read processed data from pdata/1/
        pdata_dir = experiment_dir / "pdata" / "1"
        dic, data = ng.bruker.read_pdata(str(pdata_dir))

        # Also read acqus for acquisition parameters
        acqus_dic, _ = ng.bruker.read(str(experiment_dir))
        dic.update(acqus_dic)

        # Extract parameters
        nucleus = _get_param(dic, "NUC1")
        if nucleus is None:
            raise ValueError("NUC1 parameter not found in acqus")

        frequency = _get_param(dic, "SFO1")
        if frequency is None:
            raise ValueError("SFO1 parameter not found in acqus")

        solvent = _get_param(dic, "SOLVENT")
        pulse_program = _get_param(dic, "PULPROG")
        num_scans = _get_param(dic, "NS")
        temperature = _get_param(dic, "TE")

        # Generate ppm scale using universal dictionary
        udic = ng.bruker.guess_udic(dic, data)
        uc = ng.fileiobase.uc_from_udic(udic, dim=0)
        ppm_scale = uc.ppm_scale()

        # Build metadata
        metadata: dict[str, Any] = {}
        if pulse_program:
            metadata["pulse_program"] = pulse_program
        if num_scans is not None:
            metadata["num_scans"] = num_scans
        if temperature is not None:
            metadata["temperature"] = temperature

        return Spectrum1D(
            data=np.array(data, dtype=np.float64),
            ppm_scale=np.array(ppm_scale, dtype=np.float64),
            nucleus=nucleus,
            frequency=float(frequency),
            solvent=solvent,
            metadata=metadata,
        )

    @staticmethod
    def read_2d(experiment_dir: str | Path) -> Spectrum2D:
        """Read a Bruker 2D experiment directory and return Spectrum2D.

        Args:
            experiment_dir: Path to Bruker experiment directory (contains acqus, acqu2s, pdata/)

        Returns:
            Spectrum2D object with processed data and parameters

        Raises:
            FileNotFoundError: If experiment directory doesn't exist
            ValueError: If required parameters are missing or experiment type cannot be determined
        """
        experiment_dir = Path(experiment_dir)

        if not experiment_dir.exists():
            raise FileNotFoundError(f"Experiment directory not found: {experiment_dir}")

        # Read processed data from pdata/1/
        pdata_dir = experiment_dir / "pdata" / "1"
        dic, data = ng.bruker.read_pdata(str(pdata_dir))

        # Also read acqus and acqu2s for acquisition parameters
        acqus_dic, _ = ng.bruker.read(str(experiment_dir))
        dic.update(acqus_dic)

        # Extract 2D parameters
        params = _get_2d_params(dic)

        f1_nucleus = params["f1_nucleus"]
        f2_nucleus = params["f2_nucleus"]
        pulse_program = params["pulse_program"]

        if f1_nucleus is None:
            raise ValueError("NUC1 parameter not found in acqu2s (F1 dimension)")
        if f2_nucleus is None:
            raise ValueError("NUC1 parameter not found in acqus (F2 dimension)")
        if pulse_program is None:
            raise ValueError("PULPROG parameter not found in acqus")

        # Detect experiment type
        experiment_type = _detect_experiment_type(pulse_program, f1_nucleus, f2_nucleus)

        # Get frequency (use F2 as primary)
        frequency = params["f2_frequency"]
        if frequency is None:
            raise ValueError("SFO1 parameter not found in acqus")

        # Generate ppm scales using universal dictionary
        udic = ng.bruker.guess_udic(dic, data)

        # F1 scale (dim=0, indirect dimension)
        uc_f1 = ng.fileiobase.uc_from_udic(udic, dim=0)
        f1_ppm_scale = uc_f1.ppm_scale()

        # F2 scale (dim=1, direct dimension)
        uc_f2 = ng.fileiobase.uc_from_udic(udic, dim=1)
        f2_ppm_scale = uc_f2.ppm_scale()

        # Build metadata
        metadata: dict[str, Any] = {}
        if pulse_program:
            metadata["pulse_program"] = pulse_program
        if params["num_scans"] is not None:
            metadata["num_scans"] = params["num_scans"]
        if params["solvent"]:
            metadata["solvent"] = params["solvent"]
        if params["f1_frequency"] is not None:
            metadata["f1_frequency"] = params["f1_frequency"]
        if params["f1_sw"] is not None:
            metadata["f1_sw"] = params["f1_sw"]
        if params["f2_sw"] is not None:
            metadata["f2_sw"] = params["f2_sw"]

        return Spectrum2D(
            data=np.array(data, dtype=np.float64),
            f1_ppm_scale=np.array(f1_ppm_scale, dtype=np.float64),
            f2_ppm_scale=np.array(f2_ppm_scale, dtype=np.float64),
            f1_nucleus=f1_nucleus,
            f2_nucleus=f2_nucleus,
            experiment_type=experiment_type,
            frequency=float(frequency),
            metadata=metadata,
        )
