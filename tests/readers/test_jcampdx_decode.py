"""D-08 layer 1: hand-authored oracle unit tests for the vendored JCAMP-DX decoder.

Expected integers below are hand-computed from the JCAMP-DX pseudo-digit spec
(SQZ '@'=0,'A'=1..'I'=9,'a'=-1..'i'=-9; DIF '%'=0,'J'=1..'R'=9,'j'=-1..'r'=-9;
DUP 'S'=1,'T'=2..'Z'=8,'s'=9) -- an oracle independent of lucy-ng's own decoder,
so a bug introduced during vendoring (or a later edit) is caught even if the
reference decoder is absent or broken.

This module must NEVER import the reference decoder library -- only the
vendored lucy_ng copy under test.
"""


def test_hand_authored_mini_vector() -> None:
    """Decode a hand-traced DIF/SQZ/DUP mini-vector: [100, 105, 105, 102].

    Encoding: "(F2++(Y..Y))\\n0A00N%Sl"
      "0"    -> AFFN checkpoint value (ignored -- first value of every DIFDUP
                line is a checkpoint, never data)
      "A00"  -> SQZ: 'A' = leading digit '1', followed by literal "00"
                => absolute value 100
      "N"    -> DIF: 'N' = +5 (relative to previous)   => 100 + 5 = 105
      "%"    -> DIF: '%' = 0 (relative to previous)    => 105 + 0 = 105 (pending)
      "S"    -> DUP: 'S' = repeat-count 1 -> re-emits the pending diff (0)
                once more                              => another 105
      "l"    -> DIF: 'l' = -3 (relative to previous)   => 105 - 3 = 102
    """
    from lucy_ng.readers._jcampdx_decode import parse_data

    result, dtype = parse_data("(F2++(Y..Y))\n0A00N%Sl")
    assert list(result) == [100.0, 105.0, 105.0, 102.0]
    assert dtype == "R"


def test_hand_authored_dif_dup_heavy_line() -> None:
    """A second, DIF/DUP-heavy vector so a vendoring regression cannot hide.

    Encoding: "(F2++(Y..Y))\\n0A00JJTj" -> [100, 101, 102, 103, 102]
      "0"    -> AFFN checkpoint value (ignored)
      "A00"  -> SQZ absolute value 100
      "J"    -> DIF: 'J' = +1 (relative to previous)   => 100 + 1 = 101
      "J"    -> DIF: 'J' = +1 (relative to previous,
                pending)                               => 101 + 1 = 102 (pending)
      "T"    -> DUP: 'T' = repeat-count 2 -> re-emits the pending diff (+1)
                twice                                  => 102, then 103
      "j"    -> DIF: 'j' = -1 (relative to previous)   => 103 - 1 = 102
    """
    from lucy_ng.readers._jcampdx_decode import parse_data

    result, dtype = parse_data("(F2++(Y..Y))\n0A00JJTj")
    assert list(result) == [100.0, 101.0, 102.0, 103.0, 102.0]
    assert dtype == "R"
