#!/usr/bin/env bash
# TZ-3Z branch: three-zone shield + old-head — collect on 125, eval on H100 (remote from 125).
#
#   # On cursor-125 (4090 loopback):
#   cd ~/aerial-wam-v2
#   source experiments/aerial/scripts/env_4090.sh
#   STAMP=20260823 EPISODES=24 MODE=all bash experiments/aerial/scripts/v4_three_zone_branch.sh
#
# Modes: collect | collect_near | merge_near | merge_full | sync | eval | all | all_near | topup_near
# Doc: docs/handover/V4_THREE_ZONE_BRANCH_125_H100_20260823.md
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || echo "$HOME/aerial-wam-v2")"
cd "$ROOT"

# 125-local credentials (gitignored); see setup_h100_ssh_from_125.sh
if [[ -f "${ROOT}/experiments/aerial/scripts/env_h100_from_125.sh" ]]; then
  # shellcheck disable=SC1091
  source "${ROOT}/experiments/aerial/scripts/env_h100_from_125.sh"
fi

STAMP="${STAMP:-20260823}"
MODE="${MODE:-all}"
EPISODES="${EPISODES:-24}"
MAX_STEPS="${MAX_STEPS:-200}"
APPROACH_BIAS="${APPROACH_BIAS:-1}"
PER_LAYER="${PER_LAYER:-12}"
APPROACH_DIST_NEAR="${APPROACH_DIST_NEAR:-12}"
GOAL_DIST_M="${GOAL_DIST_M:-30}"
ONLY_LAYER="${ONLY_LAYER:-blocked}"
PROBE_NEAR_M="${PROBE_NEAR_M:-1.5}"
BLOCKED_SEED="${BLOCKED_SEED:-100}"
# Scan pool: use wide r60/p45-balanced positions (304 merged ep ≪ 1219 balanced → probe_no_hit).
ROLLOUT_DATASET="${ROLLOUT_DATASET:-experiments/aerial/rl/artifacts/dataset_v0_p45_balanced_20260820}"
MERGED_BASE_STAMP="${MERGED_BASE_STAMP:-20260823_merged}"
NEAR_STAMP="${NEAR_STAMP:-$STAMP}"
PRIOR_NEAR_STAMP="${PRIOR_NEAR_STAMP:-20260823f}"
NEAR_COMBINED_STAMP="${NEAR_COMBINED_STAMP:-}"

DATASET_NAME="dataset_v0_three_zone_oldhead_${STAMP}"
NEAR_DATASET_NAME="dataset_v0_three_zone_near_${NEAR_STAMP}"
DATASET_REL="experiments/aerial/rl/artifacts/${DATASET_NAME}"
LOG_DIR="${LOG_DIR:-logs}"
BRANCH_LOG="${LOG_DIR}/v4_three_zone_branch_${STAMP}.log"
COLLECT_LOG="${LOG_DIR}/v4_three_zone_collect_${STAMP}.log"
EVAL_LOG="${LOG_DIR}/v4_three_zone_eval_${STAMP}.log"

# H100 remote (override on 125 if host/key differs)
H100_USER="${H100_USER:-a25689}"
H100_HOST="${H100_HOST:-10.239.121.26}"
H100_PORT="${H100_PORT:-31126}"
H100_REPO="${H100_REPO:-/home/a25689/aerial-wam-v2}"

OLD_HEAD_REL="experiments/aerial/rl/artifacts/depth_ckpt_da3_r60_20260814/depth_step_2000_da3_ft_head.pt"
TAU_REL="experiments/aerial/rl/artifacts/tau_ckpt_foe_r60_20260815/tau_foe_calibrator.pt"
REF_CORPUS_REL="experiments/aerial/rl/artifacts/dataset_v0_p45_merged_20260821"

mkdir -p "$LOG_DIR" "$(dirname "$DATASET_REL")"

say() { echo "[tz-3z] $*" | tee -a "$BRANCH_LOG"; }

_ssh_base() {
  local target="${H100_USER}@${H100_HOST}"
  if [[ -n "${H100_SSH_KEY:-}" && -f "${H100_SSH_KEY}" ]]; then
    ssh -i "$H100_SSH_KEY" -o IdentitiesOnly=yes -o BatchMode=yes \
      -o StrictHostKeyChecking=accept-new -p "$H100_PORT" "$target" "$@"
    return
  fi
  if [[ -n "${H100_PASS:-}" ]] && command -v sshpass >/dev/null 2>&1; then
    sshpass -p "$H100_PASS" ssh \
      -o PreferredAuthentications=password \
      -o PubkeyAuthentication=no \
      -o NumberOfPasswordPrompts=1 \
      -o StrictHostKeyChecking=accept-new \
      -p "$H100_PORT" "$target" "$@"
    return
  fi
  ssh -o ConnectTimeout=30 -o StrictHostKeyChecking=accept-new -p "$H100_PORT" "$target" "$@"
}

ssh_h100() { _ssh_base "$@"; }

_tar_to_h100() { _ssh_base "$@"; }

phase_collect() {
  say "=== Phase A: collect on 125 (three_zone yaml, grab_depth, 5 Hz) ==="
  # shellcheck disable=SC1091
  source experiments/aerial/scripts/env_4090.sh
  export PYTHONPATH="${ROOT}${PYTHONPATH:+:$PYTHONPATH}"

  ARGS=(
    -m experiments.aerial.rl.collect_dataset
    --backend airsim
    --host 127.0.0.1
    --port 41451
    --config configs/aerial_rl.yaml
    --annotation "${ANNOTATION:-${ROOT}/artifacts/seen_airsim16_m1a20.json}"
    --episodes "$EPISODES"
    --max-steps "$MAX_STEPS"
    --step-hz 5.0
    --grab-depth
    --out "$DATASET_REL"
  )
  if [[ "$APPROACH_BIAS" == "1" ]]; then
    ARGS+=(--approach-bias --approach-dist-m 25)
  fi

  say "cmd: $AERIAL_PY ${ARGS[*]}"
  "$AERIAL_PY" "${ARGS[@]}" 2>&1 | tee -a "$COLLECT_LOG"

  test -f "${DATASET_REL}/manifest.json"
  say "collect done: ${DATASET_REL}"
}

phase_collect_near() {
  say "=== Phase A2: near-band scan collect (p45 pool + three_zone yaml) ==="
  # shellcheck disable=SC1091
  source experiments/aerial/scripts/env_4090.sh
  export PYTHONPATH="${ROOT}${PYTHONPATH:+:$PYTHONPATH}"
  NEAR_REL="experiments/aerial/rl/artifacts/${NEAR_DATASET_NAME}"

  ARGS=(
    experiments/aerial/scripts/v4_p45_collect.py
    --config configs/aerial_rl.yaml
    --host 127.0.0.1
    --port 41451
    --per-layer "$PER_LAYER"
    --only-layer "$ONLY_LAYER"
    --approach-dist-m "$APPROACH_DIST_NEAR"
    --goal-dist-m "$GOAL_DIST_M"
    --probe-near-m "$PROBE_NEAR_M"
    --blocked-seed "$BLOCKED_SEED"
    --rollout-dataset "$ROLLOUT_DATASET"
    --step-hz 5.0
    --max-steps "$MAX_STEPS"
    --out "$NEAR_REL"
  )
  say "cmd: $AERIAL_PY ${ARGS[*]}"
  "$AERIAL_PY" "${ARGS[@]}" 2>&1 | tee -a "$COLLECT_LOG"

  test -f "${NEAR_REL}/manifest.json"
  say "collect_near done: ${NEAR_REL}"
}

phase_merge_near() {
  say "=== Phase A2b: merge prior + supplement near corpora ==="
  # shellcheck disable=SC1091
  source experiments/aerial/scripts/env_4090.sh
  export PYTHONPATH="${ROOT}${PYTHONPATH:+:$PYTHONPATH}"

  local prior="${PRIOR_NEAR_STAMP}"
  local supp="${SUPP_NEAR_STAMP:-$NEAR_STAMP}"
  local combined="${NEAR_COMBINED_STAMP:-${prior}_${supp}}"
  local prior_rel="experiments/aerial/rl/artifacts/dataset_v0_three_zone_near_${prior}"
  local supp_rel="experiments/aerial/rl/artifacts/dataset_v0_three_zone_near_${supp}"
  local out_rel="experiments/aerial/rl/artifacts/dataset_v0_three_zone_near_${combined}"

  test -d "$prior_rel" || { say "ERROR: missing $prior_rel"; exit 1; }
  test -d "$supp_rel" || { say "ERROR: missing $supp_rel — run supplement collect_near first"; exit 1; }

  "$AERIAL_PY" -m experiments.aerial.rl._merge_datasets \
    --src "$prior_rel" --src "$supp_rel" --out "$out_rel" --overwrite 2>&1 | tee -a "$BRANCH_LOG"

  NEAR_STAMP="$combined"
  NEAR_DATASET_NAME="dataset_v0_three_zone_near_${combined}"
  say "merge_near done: ${out_rel} (prior=${prior} + supp=${supp})"
}

phase_merge_full() {
  say "=== Phase A3: merge open-field + near-band corpora ==="
  BASE_REL="experiments/aerial/rl/artifacts/dataset_v0_three_zone_oldhead_${MERGED_BASE_STAMP}"
  NEAR_REL="experiments/aerial/rl/artifacts/${NEAR_DATASET_NAME}"
  test -d "$BASE_REL" || { say "ERROR: missing $BASE_REL"; exit 1; }
  test -d "$NEAR_REL" || { say "ERROR: missing $NEAR_REL — run MODE=collect_near first"; exit 1; }

  "$AERIAL_PY" -m experiments.aerial.rl._merge_datasets \
    --src "$BASE_REL" --src "$NEAR_REL" --out "$DATASET_REL" --overwrite 2>&1 | tee -a "$BRANCH_LOG"
  say "merge_full done: ${DATASET_REL} (base=${MERGED_BASE_STAMP} + near stamp=${STAMP})"
}

phase_sync() {
  say "=== Phase B: tar sync 125 → H100 ==="
  # shellcheck disable=SC1091
  source experiments/aerial/scripts/env_h100_from_125.sh
  test -d "$DATASET_REL" || { say "ERROR: missing $DATASET_REL — run MODE=collect first"; exit 1; }

  ssh_h100 "mkdir -p ${H100_REPO}/experiments/aerial/rl/artifacts"
  tar -C "$(dirname "$DATASET_REL")" -cf - "$(basename "$DATASET_REL")" | \
    _tar_to_h100 "tar xf - -C ${H100_REPO}/experiments/aerial/rl/artifacts"

  ssh_h100 "
    set -e
    D=${H100_REPO}/${DATASET_REL}
    N=\$(ls \"\$D\"/episode_*.npz 2>/dev/null | wc -l)
    test -f \"\$D/manifest.json\"
    echo H100_NPZ=\$N
    du -sh \"\$D\"
  " | tee -a "$BRANCH_LOG"
  say "sync done"
}

_run_h100_eval() {
  local tag="$1"
  local heldout="$2"
  local corpus_rel="$3"
  ssh_h100 bash -s <<REMOTE
set -euo pipefail
export SKIP_H100_GIT=1
cd ${H100_REPO}
if [[ "${SKIP_H100_GIT:-0}" != "1" ]]; then
  git fetch --all 2>/dev/null || true
  git checkout -B aerial-rl-skeleton origin/aerial-rl-skeleton 2>/dev/null \
    || git pull --ff-only 2>/dev/null || true
fi
source experiments/aerial/scripts/env_h100.sh
export PYTHONPATH="\${PWD}\${PYTHONPATH:+:\$PYTHONPATH}"

DEPTH=${H100_REPO}/${OLD_HEAD_REL}
TAU=${H100_REPO}/${TAU_REL}
DATA=${H100_REPO}/${corpus_rel}
EMIT=${H100_REPO}/artifacts/v4_three_zone_branch_${tag}_${STAMP}.json

test -f "\$DEPTH" || { echo "MISSING depth ckpt: \$DEPTH"; exit 2; }
test -f "\$TAU" || { echo "MISSING tau ckpt: \$TAU"; exit 2; }
test -d "\$DATA" || { echo "MISSING dataset: \$DATA"; exit 2; }

echo "[h100-eval] ${tag} heldout=${heldout} corpus=${corpus_rel}"
"\$AERIAL_PY" -m experiments.aerial.rl.v4_three_zone_eval \\
  --dataset "\$DATA" \\
  --depth-ckpt "\$DEPTH" \\
  --tau-ckpt "\$TAU" \\
  --config configs/aerial_rl.yaml \\
  --device cuda \\
  --heldout-frac ${heldout} --split-seed 0 \\
  --emit "\$EMIT"
echo "[h100-eval] wrote \$EMIT"
REMOTE
}

phase_eval() {
  say "=== Phase C: H100 offline eval (remote from 125) ==="
  # Primary: new corpus if synced; fallback: p45 merged for regression compare
  local corpus="$DATASET_REL"
  if ! ssh_h100 "test -d ${H100_REPO}/${DATASET_REL}" 2>/dev/null; then
    say "WARN: ${DATASET_REL} not on H100 — eval on reference ${REF_CORPUS_REL}"
    corpus="$REF_CORPUS_REL"
  fi

  _run_h100_eval "hold035" "0.35" "$corpus" 2>&1 | tee -a "$EVAL_LOG"
  _run_h100_eval "full77" "0.0" "$corpus" 2>&1 | tee -a "$EVAL_LOG"
  say "eval done — see H100 artifacts/v4_three_zone_branch_*_${STAMP}.json"
}

case "$MODE" in
  collect)      phase_collect ;;
  collect_near) phase_collect_near ;;
  merge_near)   phase_merge_near ;;
  merge_full)   phase_merge_full ;;
  sync)         phase_sync ;;
  eval)         phase_eval ;;
  all)
    phase_collect
    phase_sync
    phase_eval
    ;;
  all_near)
    phase_collect_near
    phase_merge_full
    phase_sync
    phase_eval
    ;;
  topup_near)
    # Supplement near-band: collect PER_LAYER more, merge with PRIOR_NEAR_STAMP, rebuild full corpus.
    SUPP_NEAR_STAMP="${SUPP_NEAR_STAMP:-$NEAR_STAMP}"
    phase_collect_near
    phase_merge_near
    phase_merge_full
    phase_sync
    phase_eval
    ;;
  *)
    echo "unknown MODE=$MODE (use collect|collect_near|merge_near|merge_full|sync|eval|all|all_near|topup_near)" >&2
    exit 1
    ;;
esac

say "DONE mode=$MODE stamp=$STAMP"
