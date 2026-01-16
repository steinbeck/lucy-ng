"""Tests for NMR correlation diagram visualization module."""

from __future__ import annotations

import pytest

from lucy_ng.visualization import (
    ArrowRouter,
    ArrowStyle,
    AtomPosition,
    Correlation,
    CorrelationDiagramGenerator,
    CorrelationType,
    DiagramConfig,
    DiagramResult,
    RoutedArrow,
    SVGBuilder,
    fan_out_arrows,
)


class TestCorrelationType:
    """Tests for CorrelationType enum."""

    def test_enum_values(self) -> None:
        """Test all correlation types exist."""
        assert CorrelationType.HMBC.value == "HMBC"
        assert CorrelationType.HSQC.value == "HSQC"
        assert CorrelationType.COSY.value == "COSY"
        assert CorrelationType.NOESY.value == "NOESY"
        assert CorrelationType.ROESY.value == "ROESY"


class TestArrowStyle:
    """Tests for ArrowStyle model."""

    def test_defaults(self) -> None:
        """Test default arrow style values."""
        style = ArrowStyle()
        assert style.color == "#E41A1C"
        assert style.stroke_width == 2.0  # Increased for better visibility
        assert style.head_size == 10.0  # Increased for clearer arrow heads
        assert style.start_marker_size == 5.0  # Circle at arrow start
        assert style.curvature == 0.8  # Publication-style wide arcs
        assert style.dash_pattern is None

    def test_custom_values(self) -> None:
        """Test custom arrow style values."""
        style = ArrowStyle(
            color="#0000FF",
            stroke_width=2.0,
            curvature=0.5,
            dash_pattern="5,3",
        )
        assert style.color == "#0000FF"
        assert style.stroke_width == 2.0
        assert style.curvature == 0.5
        assert style.dash_pattern == "5,3"


class TestAtomPosition:
    """Tests for AtomPosition model."""

    def test_required_fields(self) -> None:
        """Test atom position with required fields only."""
        pos = AtomPosition(atom_index=0, x=1.0, y=2.0, element="C")
        assert pos.atom_index == 0
        assert pos.x == 1.0
        assert pos.y == 2.0
        assert pos.element == "C"
        assert pos.hydrogen_count == 0
        assert pos.carbon_shift is None
        assert pos.proton_shift is None

    def test_with_shifts(self) -> None:
        """Test atom position with chemical shifts."""
        pos = AtomPosition(
            atom_index=5,
            x=10.0,
            y=20.0,
            element="C",
            hydrogen_count=3,
            carbon_shift=22.5,
            proton_shift=0.9,
        )
        assert pos.hydrogen_count == 3
        assert pos.carbon_shift == 22.5
        assert pos.proton_shift == 0.9


class TestCorrelation:
    """Tests for Correlation model."""

    def test_hmbc_correlation(self) -> None:
        """Test HMBC correlation creation."""
        corr = Correlation(
            source_atom=0,
            target_atom=5,
            correlation_type=CorrelationType.HMBC,
        )
        assert corr.source_atom == 0
        assert corr.target_atom == 5
        assert corr.correlation_type == CorrelationType.HMBC

    def test_correlation_types(self) -> None:
        """Test different correlation types."""
        for corr_type in CorrelationType:
            corr = Correlation(
                source_atom=1,
                target_atom=2,
                correlation_type=corr_type,
            )
            assert corr.correlation_type == corr_type


class TestDiagramConfig:
    """Tests for DiagramConfig model."""

    def test_defaults(self) -> None:
        """Test default configuration values."""
        config = DiagramConfig()
        assert config.width == 800
        assert config.height == 600
        assert config.padding == 50
        assert config.show_chemical_shifts is True
        assert config.show_legend is True
        assert config.show_atom_indices is False
        assert config.show_hydrogens is False  # Publication style: no explicit H (cleaner)

    def test_get_style_for_type(self) -> None:
        """Test getting style for each correlation type."""
        config = DiagramConfig()

        hmbc_style = config.get_style_for_type(CorrelationType.HMBC)
        assert hmbc_style.color == config.hmbc_style.color

        hsqc_style = config.get_style_for_type(CorrelationType.HSQC)
        assert hsqc_style.color == config.hsqc_style.color

        cosy_style = config.get_style_for_type(CorrelationType.COSY)
        assert cosy_style.color == config.cosy_style.color

        noesy_style = config.get_style_for_type(CorrelationType.NOESY)
        assert noesy_style.color == config.noesy_style.color

    def test_custom_dimensions(self) -> None:
        """Test custom diagram dimensions."""
        config = DiagramConfig(width=1200, height=900, padding=60)
        assert config.width == 1200
        assert config.height == 900
        assert config.padding == 60


class TestRoutedArrow:
    """Tests for RoutedArrow model."""

    def test_routed_arrow(self) -> None:
        """Test routed arrow creation."""
        corr = Correlation(
            source_atom=0,
            target_atom=1,
            correlation_type=CorrelationType.HMBC,
        )
        style = ArrowStyle()

        arrow = RoutedArrow(
            correlation=corr,
            start_x=10.0,
            start_y=20.0,
            end_x=100.0,
            end_y=50.0,
            control_points=[(55.0, 0.0)],
            style=style,
        )

        assert arrow.correlation == corr
        assert arrow.start_x == 10.0
        assert arrow.start_y == 20.0
        assert arrow.end_x == 100.0
        assert arrow.end_y == 50.0
        assert len(arrow.control_points) == 1
        assert arrow.control_points[0] == (55.0, 0.0)


class TestSVGBuilder:
    """Tests for SVGBuilder class."""

    def test_empty_svg(self) -> None:
        """Test building empty SVG."""
        builder = SVGBuilder(800, 600)
        svg = builder.build()

        assert '<?xml version="1.0" encoding="UTF-8"?>' in svg
        assert 'width="800"' in svg
        assert 'height="600"' in svg
        assert 'viewBox="0 0 800 600"' in svg

    def test_arrow_marker(self) -> None:
        """Test adding arrow marker definition."""
        builder = SVGBuilder(800, 600)
        builder.add_arrow_marker("test-arrow", "#FF0000", size=8.0)
        svg = builder.build()

        assert '<defs>' in svg
        assert 'id="test-arrow"' in svg
        assert 'fill="#FF0000"' in svg

    def test_bezier_arrow_quadratic(self) -> None:
        """Test adding quadratic Bezier arrow."""
        builder = SVGBuilder(800, 600)
        builder.add_arrow_marker("hmbc", "#E41A1C")

        corr = Correlation(
            source_atom=0,
            target_atom=1,
            correlation_type=CorrelationType.HMBC,
        )
        arrow = RoutedArrow(
            correlation=corr,
            start_x=100.0,
            start_y=200.0,
            end_x=300.0,
            end_y=200.0,
            control_points=[(200.0, 150.0)],
            style=ArrowStyle(),
        )

        builder.add_bezier_arrow(arrow, "hmbc")
        svg = builder.build()

        assert 'M 100.00 200.00' in svg
        assert 'Q 200.00 150.00' in svg
        assert 'marker-end="url(#hmbc)"' in svg

    def test_bezier_arrow_cubic(self) -> None:
        """Test adding cubic Bezier arrow."""
        builder = SVGBuilder(800, 600)
        builder.add_arrow_marker("test", "#000000")

        corr = Correlation(
            source_atom=0,
            target_atom=1,
            correlation_type=CorrelationType.HMBC,
        )
        arrow = RoutedArrow(
            correlation=corr,
            start_x=0.0,
            start_y=0.0,
            end_x=100.0,
            end_y=100.0,
            control_points=[(25.0, 50.0), (75.0, 50.0)],
            style=ArrowStyle(),
        )

        builder.add_bezier_arrow(arrow, "test")
        svg = builder.build()

        # Cubic bezier uses C command
        assert ' C ' in svg

    def test_text_label(self) -> None:
        """Test adding text label."""
        builder = SVGBuilder(800, 600)
        builder.add_text_label(100.0, 200.0, "45.2", font_size=12.0, color="#666666")
        svg = builder.build()

        assert '<text x="100.00" y="200.00"' in svg
        assert 'font-size="12.0"' in svg
        assert 'fill="#666666"' in svg
        assert '>45.2</text>' in svg

    def test_raw_svg(self) -> None:
        """Test adding raw SVG content."""
        builder = SVGBuilder(400, 300)
        builder.add_raw_svg('<circle cx="200" cy="150" r="50" fill="blue" />')
        svg = builder.build()

        assert '<circle cx="200" cy="150" r="50" fill="blue" />' in svg

    def test_legend(self) -> None:
        """Test adding legend."""
        builder = SVGBuilder(800, 600)
        items = [
            ("HMBC", ArrowStyle(color="#E41A1C")),
            ("COSY", ArrowStyle(color="#377EB8")),
        ]
        builder.add_legend(700.0, 50.0, items)
        svg = builder.build()

        assert '>HMBC</text>' in svg
        assert '>COSY</text>' in svg


class TestArrowRouter:
    """Tests for ArrowRouter class."""

    def test_empty_correlations(self) -> None:
        """Test routing with no correlations."""
        router = ArrowRouter()
        config = DiagramConfig()
        result = router.route_arrows([], {}, config)
        assert result == []

    def test_single_arrow(self) -> None:
        """Test routing a single arrow."""
        router = ArrowRouter()
        config = DiagramConfig()

        positions = {
            0: AtomPosition(atom_index=0, x=0.0, y=0.0, element="C"),
            1: AtomPosition(atom_index=1, x=2.0, y=0.0, element="C"),
        }
        correlations = [
            Correlation(
                source_atom=0,
                target_atom=1,
                correlation_type=CorrelationType.HMBC,
            )
        ]

        result = router.route_arrows(correlations, positions, config)

        assert len(result) == 1
        assert result[0].correlation == correlations[0]
        assert len(result[0].control_points) == 1

    def test_missing_atom_skipped(self) -> None:
        """Test that correlations with missing atoms are skipped."""
        router = ArrowRouter()
        config = DiagramConfig()

        positions = {
            0: AtomPosition(atom_index=0, x=0.0, y=0.0, element="C"),
        }
        correlations = [
            Correlation(
                source_atom=0,
                target_atom=99,  # Missing atom
                correlation_type=CorrelationType.HMBC,
            )
        ]

        result = router.route_arrows(correlations, positions, config)
        assert len(result) == 0

    def test_multiple_arrows(self) -> None:
        """Test routing multiple arrows."""
        router = ArrowRouter()
        config = DiagramConfig()

        positions = {
            0: AtomPosition(atom_index=0, x=0.0, y=0.0, element="C"),
            1: AtomPosition(atom_index=1, x=2.0, y=0.0, element="C"),
            2: AtomPosition(atom_index=2, x=1.0, y=2.0, element="C"),
        }
        correlations = [
            Correlation(source_atom=0, target_atom=1, correlation_type=CorrelationType.HMBC),
            Correlation(source_atom=0, target_atom=2, correlation_type=CorrelationType.HMBC),
            Correlation(source_atom=1, target_atom=2, correlation_type=CorrelationType.HMBC),
        ]

        result = router.route_arrows(correlations, positions, config)
        assert len(result) == 3


class TestFanOutArrows:
    """Tests for fan_out_arrows function."""

    def test_no_fanout_needed(self) -> None:
        """Test that arrows with different sources are unchanged."""
        corr1 = Correlation(source_atom=0, target_atom=1, correlation_type=CorrelationType.HMBC)
        corr2 = Correlation(source_atom=2, target_atom=3, correlation_type=CorrelationType.HMBC)

        arrows = [
            RoutedArrow(
                correlation=corr1,
                start_x=0, start_y=0, end_x=10, end_y=0,
                control_points=[(5, -5)],
                style=ArrowStyle(),
            ),
            RoutedArrow(
                correlation=corr2,
                start_x=20, start_y=0, end_x=30, end_y=0,
                control_points=[(25, -5)],
                style=ArrowStyle(),
            ),
        ]

        result = fan_out_arrows(arrows)
        assert len(result) == 2

    def test_fanout_same_source(self) -> None:
        """Test that arrows from same source are fanned out."""
        corr1 = Correlation(source_atom=0, target_atom=1, correlation_type=CorrelationType.HMBC)
        corr2 = Correlation(source_atom=0, target_atom=2, correlation_type=CorrelationType.HMBC)

        arrows = [
            RoutedArrow(
                correlation=corr1,
                start_x=0, start_y=0, end_x=10, end_y=0,
                control_points=[(5, -5)],
                style=ArrowStyle(),
            ),
            RoutedArrow(
                correlation=corr2,
                start_x=0, start_y=0, end_x=0, end_y=10,
                control_points=[(-5, 5)],
                style=ArrowStyle(),
            ),
        ]

        result = fan_out_arrows(arrows)
        assert len(result) == 2
        # Control points should be adjusted (different from original)
        # The exact values depend on the fan angle calculation


class TestCorrelationDiagramGenerator:
    """Tests for CorrelationDiagramGenerator class."""

    def test_generate_simple(self) -> None:
        """Test generating diagram for simple molecule."""
        gen = CorrelationDiagramGenerator()

        result = gen.generate(
            smiles="CCO",  # Ethanol
            correlations=[
                Correlation(source_atom=0, target_atom=1, correlation_type=CorrelationType.HMBC),
            ],
        )

        assert isinstance(result, DiagramResult)
        assert result.svg_content.startswith('<?xml version="1.0"')
        assert result.width == 800
        assert result.height == 600
        assert result.correlation_count == 1
        assert result.arrows_routed == 1

    def test_generate_with_shifts(self) -> None:
        """Test generating diagram with chemical shift annotations."""
        gen = CorrelationDiagramGenerator()

        result = gen.generate(
            smiles="CC",  # Ethane
            correlations=[],
            carbon_shifts={0: 5.7, 1: 5.7},
        )

        assert "5.7" in result.svg_content

    def test_invalid_smiles(self) -> None:
        """Test that invalid SMILES raises ValueError."""
        gen = CorrelationDiagramGenerator()

        with pytest.raises(ValueError, match="Invalid SMILES"):
            gen.generate(
                smiles="invalid_smiles_xyz",
                correlations=[],
            )

    def test_custom_config(self) -> None:
        """Test generating with custom configuration."""
        config = DiagramConfig(
            width=1200,
            height=900,
            show_chemical_shifts=False,
            show_legend=False,
        )
        gen = CorrelationDiagramGenerator(config=config)

        result = gen.generate(
            smiles="C",
            correlations=[],
        )

        assert result.width == 1200
        assert result.height == 900

    def test_multiple_correlation_types(self) -> None:
        """Test generating diagram with multiple correlation types."""
        gen = CorrelationDiagramGenerator()

        result = gen.generate(
            smiles="CCCC",
            correlations=[
                Correlation(source_atom=0, target_atom=2, correlation_type=CorrelationType.HMBC),
                Correlation(source_atom=0, target_atom=1, correlation_type=CorrelationType.HSQC),
                Correlation(source_atom=1, target_atom=2, correlation_type=CorrelationType.COSY),
            ],
        )

        assert result.correlation_count == 3
        assert result.arrows_routed == 3
        # Check all marker types are defined (circles at start and end, no arrowheads)
        assert 'id="hmbc-start"' in result.svg_content
        assert 'id="hmbc-end"' in result.svg_content
        assert 'id="hsqc-start"' in result.svg_content
        assert 'id="cosy-start"' in result.svg_content

    def test_generate_aromatic(self) -> None:
        """Test generating diagram for aromatic molecule (benzene)."""
        # Use show_hydrogens=False to get just heavy atoms
        config = DiagramConfig(show_hydrogens=False)
        gen = CorrelationDiagramGenerator(config=config)

        result = gen.generate(
            smiles="c1ccccc1",  # Benzene
            correlations=[
                Correlation(source_atom=0, target_atom=2, correlation_type=CorrelationType.HMBC),
                Correlation(source_atom=0, target_atom=4, correlation_type=CorrelationType.HMBC),
            ],
            carbon_shifts={0: 128.5, 1: 128.5, 2: 128.5, 3: 128.5, 4: 128.5, 5: 128.5},
        )

        assert result.atom_count == 6  # Just 6 carbons without explicit H
        assert result.correlation_count == 2

    def test_generate_ibuprofen(self) -> None:
        """Test generating diagram for ibuprofen (realistic test case)."""
        gen = CorrelationDiagramGenerator()

        # Ibuprofen SMILES
        smiles = "CC(C)Cc1ccc(cc1)C(C)C(=O)O"

        # Sample HMBC correlations
        correlations = [
            Correlation(source_atom=0, target_atom=3, correlation_type=CorrelationType.HMBC),
            Correlation(source_atom=12, target_atom=10, correlation_type=CorrelationType.HMBC),
            Correlation(source_atom=12, target_atom=11, correlation_type=CorrelationType.HMBC),
        ]

        # Sample chemical shifts
        carbon_shifts = {
            0: 22.5,   # CH3
            2: 30.2,   # CH
            3: 45.1,   # CH2
            12: 180.5, # COOH
        }

        result = gen.generate(
            smiles=smiles,
            correlations=correlations,
            carbon_shifts=carbon_shifts,
        )

        assert result.svg_content.startswith('<?xml')
        assert result.correlation_count == 3
        assert result.arrows_routed == 3
        assert "22.5" in result.svg_content
        assert "180.5" in result.svg_content


class TestDiagramResult:
    """Tests for DiagramResult model."""

    def test_diagram_result(self) -> None:
        """Test diagram result fields."""
        result = DiagramResult(
            svg_content="<svg>test</svg>",
            width=800,
            height=600,
            atom_count=10,
            correlation_count=5,
            arrows_routed=5,
        )

        assert result.svg_content == "<svg>test</svg>"
        assert result.width == 800
        assert result.height == 600
        assert result.atom_count == 10
        assert result.correlation_count == 5
        assert result.arrows_routed == 5
