"""Data models for NMR chemical shift prediction."""

from dataclasses import dataclass

from pydantic import BaseModel, Field


@dataclass
class HOSEStatsResult:
    """Statistics result from HOSE code lookup.

    Used as a common return type for both in-memory lookup tables
    and database-backed lookup adapters.
    """

    mean: float  # Mean chemical shift in ppm
    std: float  # Standard deviation
    count: int  # Number of observations


class ShiftEntry(BaseModel):
    """A chemical shift entry in the lookup table."""

    shift: float = Field(description="Chemical shift in ppm")
    multiplicity: str | None = Field(
        default=None, description="Carbon multiplicity (C, CH, CH2, CH3)"
    )
    source_id: str | None = Field(
        default=None, description="Source molecule identifier"
    )


class PredictedShift(BaseModel):
    """A predicted 13C chemical shift for a specific atom."""

    atom_index: int = Field(description="Atom index in the molecule")
    shift: float = Field(description="Predicted chemical shift in ppm")
    confidence: float = Field(
        ge=0.0, le=1.0, description="Confidence score (0-1)"
    )
    hose_code: str = Field(description="HOSE code used for prediction")
    radius_used: int = Field(description="HOSE radius at which match was found")
    match_count: int = Field(description="Number of reference matches")
    std_dev: float = Field(description="Standard deviation of matched shifts")
    min_shift: float = Field(description="Minimum shift in matches")
    max_shift: float = Field(description="Maximum shift in matches")


class PredictionResult(BaseModel):
    """Result of predicting 13C shifts for a molecule."""

    smiles: str = Field(description="Input SMILES string")
    predictions: list[PredictedShift] = Field(
        default_factory=list, description="Predicted shifts for each carbon"
    )
    carbon_count: int = Field(description="Number of carbons in molecule")
    success_count: int = Field(description="Number of successfully predicted carbons")

    @property
    def success_rate(self) -> float:
        """Fraction of carbons that were successfully predicted."""
        if self.carbon_count == 0:
            return 0.0
        return self.success_count / self.carbon_count

    def get_shifts_sorted(self) -> list[PredictedShift]:
        """Get predictions sorted by chemical shift (descending)."""
        return sorted(self.predictions, key=lambda p: p.shift, reverse=True)

    def summary(self) -> str:
        """Return a human-readable summary of predictions."""
        lines = [
            f"13C Shift Predictions for: {self.smiles}",
            f"Carbons: {self.carbon_count}, Predicted: {self.success_count} "
            f"({self.success_rate:.0%})",
            "",
            "Atom  Shift (ppm)  Confidence  Radius  Matches",
            "-" * 50,
        ]
        for p in self.get_shifts_sorted():
            lines.append(
                f"C{p.atom_index:<4} {p.shift:>10.2f}  {p.confidence:>10.2f}  "
                f"{p.radius_used:>6}  {p.match_count:>7}"
            )
        return "\n".join(lines)
