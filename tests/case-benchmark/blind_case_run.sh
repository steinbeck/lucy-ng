#!/usr/bin/env bash
# blind_case_run.sh — run ONE blind lucy-ng:case elucidation on a sanitised
# dataset in a fresh, isolated, headless `claude` process, with a resume-on-stall
# backstop.
#
# Blindness: the fresh process starts with EMPTY conversation context and is
# given ONLY the dataset path + the molecular formula (read from the dataset's own
# molecular-formula.txt / molecularformula.txt). It runs in a neutral scratch cwd
# (no project memory) and a system-prompt fence forbids reading ground-truth /
# answer-key locations. Grading (correctness vs truth) happens SEPARATELY, later,
# in grade_blind.py — never inside the solving process.
#
# Resume-on-stall (B): the run is a persisted session; if it exits without
# writing final_results.md it is nudged to continue (`claude --resume`), which
# triggers the skill's own stall-recovery, bounded by MAX_ATTEMPTS + a deadline.
# (The skill itself also carries a headless anti-stall caveat as of the
# "prevent headless/non-interactive orchestrator stall" fix; B is the
# deterministic backstop on top of that.)
#
# Usage: blind_case_run.sh <CASE_DIR> <RESULTS_DIR> [full|smoke]
#
# Env (see README.md):
#   CASE_PROJECT_DIR   lucy-ng repo root (for .venv/bin). Default: repo of this script.
#   CLAUDE_MODEL       model id. Default: claude-opus-4-8
#   CASE_ANSWERKEY_DIR optional dir the fence explicitly forbids reading.
#   CASE_RUN_MAX_ATTEMPTS (default 8), CASE_RUN_CALL_TIMEOUT s (3600),
#   CASE_RUN_DEADLINE_S total per dataset (9000)
set -u
CASE_DIR="$1"; RESULTS_DIR="$2"; MODE="${3:-full}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CASE_PROJECT_DIR="${CASE_PROJECT_DIR:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
CLAUDE_MODEL="${CLAUDE_MODEL:-claude-opus-4-8}"
CASE_ANSWERKEY_DIR="${CASE_ANSWERKEY_DIR:-}"
MAX_ATTEMPTS="${CASE_RUN_MAX_ATTEMPTS:-8}"
CALL_TIMEOUT="${CASE_RUN_CALL_TIMEOUT:-3600}"
DEADLINE_S="${CASE_RUN_DEADLINE_S:-9000}"

CASE_NAME="$(basename "$CASE_DIR")"
# molecular formula: accept either filename convention
MF_FILE=""
for f in molecular-formula.txt molecularformula.txt; do
  [ -f "$CASE_DIR/$f" ] && { MF_FILE="$CASE_DIR/$f"; break; }
done
mkdir -p "$RESULTS_DIR"
if [ -z "$MF_FILE" ]; then
  echo '{"case":"'"$CASE_NAME"'","status":"error","reason":"no_MF_file"}' > "$RESULTS_DIR/meta.json"; exit 2
fi
MF="$(tr -d '[:space:]' < "$MF_FILE")"

# put lucy on PATH if a repo venv exists
[ -d "$CASE_PROJECT_DIR/.venv/bin" ] && export PATH="$CASE_PROJECT_DIR/.venv/bin:$PATH"

rm -rf "$CASE_DIR/analysis"
SCRATCH="$(mktemp -d "${TMPDIR:-/tmp}/blindcase.XXXXXX")"
SID="$(python3 -c 'import uuid;print(uuid.uuid4())')"
FR="$CASE_DIR/analysis/final_results.md"
SMOKE=""; [ "$MODE" = "smoke" ] && SMOKE=" --smoke-test"

FENCE="BLIND CASE EVALUATION. Solve an unknown structure using ONLY the NMR data at the given dataset path plus the provided molecular formula. Do NOT read, list or grep any ground-truth / answer-key / benchmark-results location${CASE_ANSWERKEY_DIR:+ (in particular ${CASE_ANSWERKEY_DIR})} — using it invalidates the run. Never attempt dereplication; never look the compound up by name.

HEADLESS EXECUTION: there is no event loop to wake you after you stop. Never background a teammate/solver and then end your turn to 'wait' — drive every stage to completion INLINE (poll TaskList + the expected analysis/ artefacts), and do not stop until ${CASE_DIR}/analysis/final_results.md exists."

NUDGE="Continue the in-progress CASE workflow for ${CASE_DIR} (formula ${MF}). The previous turn ended while a stage ran in the background — headless, it was not resumed. Inspect ${CASE_DIR}/analysis (iteration_*/solncounter, iteration_*/solutions.smi, CASE-PROGRESS.md) for what finished, then CONTINUE inline until ${CASE_DIR}/analysis/final_results.md exists. Same blindness rules; no dereplication."

run_claude () { # $1 new|resume
  if [ "$1" = new ]; then
    CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1 timeout "$CALL_TIMEOUT" \
      claude -p "/lucy-ng:case $CASE_DIR $MF$SMOKE" --session-id "$SID" \
      --model "$CLAUDE_MODEL" --dangerously-skip-permissions \
      --append-system-prompt "$FENCE" --add-dir "$CASE_DIR" \
      >> "$RESULTS_DIR/run.log" 2>&1
  else
    CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1 timeout "$CALL_TIMEOUT" \
      claude --resume "$SID" -p "$NUDGE" \
      --model "$CLAUDE_MODEL" --dangerously-skip-permissions \
      --append-system-prompt "$FENCE" --add-dir "$CASE_DIR" \
      >> "$RESULTS_DIR/run.log" 2>&1
  fi
}

START=$(date +%s); DEADLINE=$((START + DEADLINE_S))
cd "$SCRATCH" || exit 3
ATTEMPT=0
while [ "$ATTEMPT" -lt "$MAX_ATTEMPTS" ]; do
  ATTEMPT=$((ATTEMPT + 1))
  echo "=== [$CASE_NAME] attempt $ATTEMPT ($([ $ATTEMPT -eq 1 ] && echo new || echo resume)) $(date -u +%H:%M:%S) ===" >> "$RESULTS_DIR/run.log"
  if [ "$ATTEMPT" -eq 1 ]; then run_claude new; else run_claude resume; fi
  [ -f "$FR" ] && break
  [ "$MODE" = smoke ] && break
  [ "$(date +%s)" -ge "$DEADLINE" ] && { echo "[deadline]" >> "$RESULTS_DIR/run.log"; break; }
done
END=$(date +%s); RUNTIME=$((END - START))
rm -rf "$SCRATCH"

[ -d "$CASE_DIR/analysis" ] && mv "$CASE_DIR/analysis" "$RESULTS_DIR/analysis"
FRR="$RESULTS_DIR/analysis/final_results.md"; FR_EXISTS=false; TOPSMI=""
if [ -f "$FRR" ]; then
  FR_EXISTS=true
  TOPSMI="$(grep -aoiE 'SMILES[^A-Za-z0-9]+[^ `|)]+' "$FRR" | head -1 | sed -E 's/.*SMILES[^A-Za-z0-9]+//I')"
  case "$TOPSMI" in *' '*|"") TOPSMI="";; esac
  echo "$TOPSMI" | grep -qE '[=#()1-9]|[cC][cC]' || TOPSMI=""
fi
printf '{"case":"%s","mf":"%s","mode":"%s","attempts":%d,"runtime_s":%d,"final_results":%s,"top_smiles":"%s"}\n' \
  "$CASE_NAME" "$MF" "$MODE" "$ATTEMPT" "$RUNTIME" "$FR_EXISTS" "${TOPSMI//\"/}" > "$RESULTS_DIR/meta.json"
echo "[$CASE_NAME] attempts=$ATTEMPT runtime=${RUNTIME}s final_results=$FR_EXISTS"
