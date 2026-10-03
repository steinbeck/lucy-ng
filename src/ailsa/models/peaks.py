"""Data models for NMR peaks and peak lists."""

from typing import Any

from pydantic import BaseModel, field_validator


class Peak1D(BaseModel):
    """1D NMR peak."""

    position: float  # ppm
    intensity: float
    assignment: str | None = None
    multiplicity: str | None = None  # s, d, t, q, m, etc.
    snr: float | None = None  # signal-to-noise ratio vs MAD-based sigma (Phase 79)

    @field_validator("multiplicity")
    @classmethod
    def validate_multiplicity(cls, v: str | None) -> str | None:
        """Validate multiplicity code."""
        if v is None:
            return None
        valid = {"s", "d", "t", "q", "quint", "sext", "sept", "m", "br", "dd", "dt", "td", "dq"}
        if v.lower() not in valid:
            raise ValueError(f"Unknown multiplicity: {v}. Valid: {valid}")
        return v.lower()


class Peak2D(BaseModel):
    """2D NMR peak (correlation)."""

    f1_position: float  # ppm in indirect dimension
    f2_position: float  # ppm in direct dimension
    intensity: float
    f1_assignment: str | None = None
    f2_assignment: str | None = None
    snr: float | None = None  # signal-to-noise ratio vs MAD-based 2D sigma (FIX-12)

    @property
    def position(self) -> tuple[float, float]:
        """Return position as (f1, f2) tuple."""
        return (self.f1_position, self.f2_position)


class PeakList1D(BaseModel):
    """List of 1D NMR peaks."""

    peaks: list[Peak1D]
    nucleus: str
    spectrum_id: str | None = None
    noise_sigma: float | None = None  # MAD-based noise estimate sigma (Phase 79)

    @field_validator("nucleus")
    @classmethod
    def validate_nucleus(cls, v: str) -> str:
        """Validate nucleus."""
        valid_nuclei = {"1H", "13C", "15N", "31P", "19F", "2H"}
        if v not in valid_nuclei:
            raise ValueError(f"Unknown nucleus: {v}. Valid: {valid_nuclei}")
        return v

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return {
            "peaks": [p.model_dump() for p in self.peaks],
            "nucleus": self.nucleus,
            "spectrum_id": self.spectrum_id,
            "noise_sigma": self.noise_sigma,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "PeakList1D":
        """Create from dictionary."""
        return cls(
            peaks=[Peak1D(**p) for p in d["peaks"]],
            nucleus=d["nucleus"],
            spectrum_id=d.get("spectrum_id"),
            noise_sigma=d.get("noise_sigma"),
        )


class PeakList2D(BaseModel):
    """List of 2D NMR peaks (correlations)."""

    peaks: list[Peak2D]
    f1_nucleus: str
    f2_nucleus: str
    experiment_type: str
    spectrum_id: str | None = None

    @field_validator("f1_nucleus", "f2_nucleus")
    @classmethod
    def validate_nucleus(cls, v: str) -> str:
        """Validate nucleus."""
        valid_nuclei = {"1H", "13C", "15N", "31P", "19F", "2H"}
        if v not in valid_nuclei:
            raise ValueError(f"Unknown nucleus: {v}. Valid: {valid_nuclei}")
        return v

    @field_validator("experiment_type")
    @classmethod
    def validate_experiment_type(cls, v: str) -> str:
        """Validate experiment type."""
        valid_types = {"HSQC", "HMBC", "COSY", "TOCSY", "NOESY", "ROESY"}
        if v not in valid_types:
            raise ValueError(f"Unknown experiment type: {v}. Valid: {valid_types}")
        return v

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return {
            "peaks": [p.model_dump() for p in self.peaks],
            "f1_nucleus": self.f1_nucleus,
            "f2_nucleus": self.f2_nucleus,
            "experiment_type": self.experiment_type,
            "spectrum_id": self.spectrum_id,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "PeakList2D":
        """Create from dictionary."""
        return cls(
            peaks=[Peak2D(**p) for p in d["peaks"]],
            f1_nucleus=d["f1_nucleus"],
            f2_nucleus=d["f2_nucleus"],
            experiment_type=d["experiment_type"],
            spectrum_id=d.get("spectrum_id"),
        )
