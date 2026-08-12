#!/usr/bin/env python3
"""Score a known structure against a .sml with faulon-ng's own ChiefJustice.

Answers the one question a failed SA run cannot: is the truth missed because the
search never reached it (sampling), or because the scoring function ranks it
below the decoys (scoring)? Rebuilds the exact judge stack from
faulon_ng/cli/pipeline.py, then binds the reference SMILES to the slot contract
via bind_oracle_map_from_smiles so it is scored on the same landscape the SA sees.

Usage: score_truth.py FILE.SML "TRUTH_SMILES" ["DECOY_SMILES" ...]
"""
import sys

from faulon_ng.scoring.hose_table_loader import CHOSEN_MAX_RADIUS
from faulon_ng.scoring.candidate_pairs import build_all_candidates
from faulon_ng.scoring.chief_justice import ChiefJustice
from faulon_ng.scoring.cosy_judge import COSYJudge
from faulon_ng.scoring.environment_judge import EnvironmentJudge, load_shift_env_probs
from faulon_ng.scoring.h_counts import select_h_counts
from faulon_ng.scoring.hmbc_judge import HMBCJudge
from faulon_ng.scoring.hsqc_judge import HSQCJudge
from faulon_ng.scoring.multisphere_13c_judge import MultiSphere13CJudge
from faulon_ng.scoring.nmr_problem import load_sml
from faulon_ng.scoring.oracle_map_binding import bind_oracle_map_from_smiles
from faulon_ng.scoring.plausibility_judge import PlausibilityJudge


def build_chief(problem, hmbc_4j_weight=10):
    """Mirror of pipeline.py step 4 -- same judges, same weights."""
    hmbc = HMBCJudge(peaks=list(problem.hmbc_peaks), weights=(100, 100, hmbc_4j_weight))
    hsqc = HSQCJudge(peaks=list(problem.hsqc_peaks))
    cosy = COSYJudge(peaks=list(problem.cosy_peaks))
    plausibility = PlausibilityJudge()
    env = EnvironmentJudge.from_problem(problem, load_shift_env_probs())
    c13 = MultiSphere13CJudge.from_data_file(
        carbon_slots=list(problem.atoms), max_radius=CHOSEN_MAX_RADIUS
    )
    return ChiefJustice(judges=[
        (1.0, hmbc), (1.0, hsqc), (1.0, cosy),
        (1.0, plausibility), (0.5, env), (1.0, c13),
    ])


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    sml, smiles_list = sys.argv[1], sys.argv[2:]

    problem = load_sml(sml)
    select_h_counts(problem)
    problem = build_all_candidates(problem)
    table = load_shift_env_probs()

    for weight in (10, 0):
        chief = build_chief(problem, hmbc_4j_weight=weight)
        label = "graded 4J (default)" if weight else "rigid 4J (LSD-like)"
        print(f"\n=== hmbc-4j-weight={weight}  [{label}] ===")
        for smi in smiles_list:
            try:
                graph = bind_oracle_map_from_smiles(
                    smi, list(problem.atoms), table, problem=problem
                )
                print(f"  {chief.compute(graph):.4f}   {smi}")
            except Exception as exc:                     # noqa: BLE001 - diagnostic
                print(f"  FEHLER {type(exc).__name__}: {str(exc)[:90]}   {smi}")


if __name__ == "__main__":
    main()
