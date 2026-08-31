# V4-① progress diagnosis (125, 2026-08-17)

- **status**: **done**
- **script**: `experiments/aerial/scripts/v4_progress_diag.py` (`37e5cb9`)
- **JSON**: `artifacts/v4_progress_diag_20260817.json`
- **log**: `logs/v4_progress_diag_20260817.log`
- **ckpt**: `v4_ac_ckpt_20260817_wm_rh_goal_rgb/v4_ac_latest.pt` + RH WM `wm_step_1000.pt`
- **dataset**: `dataset_v0_headon_20260811` (same harness family as goal+z0 gate)

## Verdict

**Actor is anti-aligned with the goal on deploy.** Heuristic is correctly goal-seeking. This is not a thin margin failure — direction is wrong.

| Metric (n=7 scored; 1 spawn drop) | Actor | Heuristic |
|---|---|---|
| mean progress | **−10.35** | **+9.11** |
| mean cos(path, goal) | **−0.44** | **+0.97** |
| mean cos(first_act, goal_body) | **−0.88** | **+0.99** |
| frac path cos &lt; 0 | **6/7 (86%)** | 0 |

Representative ep0: `goal_body0 ≈ [+30, 0, 0.85]` (body forward); heur first act `[+1, 0, 0]`; actor first act **`[-1, -0.4, -0.4]`** (saturated retreat). Same pattern on other scored eps (`cos_first_act_actor ≈ −0.88` every time).

## Code facts (confirmed in diag)

| Fact | Meaning |
|---|---|
| `actor_has_no_goal_input: true` | `LatentActorDeployPolicy.act` = encode(RGB+proprio4) → `act_latent(z)` — **no goal** |
| `encode_uses_proprio4_only: true` | state vel slots zeroed in deploy do **not** enter encode |
| `heuristic_uses_goal_getter: true` | oracle steers with privileged goal |

So “deploy vel=0” is a red herring for encode; the structural gap is **π(a\|z) without goal** vs heuristic **π(a\|goal, proprio)**. Mock train goal `start→[30,0,5]` cannot put goal into z at deploy.

## Root cause (2026-08-18, recorded)

Not a deploy-only miss. Two stacked defects:

1. **Spec**: V4-MVP In table is `act_latent(z)` / `V(z)` — goal never enters π. Implementation is faithful.
2. **Train**: M5d 300 iter used `_mock_goal_episode()` (one start→`[30,0,5]`). Phase 2 headon RGB was a 2-iter probe, not diverse-goal AC.

Together: `π(z)` brands one goal’s action, insensitive to the deploy goal. M5c `goal_rel≈0` → weak policy (−3.17); M5d strong single-goal reward → **worse** (−8.74). **Longer train on current π is predicted to worsen.**

① vs Heuristic is **not robustly reachable** without goal leaking into z (RGB RSSM has no 3-D waypoint channel). Same class as 08-11 ④ (spec revision, not more tuning). Proposal: [`V4_SIGNAL1_STRUCTURAL_REFREEZE_PROPOSAL.md`](V4_SIGNAL1_STRUCTURAL_REFREEZE_PROPOSAL.md).

### Scope of this root cause — what it does NOT explain (2026-08-18)

Two corrections to the wording above:

1. **Not "structurally unreachable" in the strict sense.** Goals here are systematically body-forward (`goal_body0 ≈ [+30, 0, 0.85]`), so a goal-blind *constant-forward* policy would score positive progress. The honest claim is **not robustly reachable**: any pass would ride on "eval goals happen to align with the branded direction". Riding that is 凑过 and is now explicitly forbidden (proposal §3 / §4 明确不做).
2. **Branding does not explain the *negative sign*.** Line above ("Deploy goals differ → anti-align") is inconsistent with this doc's own ep0 numbers: the train goal `start→[30,0,5]` and the deploy goal `[+30, 0, 0.85]` are **both forward**, so branding predicts cos **positive**, not a saturated retreat `[-1,-0.4,-0.4]` on *every* scored ep. Branding explains the **constancy** and the M5c→M5d magnitude growth; the **direction** is unexplained.

Statically ruled out as the cause of directionality: `advance_goal_rel_body` sign is correct (`g[:3] = g[:3] - disp`, `goal_features.py:71` — forward *reduces* remaining distance), and `maneuver = ‖a‖` is direction-agnostic. Remaining suspects: the learned RH `progress` output and `p_coll`. If `p_coll` dominates in imagination, retreat *is* the imagined optimum — which would also explain why ④ PASSes (0.000 collisions) while ① is −8.74. Read-only discriminator + pre-committed decision rule: proposal **§A**. Until §A resolves, do **not** assume the In-table revision alone is sufficient.

`enable_policy_update` remains **false**.
