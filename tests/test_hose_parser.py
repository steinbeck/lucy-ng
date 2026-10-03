"""Tests for HOSE code sphere 1 parsing."""

from ailsa.prediction.hose_parser import parse_sphere_1


def test_parse_simple():
    """Test parsing simple single neighbor."""
    result = parse_sphere_1("C-4;C(/)")
    assert result == {"C": 1}


def test_parse_multiple_elements():
    """Test parsing multiple different elements."""
    result = parse_sphere_1("C-4;CO(//)")
    assert result == {"C": 1, "O": 1}


def test_parse_double_bond_prefix():
    """Test parsing with double bond prefix (=)."""
    result = parse_sphere_1("C-3;=OCO(,,//)")
    assert result == {"O": 2, "C": 1}


def test_parse_aromatic_prefix():
    """Test parsing with aromatic prefix (*)."""
    result = parse_sphere_1("C-3;*C*C(//)")
    assert result == {"C": 2}


def test_parse_halogen():
    """Test parsing with halogen (Cl)."""
    result = parse_sphere_1("C-4;CClN(//)")
    assert result == {"C": 1, "Cl": 1, "N": 1}


def test_parse_bromine():
    """Test parsing with bromine."""
    result = parse_sphere_1("C-4;CBr(//)")
    assert result == {"C": 1, "Br": 1}


def test_parse_empty():
    """Test parsing empty string."""
    result = parse_sphere_1("")
    assert result == {}


def test_parse_no_semicolon():
    """Test parsing HOSE code without semicolon."""
    result = parse_sphere_1("C-4")
    assert result == {}


def test_parse_no_parens():
    """Test parsing sphere 1 without parentheses."""
    result = parse_sphere_1("C-4;CC")
    assert result == {"C": 2}


def test_parse_complex():
    """Test parsing complex sphere 1 with multiple bond types."""
    # C=O and C-C bonds
    result = parse_sphere_1("C-3;=OCC(//)")
    assert result == {"O": 1, "C": 2}


def test_parse_multiple_same_element():
    """Test parsing with multiple instances of same element."""
    result = parse_sphere_1("C-4;CCC(//)")
    assert result == {"C": 3}


def test_parse_all_halogens():
    """Test parsing with different halogens."""
    result = parse_sphere_1("C-4;FClBrI(//)")
    assert result == {"F": 1, "Cl": 1, "Br": 1, "I": 1}
