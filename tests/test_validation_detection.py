"""Validation tests for detection accuracy on synthetic data.

These tests verify that v3.0 detection algorithms produce scientifically
correct results across known chemical shift regions and functional groups.
Unlike unit tests that check implementation correctness, these validate
that detection results match expected chemistry principles.
"""

import pytest
from pathlib import Path

from ailsa.database import DatabaseManager
from ailsa.detection import StatisticalDetector
from ailsa.detection.grouping import group_signals


@pytest.fixture
def validation_db(tmp_path: Path) -> Path:
    """Create validation database with chemically realistic synthetic data."""
    db_path = tmp_path / "validation_hose.db"

    with DatabaseManager(db_path) as db:
        db.create_tables()

        conn = db.connection
        cursor = conn.cursor()

        # ===== HYBRIDISATION VALIDATION DATA =====

        # Aromatic region (120-160 ppm): sp2 dominant (>90%)
        # Chemistry principle: aromatic carbons are sp2 hybridised
        cursor.execute(
            """
            INSERT INTO hose_stats
                (hose_code, radius, mean, std, count, sp3_count, sp2_count, sp1_count,
                 has_carbon_neighbor, has_oxygen_neighbor, has_nitrogen_neighbor,
                 has_sulfur_neighbor, has_halogen_neighbor)
            VALUES
                ('C-3;=CC(=C/)', 3, 128.5, 2.0, 1000, 50, 940, 10, 980, 20, 30, 5, 0),
                ('C-3;=CC(=N/)', 3, 135.2, 1.8, 500, 20, 475, 5, 490, 10, 200, 2, 0),
                ('C-3;=CN(=C/)', 3, 142.8, 2.2, 300, 15, 280, 5, 295, 5, 150, 1, 0)
            """
        )

        # Aliphatic region (10-50 ppm): sp3 dominant (>90%)
        # Chemistry principle: alkyl carbons are sp3 hybridised
        cursor.execute(
            """
            INSERT INTO hose_stats
                (hose_code, radius, mean, std, count, sp3_count, sp2_count, sp1_count,
                 has_carbon_neighbor, has_oxygen_neighbor, has_nitrogen_neighbor,
                 has_sulfur_neighbor, has_halogen_neighbor)
            VALUES
                ('C-4;CC(C/C)', 3, 30.5, 1.5, 1200, 1150, 40, 10, 1190, 80, 20, 3, 0),
                ('C-4;CC(C/N)', 3, 35.2, 1.2, 400, 385, 10, 5, 395, 30, 150, 2, 0),
                ('C-4;CO(C/C)', 3, 42.1, 1.8, 350, 340, 8, 2, 345, 200, 10, 1, 0)
            """
        )

        # Carbonyl region (160-220 ppm): sp2 dominant + oxygen mandatory
        # Chemistry principle: carbonyl carbons are sp2 and bonded to oxygen
        cursor.execute(
            """
            INSERT INTO hose_stats
                (hose_code, radius, mean, std, count, sp3_count, sp2_count, sp1_count,
                 has_carbon_neighbor, has_oxygen_neighbor, has_nitrogen_neighbor,
                 has_sulfur_neighbor, has_halogen_neighbor)
            VALUES
                ('C-3;=OC(C/)', 3, 180.5, 3.0, 900, 10, 885, 5, 850, 895, 50, 1, 0),
                ('C-3;=ON(C/)', 3, 175.2, 2.5, 250, 5, 243, 2, 230, 245, 120, 0, 0),
                ('C-3;=OC(=C/)', 3, 195.8, 4.0, 180, 3, 175, 2, 178, 178, 15, 0, 0)
            """
        )

        # ===== NEIGHBOUR VALIDATION DATA =====

        # Ether C region (50-90 ppm): oxygen common (>50%)
        # Chemistry principle: ether carbons typically bonded to oxygen
        cursor.execute(
            """
            INSERT INTO hose_stats
                (hose_code, radius, mean, std, count, sp3_count, sp2_count, sp1_count,
                 has_carbon_neighbor, has_oxygen_neighbor, has_nitrogen_neighbor,
                 has_sulfur_neighbor, has_halogen_neighbor)
            VALUES
                ('C-4;OC(C/C)', 3, 68.5, 2.5, 600, 580, 15, 5, 590, 550, 30, 2, 0),
                ('C-4;OO(C/C)', 3, 75.2, 2.0, 120, 118, 2, 0, 115, 118, 5, 0, 0)
            """
        )

        # ===== BOND PAIR VALIDATION DATA =====

        # Create formula-normalized entries in compounds table
        cursor.execute(
            """
            INSERT INTO compounds (id, formula, formula_normalized, smiles, name)
            VALUES
                (1, 'C13H18O2', 'C13H18O2', 'CC(C)Cc1ccc(cc1)C(C)C(=O)O', 'ibuprofen'),
                (2, 'C10H14', 'C10H14', 'CC(C)Cc1ccccc1', 'hydrocarbon')
            """
        )

        # Insert bond pair statistics for HHB detection
        # C13H18O2 (ibuprofen-like): C-O bonds common (90%), O-O rare (1.6%)
        cursor.execute(
            """
            INSERT INTO bond_pair_stats
                (formula_normalized, element1, element2, compound_count, total_compounds, frequency)
            VALUES
                ('C13H18O2', 'C', 'O', 450, 500, 0.90),
                ('C13H18O2', 'O', 'O', 8, 500, 0.016),
                ('C13H18O2', 'C', 'N', 2, 500, 0.004)
            """
        )

        # C10H14 (hydrocarbon): no hetero-hetero bonds
        # (No bond_pair_stats entry - valid scenario)

        conn.commit()

    return db_path


class TestHybridisationAccuracy:
    """Validate hybridisation detection accuracy for known shift regions."""

    def test_aromatic_region_sp2_dominant(self, validation_db: Path):
        """Aromatic shifts (120-160 ppm) must show sp2 dominance (>90%).

        Chemistry: Aromatic carbons are sp2 hybridised. Detection must
        correctly identify this from shift-based HOSE statistics.
        """
        with StatisticalDetector(validation_db) as detector:
            result = detector.detect_hybridisation(130.0, radius=3, window_ppm=5.0)

        assert result.has_data is True, "Should have data for aromatic region"
        assert result.distribution.dominant == "sp2", "Aromatic carbons are sp2"
        assert result.distribution.sp2 > 0.90, "sp2 should dominate (>90%)"
        assert result.distribution.sp3 < 0.10, "sp3 should be rare (<10%)"

    def test_aliphatic_region_sp3_dominant(self, validation_db: Path):
        """Aliphatic shifts (10-50 ppm) must show sp3 dominance (>90%).

        Chemistry: Alkyl carbons are sp3 hybridised. Detection must
        correctly identify this from shift-based HOSE statistics.
        """
        with StatisticalDetector(validation_db) as detector:
            result = detector.detect_hybridisation(35.0, radius=3, window_ppm=5.0)

        assert result.has_data is True, "Should have data for aliphatic region"
        assert result.distribution.dominant == "sp3", "Aliphatic carbons are sp3"
        assert result.distribution.sp3 > 0.90, "sp3 should dominate (>90%)"
        assert result.distribution.sp2 < 0.10, "sp2 should be rare (<10%)"

    def test_carbonyl_region_sp2_dominant(self, validation_db: Path):
        """Carbonyl shifts (160-220 ppm) must show sp2 dominance.

        Chemistry: Carbonyl carbons (C=O) are sp2 hybridised.
        """
        with StatisticalDetector(validation_db) as detector:
            result = detector.detect_hybridisation(180.0, radius=3, window_ppm=5.0)

        assert result.has_data is True, "Should have data for carbonyl region"
        assert result.distribution.dominant == "sp2", "Carbonyl carbons are sp2"
        assert result.distribution.sp2 > 0.90, "sp2 should dominate (>90%)"


class TestNeighbourAccuracy:
    """Validate neighbour detection accuracy for known functional groups."""

    def test_carbonyl_oxygen_mandatory(self, validation_db: Path):
        """Carbonyl C (170-220 ppm) must show oxygen as mandatory (>95%).

        Chemistry: Carbonyl carbons are always bonded to oxygen (C=O).
        """
        with StatisticalDetector(validation_db) as detector:
            result = detector.detect_neighbours(180.0, radius=3, window_ppm=5.0)

        assert result.has_data is True, "Should have data for carbonyl region"
        assert result.distribution.oxygen > 0.95, "Oxygen should be mandatory (>95%)"
        assert "oxygen" in result.distribution.mandatory_elements

    def test_carbonyl_carbon_common(self, validation_db: Path):
        """Carbonyl C (170-220 ppm) must show carbon as common.

        Chemistry: Carbonyl carbons are bonded to other carbons (C-C=O).
        """
        with StatisticalDetector(validation_db) as detector:
            result = detector.detect_neighbours(180.0, radius=3, window_ppm=5.0)

        assert result.has_data is True
        assert result.distribution.carbon > 0.50, "Carbon should be common (>50%)"

    def test_aromatic_carbon_mandatory(self, validation_db: Path):
        """Aromatic CH (115-145 ppm) must show carbon as mandatory.

        Chemistry: Aromatic carbons have ring neighbours (all carbon).
        """
        with StatisticalDetector(validation_db) as detector:
            result = detector.detect_neighbours(130.0, radius=3, window_ppm=5.0)

        assert result.has_data is True
        assert result.distribution.carbon > 0.95, "Carbon should be mandatory for aromatics"
        assert "carbon" in result.distribution.mandatory_elements

    def test_ether_oxygen_common(self, validation_db: Path):
        """Ether C (50-90 ppm) must show oxygen as common (>50%).

        Chemistry: Ether carbons (C-O-C) are bonded to oxygen.
        """
        with StatisticalDetector(validation_db) as detector:
            result = detector.detect_neighbours(68.0, radius=3, window_ppm=5.0)

        assert result.has_data is True
        assert result.distribution.oxygen > 0.50, "Oxygen should be common for ethers (>50%)"


class TestSignalGrouping:
    """Validate signal grouping with tolerance and multiplicity awareness."""

    def test_ibuprofen_close_shifts_group(self):
        """Ibuprofen C4/C5 (44.90 + 45.03 ppm) should group at 0.25 ppm tolerance.

        Chemistry: These are chemically distinct but very close in shift.
        Grouping helps LSD handle magnetic equivalence ambiguity.
        """
        result = group_signals([44.90, 45.03], tolerance=0.25)

        assert len(result.groups) == 1, "Close shifts should group"
        assert result.groups[0].indices == [0, 1]
        assert result.groups[0].span == pytest.approx(0.13, abs=0.01)
        assert len(result.ungrouped) == 0, "No ungrouped signals"

    def test_well_separated_shifts_no_group(self):
        """Well-separated shifts should NOT group.

        Chemistry: 44.90 ppm (aliphatic) and 129.38 ppm (aromatic)
        are chemically distinct with large shift difference.
        """
        result = group_signals([44.90, 129.38], tolerance=0.25)

        assert len(result.groups) == 0, "Separated shifts should not group"
        assert len(result.ungrouped) == 2, "Both should be ungrouped"

    def test_multiplicity_aware_grouping(self):
        """Same multiplicity allows grouping; different multiplicities prevent it.

        Chemistry: CH2 groups can be magnetically equivalent; CH vs CH3
        are chemically distinct and should not group even if close.
        """
        # Same multiplicity (CH2) - should group
        result_same = group_signals(
            [44.90, 45.03],
            multiplicities=["CH2", "CH2"],
            tolerance=0.25
        )
        assert len(result_same.groups) == 1, "Same multiplicity should group"

        # Different multiplicity (CH vs CH2) - should not group
        result_diff = group_signals(
            [44.90, 45.03],
            multiplicities=["CH", "CH2"],
            tolerance=0.25
        )
        assert len(result_diff.groups) == 0, "Different multiplicities should not group"
        assert len(result_diff.ungrouped) == 2, "Both should be ungrouped"

    def test_ambiguous_multiplicity_does_not_bridge_incompatible(self):
        """Ambiguous CH/CH3 should NOT bridge incompatible CH and CH3.

        Chemistry: Even though CH/CH3 is compatible with both CH and CH3
        individually, if CH and CH3 are present in the same proximity,
        the complete linkage rule (pairwise incompatibility) should split
        the entire group into singletons.
        """
        result = group_signals(
            [44.90, 45.03, 45.15],
            multiplicities=["CH", "CH/CH3", "CH3"],
            tolerance=0.25
        )

        # CH and CH3 are incompatible, so entire group splits
        assert len(result.groups) == 0, "Incompatible pair should split group"
        assert len(result.ungrouped) == 3, "All become singletons"

    def test_single_peak_ungrouped(self):
        """Single isolated peak forms singleton (ungrouped).

        Chemistry: No magnetic equivalence, no grouping needed.
        """
        result = group_signals([129.38], tolerance=0.25)

        assert len(result.groups) == 0, "No groups for single peak"
        assert result.ungrouped == [0], "Single peak is ungrouped"


class TestHHBDetection:
    """Validate hetero-hetero bond detection for known formula classes."""

    def test_oxygen_formula_co_bonds_common(self, validation_db: Path):
        """Formulas with oxygen (e.g., C13H18O2) must show C-O bonds as common (>50%).

        Chemistry: Organic oxygen compounds have C-O bonds (alcohols, ethers, esters).
        """
        with StatisticalDetector(validation_db) as detector:
            result = detector.detect_hhb("C13H18O2", threshold=0.01)

        assert result.has_data is True, "Should have data for C13H18O2"
        assert result.has_heteroatoms is True

        # Check that C-O appears in allowed pairs
        co_pairs = [p for p in result.allowed_pairs if {p.element1, p.element2} == {"C", "O"}]
        assert len(co_pairs) > 0, "C-O bond should be present"
        assert co_pairs[0].frequency > 0.50, "C-O should be common (>50%)"

    def test_oo_bonds_rare(self, validation_db: Path):
        """O-O bonds should be rare (<5%) for non-peroxide formulas.

        Chemistry: Peroxides are rare; most oxygen compounds have C-O, not O-O.
        """
        with StatisticalDetector(validation_db) as detector:
            result = detector.detect_hhb("C13H18O2", threshold=0.01)

        assert result.has_data is True

        # Check that O-O is either forbidden or has very low frequency
        oo_pairs = [p for p in result.allowed_pairs if {p.element1, p.element2} == {"O", "O"}]
        if oo_pairs:
            assert oo_pairs[0].frequency < 0.05, "O-O should be rare (<5%) for non-peroxides"
        else:
            # O-O not in allowed pairs means it's forbidden (frequency < threshold)
            oo_forbidden = [p for p in result.forbidden_pairs if {p.element1, p.element2} == {"O", "O"}]
            assert len(oo_forbidden) > 0, "O-O should be in forbidden pairs"

    def test_pure_hydrocarbon_no_hhb(self, validation_db: Path):
        """Pure hydrocarbons (C10H14) should have no hetero-hetero bonds.

        Chemistry: Hydrocarbons contain only C and H; no heteroatom pairs.
        """
        with StatisticalDetector(validation_db) as detector:
            result = detector.detect_hhb("C10H14", threshold=0.01)

        assert result.has_heteroatoms is False, "Hydrocarbons have no heteroatoms"
        assert result.allowed_pairs == [], "No HHB for hydrocarbons"
        assert result.forbidden_pairs == [], "No HHB for hydrocarbons"
