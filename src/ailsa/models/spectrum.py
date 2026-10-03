"""Data models for NMR spectra."""

from typing import Any

import numpy as np
from numpy.typing import NDArray
from pydantic import BaseModel, ConfigDict, field_validator


class Spectrum1D(BaseModel):
    """1D NMR spectrum data model."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    data: NDArray[np.float64]
    ppm_scale: NDArray[np.float64]
    nucleus: str
    frequency: float
    solvent: str | None = None
    metadata: dict[str, Any] = {}

    @field_validator("data", "ppm_scale", mode="before")
    @classmethod
    def convert_to_numpy(cls, v: Any) -> NDArray[np.float64]:
        """Convert input to numpy array."""
        if isinstance(v, np.ndarray):
            return v.astype(np.float64)
        return np.array(v, dtype=np.float64)

    @field_validator("nucleus")
    @classmethod
    def validate_nucleus(cls, v: str) -> str:
        """Validate nucleus is a known NMR-active nucleus."""
        valid_nuclei = {"1H", "13C", "15N", "31P", "19F", "2H"}
        if v not in valid_nuclei:
            raise ValueError(f"Unknown nucleus: {v}. Valid: {valid_nuclei}")
        return v

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return {
            "data": self.data.tolist(),
            "ppm_scale": self.ppm_scale.tolist(),
            "nucleus": self.nucleus,
            "frequency": self.frequency,
            "solvent": self.solvent,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Spectrum1D":
        """Create from dictionary."""
        return cls(**d)


class Spectrum2D(BaseModel):
    """2D NMR spectrum data model."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    data: NDArray[np.float64]
    f1_ppm_scale: NDArray[np.float64]
    f2_ppm_scale: NDArray[np.float64]
    f1_nucleus: str
    f2_nucleus: str
    experiment_type: str
    frequency: float
    metadata: dict[str, Any] = {}

    @field_validator("data", "f1_ppm_scale", "f2_ppm_scale", mode="before")
    @classmethod
    def convert_to_numpy(cls, v: Any) -> NDArray[np.float64]:
        """Convert input to numpy array."""
        if isinstance(v, np.ndarray):
            return v.astype(np.float64)
        return np.array(v, dtype=np.float64)

    @field_validator("f1_nucleus", "f2_nucleus")
    @classmethod
    def validate_nucleus(cls, v: str) -> str:
        """Validate nucleus is a known NMR-active nucleus."""
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
            "data": self.data.tolist(),
            "f1_ppm_scale": self.f1_ppm_scale.tolist(),
            "f2_ppm_scale": self.f2_ppm_scale.tolist(),
            "f1_nucleus": self.f1_nucleus,
            "f2_nucleus": self.f2_nucleus,
            "experiment_type": self.experiment_type,
            "frequency": self.frequency,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Spectrum2D":
        """Create from dictionary."""
        return cls(**d)

    def f1_ppm_to_index(self, ppm: float) -> int:
        """Convert F1 ppm value to nearest array index.

        Args:
            ppm: Chemical shift in ppm

        Returns:
            Nearest array index
        """
        return int(np.argmin(np.abs(self.f1_ppm_scale - ppm)))

    def f2_ppm_to_index(self, ppm: float) -> int:
        """Convert F2 ppm value to nearest array index.

        Args:
            ppm: Chemical shift in ppm

        Returns:
            Nearest array index
        """
        return int(np.argmin(np.abs(self.f2_ppm_scale - ppm)))

    def f1_index_to_ppm(self, index: int) -> float:
        """Convert F1 array index to ppm value.

        Args:
            index: Array index

        Returns:
            Chemical shift in ppm
        """
        return float(self.f1_ppm_scale[index])

    def f2_index_to_ppm(self, index: int) -> float:
        """Convert F2 array index to ppm value.

        Args:
            index: Array index

        Returns:
            Chemical shift in ppm
        """
        return float(self.f2_ppm_scale[index])
