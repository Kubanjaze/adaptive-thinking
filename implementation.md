# Phase 56 — Adaptive Thinking: SAR Hypothesis Generation

**Version:** 1.1 | **Tier:** Standard | **Date:** 2026-03-26

## Goal
Demonstrate Claude's extended/adaptive thinking to generate SAR hypotheses from compound activity data.
Ask Claude to reason over a scaffold family's SAR trend and produce ranked hypotheses with confidence levels.

CLI: `python main.py --input data/compounds.csv --scaffold benz --model claude-sonnet-4-6`

Outputs: hypotheses.json, thinking_report.txt

## Logic
- Load compounds CSV, filter to specified scaffold family
- Build a SAR summary table (compound, SMILES, pIC50, activity_class)
- Send to Claude with extended thinking enabled (`thinking={"type": "enabled", "budget_tokens": 5000}`)
- Ask for: top-3 SAR hypotheses, each with rationale and confidence (high/medium/low)
- Parse output into HypothesisSet Pydantic model
- Report: thinking tokens used, hypothesis count, cost estimate

## Key Concepts
- Extended thinking: `thinking={"type": "enabled", "budget_tokens": N}` in `client.messages.create()`
- Thinking blocks appear in `response.content` as `block.type == "thinking"`, text: `block.thinking`
- Text blocks: `block.type == "text"`, text: `block.text`
- Must use claude-sonnet-4-6 or opus (Haiku does not support extended thinking)
- `max_tokens` must be > thinking_budget (set to 8000)

## Results
| Metric | Value |
|--------|-------|
| Scaffold analyzed | benz (12 compounds) |
| Hypotheses generated | 3 |
| Input tokens | 678 |
| Output tokens | 2718 |
| Est. cost | $0.0428 |

## Hypotheses Generated
1. **[HIGH]** EWGs at para position strongly enhance potency (pIC50 cliff: EWG 7.25–8.10 vs EDG 6.05–6.60). Acrylamide as Michael acceptor warhead; EWGs increase electrophilicity.
2. **[MEDIUM]** Within EWGs, lipophilicity+EW strength determines ranking: CF3>CN>Cl>Br>NO2>F. NO2 underperforms despite strongest sigma — polarity and metabolic liability penalty.
3. **[MEDIUM]** Disubstitution additive: dichloro (7.85) > monochloro (7.65); difluoro (7.40) > monofluoro (7.25). Cumulative inductive + van der Waals/halogen-bond contacts.
