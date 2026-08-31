# V4-MVP M5 — run on 125 (offline)

Design: docs/superpowers/specs/2026-08-16-v4-mvp-design.md §4–§5.

## Goal
Run authoritative **V4-①** (progress vs Heuristic) + **V4-④** (safety no-regression), merge, update living docs.
You are ON the 4090 host (renderer 127.0.0.1:41451 is up). Prefer **local rollout** with `configs/aerial_rl_rollout.yaml` (grab_depth true). H100 via `ssh h100-25`.

## Hard rules
- Do NOT flip `enable_policy_update` in production yaml (even if merge PASS — leave for human).
- Do NOT push GitHub; `git push origin main` only.
- Honest FAIL is OK — record numbers; no threshold gaming / tied-zero soft PASS for safety.
- Load actor ckpt from H100: `~/aerial-wam-v2/experiments/aerial/rl/artifacts/v4_ac_ckpt_20260816/v4_ac_latest.pt` (scp via h100-25 if needed).

## Work
1. Implement `experiments/aerial/scripts/v4_gate_run_partials.py` (or extend `_v4_gate`) to:
   - obstacle-facing scan n=8 (same harness as V0 ② / V1-①; headon or r60 dataset)
   - run HeuristicPolicy → progress sums
   - run ImaginationActorPolicy / actor from ckpt → progress sums
   - run V4 shield-on arm for hard coll_rate; compare to V1-① baseline (0.50 from rigorous partial, or remeasure V1 arm same starts)
   - optional V0-④ near ratio ≤0.80
   - emit `v4_partial_1_*.json`, `v4_partial_4_*.json`, merge → `v4_gate_r60_20260816.json`
2. Use depth ckpt r60 + foe_calibrated τ if shield needs them (paths under aerial-rl-skeleton or scp from H100).
3. Update `docs/handover/V4_GATE_STATUS.md` M5 result.
4. Write `docs/handover/V4_M5_125_STATUS.md` with HEAD, cmds, numbers, merge ok?, yaml still false.
5. Commit + push origin.

If renderer/scan fails: document and stop honestly.

Start by reading actor_critic.py, v0_rollout_eval, v1_gate_run_partials.py for patterns.
