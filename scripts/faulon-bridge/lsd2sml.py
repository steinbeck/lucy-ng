#!/usr/bin/env python3
"""Convert a lucy-ng `compound.lsd` into a SENECA `.sml` for faulon-ng.

Throwaway bridge for a feasibility test, not production code.

Why the .lsd and not the raw peak lists: lucy-ng's value sits in the curation
between them. CASE13's `hmbc_raw.json` holds 4402 peaks (mostly noise) and its
`hsqc_raw.json` only 2; the `compound.lsd` holds the 15 HMBC and 6 HSQC that the
nmr-chemist kept and the devil's advocate cleared. faulon-ng does no DEPT
analysis of its own, so the multiplicities in the MULT block are exactly the
part it cannot derive.

Mapping (SENECA spectrum ids on the left):
    carbon1d   <- MULT carbon shifts
    dept135    <- MULT, sign by multiplicity (CH/CH3 up, CH2 down)
    hetcor     <- HSQC   (f1 = 1H, f2 = 13C)
    hetcorlr   <- HMBC   (f1 = 1H, f2 = 13C)
    hhcosy     <- COSY   (f1 = 1H, f2 = 1H)

Usage:  lsd2sml.py compound.lsd C12H12N2O3 out.sml [--title NAME]
"""
from __future__ import annotations

import re
import sys
from xml.sax.saxutils import escape

# "MULT 5 C 2 1     ; 148.38 CH  (H 8.892)"
MULT_RE = re.compile(
    r"^MULT\s+(\d+)\s+([A-Z][a-z]?)\s+(\d+)\s+(\d+)\s*(?:;\s*(.*))?$"
)
SHIFT_RE = re.compile(r"([-+]?\d+\.\d+)")
HSHIFT_RE = re.compile(r"\(H\s+([-+]?\d+\.\d+)\)")
# "HMBC (4 5) 10" or "HMBC 3 11" -- trailing field is always the proton side
CORR_RE = re.compile(r"^(HSQC|HMBC|COSY)\s+(\([\d\s]+\)|\d+)\s+(\d+)")


class Atom:
    __slots__ = ("idx", "element", "nh", "cshift", "hshift")

    def __init__(self, idx, element, nh, cshift, hshift):
        self.idx, self.element, self.nh = idx, element, nh
        self.cshift, self.hshift = cshift, hshift


def parse_lsd(path):
    """Return (atoms_by_index, correlations) from a compound.lsd."""
    atoms, corrs = {}, []
    for line in open(path):
        line = line.rstrip("\n")
        m = MULT_RE.match(line)
        if m:
            idx, element, _bonds, nh = int(m.group(1)), m.group(2), m.group(3), int(m.group(4))
            comment = m.group(5) or ""
            # First float in the comment is the carbon shift; heteroatoms have none.
            cs = SHIFT_RE.search(comment)
            hs = HSHIFT_RE.search(comment)
            atoms[idx] = Atom(
                idx, element, nh,
                float(cs.group(1)) if cs and element == "C" else None,
                float(hs.group(1)) if hs else None,
            )
            continue
        m = CORR_RE.match(line)
        if m:
            kind, cside, hside = m.group(1), m.group(2), int(m.group(3))
            targets = [int(x) for x in re.findall(r"\d+", cside)]
            corrs.append((kind, targets, hside))
    return atoms, corrs


def signal(sid, locs, phase=0, intensity=0.0):
    loc = "".join(
        f'      <location role="{role}">{val:.4f}</location>\n' for role, val in locs
    )
    return (
        f'    <signal id="{sid}">\n{loc}'
        f'      <intensity type="relative">{intensity}</intensity>\n'
        f"      <normalizefactor>1.0</normalizefactor>\n"
        f"      <phase>{phase}</phase>\n"
        f"    </signal>\n"
    )


def spectrum(sid, stype, dim, axes, signals):
    axis = "".join(
        f'      <axisinfo role="{role}">\n'
        f"        <nucleus>{nuc}</nucleus>\n"
        f"        <property>shift</property>\n"
        f"        <unit>ppm</unit>\n"
        f"      </axisinfo>\n"
        for role, nuc in axes
    )
    return (
        f'  <spectrum xmlns="http://www.nmrshiftdb.org/" type="NMR Experiment" '
        f'id="{sid}" convention="Seneca">\n'
        f"    <spectruminfo>\n"
        f"      <dimension>{dim}</dimension>\n"
        f"      <type>{stype}</type>\n"
        f'      <frequency unit="MHz">0.0</frequency>\n'
        f"      <solvent>null</solvent>\n"
        f'      <standard role="calibration"></standard>\n'
        f"{axis}"
        f"    </spectruminfo>\n"
        f"{''.join(signals)}"
        f"  </spectrum>\n"
    )


def build(atoms, corrs, formula, title):
    carbons = [a for a in atoms.values() if a.element == "C" and a.cshift is not None]
    carbons.sort(key=lambda a: -a.cshift)

    # --- molecule block: every heavy atom, as SENECA expects -----------------
    mol = []
    for i, a in enumerate(sorted(atoms.values(), key=lambda a: a.idx)):
        # Same precision as the signal locations below. faulon-ng matches peaks
        # to atoms with eps = 1e-06 ppm, i.e. exact equality -- writing 165.0
        # here and 164.9600 in the signal makes every peak unassignable.
        shift = (
            f'      <float title="assignedCarbonShift">{a.cshift:.4f}</float>\n'
            if a.cshift is not None else ""
        )
        mol.append(
            f'    <atom id="a{i}">\n'
            f'      <string builtin="elementType">{a.element}</string>\n'
            f'      <integer builtin="hydrogenCount">{a.nh}</integer>\n'
            f"{shift}"
            f"    </atom>\n"
        )

    specs = []

    # --- 1D 13C --------------------------------------------------------------
    specs.append(spectrum(
        "carbon1d", "13C NMR", 1, [("f1", "13C")],
        [signal(f"carbon1d.p{i}", [("f1", a.cshift)], phase=1, intensity=1.0)
         for i, a in enumerate(carbons)],
    ))

    # --- DEPT-135: protonated carbons, CH2 negative --------------------------
    # faulon-ng derives no multiplicities itself; this carries lucy-ng's
    # validated CH/CH2/CH3 assignment across in the sign convention SENECA uses.
    dept = [a for a in carbons if a.nh > 0]
    specs.append(spectrum(
        "dept135", "DEPT135", 1, [("f1", "13C")],
        [signal(f"dept135.p{i}", [("f1", a.cshift)],
                phase=(-1 if a.nh == 2 else 1),
                intensity=(-1.0 if a.nh == 2 else 1.0))
         for i, a in enumerate(dept)],
    ))

    # --- 2D correlations -----------------------------------------------------
    def two_d(kind, sid, stype, f1_nuc, f2_nuc):
        sigs, dropped = [], 0
        n = 0
        for k, targets, hside in corrs:
            if k != kind:
                continue
            h = atoms.get(hside)
            if h is None or h.hshift is None:
                dropped += 1
                continue
            if kind == "COSY":
                partner = atoms.get(targets[0])
                if partner is None or partner.hshift is None:
                    dropped += 1
                    continue
                f2 = partner.hshift
            else:
                # A grouped C-side "(4 5)" is ONE observed peak whose F1 could not
                # be resolved between two carbons. The midpoint would be tidier but
                # matches NO atom under eps = 1e-06, so the peak would be dropped
                # entirely -- the worst outcome. Emit one signal per candidate
                # instead: that is what the data actually says (either carbon may
                # own this peak) and grading them is precisely faulon-ng's job.
                shifts = [atoms[t].cshift for t in targets
                          if t in atoms and atoms[t].cshift is not None]
                if not shifts:
                    dropped += 1
                    continue
                for t, f2 in zip(
                    [t for t in targets if t in atoms and atoms[t].cshift is not None],
                    shifts,
                ):
                    # Skip the carbon this proton sits on: that branch of a grouped
                    # correlation would be a 1J, not an nJ. faulon-ng rejects it
                    # anyway (D-02 skip); not emitting it keeps the log clean.
                    if kind == "HMBC" and t == hside:
                        continue
                    sigs.append(signal(f"{sid}.p{n}", [("f1", h.hshift), ("f2", f2)]))
                    n += 1
                continue
            sigs.append(signal(f"{sid}.p{n}", [("f1", h.hshift), ("f2", f2)]))
            n += 1
        return spectrum(sid, stype, 2, [("f1", f1_nuc), ("f2", f2_nuc)], sigs), len(sigs), dropped

    for kind, sid, stype, n1, n2 in (
        ("HSQC", "hetcor", "1JCH correlation", "1H", "13C"),
        ("HMBC", "hetcorlr", "nJCH correlation", "1H", "13C"),
        ("COSY", "hhcosy", "HH correlation", "1H", "1H"),
    ):
        block, kept, dropped = two_d(kind, sid, stype, n1, n2)
        specs.append(block)
        note = f" ({dropped} ohne ppm verworfen)" if dropped else ""
        print(f"  {sid:10} {kept:3} Signale{note}", file=sys.stderr)

    return (
        '<?xml version="1.0" ?>\n'
        f'<senecadataset title="{escape(title)}">\n'
        f"  <formula>{escape(formula)}</formula>\n"
        '  <molecule xmlns="http://www.xml-cml.org/cml.dtd" title="ConnectionTable">\n'
        f"{''.join(mol)}"
        "  </molecule>\n"
        f"{''.join(specs)}"
        "</senecadataset>\n"
    )


def main():
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    lsd, formula, out = sys.argv[1], sys.argv[2], sys.argv[3]
    title = sys.argv[5] if len(sys.argv) > 5 and sys.argv[4] == "--title" else "lucy-ng export"

    atoms, corrs = parse_lsd(lsd)
    if not atoms:
        sys.exit(f"no MULT lines parsed from {lsd} — wrong file?")
    print(f"  {len(atoms)} Schweratome, "
          f"{sum(1 for a in atoms.values() if a.element == 'C')} davon C", file=sys.stderr)

    xml = build(atoms, corrs, formula, title)
    open(out, "w").write(xml)
    print(f"  -> {out} ({len(xml)} Bytes)", file=sys.stderr)


if __name__ == "__main__":
    main()
