"""
agent.py — Autonomous Root-Cause Investigator Agent.

Orchestrates the investigation loop:
  1. Observe initial failure
  2. Build Failure Fingerprint
  3. Formulate Competing Hypotheses (H1, H2, H3)
  4. Select Next Experiment via Information Gain Scoring
  5. Execute Experiment via REAL Engine
  6. Gather Evidence & Eliminate False Hypotheses
  7. Evaluate Confidence (HIGH / MEDIUM / LOW / NOT_CONFIRMED)
  8. Generate Evidence-Backed Root Cause Report

Zero LLM or external AI dependencies — 100% local, deterministic agentic reasoning.
"""
import uuid
from typing import Dict, Any, List, Optional
from engine.crash_verifier import run_single_hook
from app.agent.fingerprint import create_failure_fingerprint
from app.agent.state_analyzer import analyze_hook_observation
from app.agent.hypothesis_engine import generate_competing_hypotheses
from app.agent.experiment_selector import select_next_experiment, calculate_information_scores
from app.agent.experiment_runner import execute_experiment
from app.agent.root_cause import evaluate_evidence_and_update_hypotheses
from app.agent.report_generator import generate_investigation_report


class AutonomousInvestigationAgent:
    """
    Deterministic Autonomous Root-Cause Investigator Agent.
    """

    def __init__(self, max_experiments: int = 20):
        self.max_experiments = max_experiments

    def investigate(self, seed: int = 42, strategy: str = "naive", initial_hook: Optional[int] = None) -> Dict[str, Any]:
        """
        Run the autonomous investigation loop for a given seed and strategy.
        """
        investigation_id = f"inv_{uuid.uuid4().hex[:8]}"

        activity_log: List[Dict[str, Any]] = []

        # ─── 1. INITIAL OBSERVATION PHASE ─────────────────────────────────────
        # If user explicitly chose a target hook, respect it directly.
        # If user chose 'Auto Sweep' (initial_hook is None), scan to find first BUG hook.
        if initial_hook is not None:
            target_hook = initial_hook
            obs_res = run_single_hook(seed=seed, strategy=strategy, hook=target_hook)
        else:
            # Auto Sweep mode: default to H11 or scan for first BUG hook
            target_hook = 11
            obs_res = run_single_hook(seed=seed, strategy=strategy, hook=target_hook)
            if obs_res.verdict == "SAFE":
                for h in range(1, 13):
                    res = run_single_hook(seed=seed, strategy=strategy, hook=h)
                    if res.verdict == "BUG":
                        obs_res = res
                        target_hook = h
                        break

        obs_map = analyze_hook_observation(obs_res)
        fp = obs_map["fingerprint"]

        activity_log.append({
            "stage": "OBSERVE",
            "message": f"Observed crash hook H{target_hook:02d} ({obs_res.phase}) under {strategy.upper()} Recovery — Verdict: {obs_res.verdict}",
            "details": f"Fingerprint: {fp['signature']} | Failed Invariants: {obs_map['failed_invariants'] or 'None'}",
        })

        # ─── 2. FORMULATE COMPETING HYPOTHESES ────────────────────────────────
        hypotheses = generate_competing_hypotheses(obs_map, fp)
        
        hyp_names = [f"'{h['name']}' ({h['id']})" for h in hypotheses]
        activity_log.append({
            "stage": "HYPOTHESIS",
            "message": f"Formulated {len(hypotheses)} competing hypotheses: {', '.join(hyp_names)}",
            "details": f"Initial evidence evaluation for hook H{target_hook:02d}.",
        })

        # If observed target hook is SAFE (e.g. under Safe Recovery or for safe crash hooks):
        if obs_res.verdict == "SAFE":
            for h in hypotheses:
                h["status"] = "REJECTED"
                h["score"] = 0.05

            activity_log.append({
                "stage": "CONCLUSION",
                "message": f"All hypotheses REJECTED — No invariant violations detected for Hook H{target_hook:02d} under {strategy.upper()} Recovery.",
                "details": f"All 4 formal invariants (INV-1 to INV-4) passed cleanly.",
            })
            activity_log.append({
                "stage": "FINAL",
                "message": f"Investigation complete. Verdict: VERIFICATION_PASSED_SAFE",
                "details": f"Target hook H{target_hook:02d} under {strategy.upper()} strategy satisfied all invariants.",
            })

            return generate_investigation_report({
                "id": investigation_id,
                "seed": seed,
                "strategy": strategy,
                "status": "VERIFICATION_PASSED_SAFE",
                "initial_hook": target_hook,
                "current_hook": target_hook,
                "observations": [obs_map],
                "fingerprints": [fp],
                "hypotheses": hypotheses,
                "experiments": [{
                    "experiment_type": "SINGLE_HOOK_INSPECTION",
                    "target_hook": target_hook,
                    "verdict": "SAFE",
                    "evidence_summary": f"Hook {target_hook} under {strategy.upper()} Recovery passed all invariants (0 records exposed)."
                }],
                "activity_log": activity_log,
                "confidence": "HIGH",
                "confidence_score": 1.0,
                "final_root_cause": f"No bug detected — Hook H{target_hook:02d} under {strategy.upper()} Recovery correctly satisfies all 4 invariants.",
                "failure_families": ["NONE_ALL_SAFE"],
            })

        # ─── 3. EXPERIMENT LOOP ───────────────────────────────────────────────
        state = {
            "id": investigation_id,
            "seed": seed,
            "strategy": strategy,
            "status": "INVESTIGATING",
            "initial_hook": target_hook,
            "current_hook": target_hook,
            "observations": [obs_map],
            "fingerprints": [fp],
            "hypotheses": hypotheses,
            "experiments": [],
            "activity_log": activity_log,
            "confidence": "LOW",
            "confidence_score": 0.20,
            "final_root_cause": "INVESTIGATION_IN_PROGRESS",
        }

        experiment_count = 0
        confidence = "LOW"
        root_cause_stmt = ""

        while experiment_count < self.max_experiments:
            experiment_count += 1

            # Select Next Experiment via Information Gain Scoring
            scores = calculate_information_scores(state["hypotheses"], state["current_hook"], state["experiments"])
            selected_exp = select_next_experiment(state["hypotheses"], state["current_hook"], state["experiments"])

            activity_log.append({
                "stage": "DECISION",
                "message": f"Selected experiment '{selected_exp['experiment_type']}' (Information Gain Score: {selected_exp['information_score']:.2f})",
                "details": selected_exp["reason"],
            })

            # Execute Experiment via REAL Engine
            exp_result = execute_experiment(selected_exp, seed=seed, strategy=strategy)
            state["experiments"].append(exp_result)

            activity_log.append({
                "stage": "EXPERIMENT",
                "message": f"Executed {selected_exp['experiment_type']} on H{selected_exp['target_hook']:02d}",
                "details": exp_result.get("evidence_summary", "Experiment executed."),
            })

            # Evaluate Evidence & Eliminate Hypotheses
            updated_hyps, families, root_cause_stmt, conf_score = evaluate_evidence_and_update_hypotheses(
                state["hypotheses"], exp_result
            )

            state["hypotheses"] = updated_hyps
            state["failure_families"] = families
            state["final_root_cause"] = root_cause_stmt
            state["confidence_score"] = conf_score

            # Check hypothesis status updates for log
            rejected_now = [h["name"] for h in updated_hyps if h["status"] == "REJECTED"]
            confirmed_now = [h["name"] for h in updated_hyps if h["status"] in ("CONFIRMED", "STRENGTHENED")]

            if rejected_now:
                activity_log.append({
                    "stage": "ELIMINATION",
                    "message": f"Eliminated competing hypothesis: {', '.join(rejected_now)}",
                    "details": "Empirical evidence contradicted hypothesis requirements.",
                })

            if confirmed_now:
                activity_log.append({
                    "stage": "CONCLUSION",
                    "message": f"Strengthened primary hypothesis: '{confirmed_now[0]}'",
                    "details": f"Root cause established.",
                })

            # Check stop condition: high confidence or budget limit
            if conf_score >= 0.90:
                confidence = "HIGH"
                state["status"] = "ROOT_CAUSE_CONFIRMED"
                state["confidence"] = confidence
                break
            elif conf_score >= 0.70:
                confidence = "MEDIUM"
                state["status"] = "ROOT_CAUSE_PLAUSIBLE"
                state["confidence"] = confidence

        if state["status"] == "INVESTIGATING":
            state["status"] = "INVESTIGATION_COMPLETE"
            state["confidence"] = "MEDIUM" if conf_score >= 0.70 else "LOW"

        activity_log.append({
            "stage": "FINAL",
            "message": f"Investigation complete. Verdict: {state['status']}",
            "details": f"Total experiments: {experiment_count} | Root cause: {state['final_root_cause']}",
        })

        return generate_investigation_report(state)
