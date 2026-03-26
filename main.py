import sys
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import argparse, os, json, warnings
warnings.filterwarnings("ignore")
import pandas as pd
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import Literal
import anthropic

load_dotenv()
os.environ.setdefault("ANTHROPIC_API_KEY", os.getenv("ANTHROPIC_API_KEY", ""))


class SARHypothesis(BaseModel):
    hypothesis: str
    rationale: str
    confidence: Literal["high", "medium", "low"]
    supporting_compounds: list[str]


class HypothesisSet(BaseModel):
    scaffold_family: str
    n_compounds: int
    hypotheses: list[SARHypothesis]


def pic50_to_class(pic50: float) -> str:
    if pic50 < 5.0:   return "inactive"
    elif pic50 < 6.0: return "weak"
    elif pic50 < 7.0: return "moderate"
    elif pic50 < 8.0: return "potent"
    else:             return "highly_potent"


def build_sar_table(df: pd.DataFrame) -> str:
    lines = ["Compound | SMILES | pIC50 | Activity Class"]
    lines.append("-" * 70)
    for _, row in df.iterrows():
        cls = pic50_to_class(row["pic50"])
        lines.append(f"{row['compound_name']:20s} | {row['smiles'][:30]:30s} | {row['pic50']:.2f} | {cls}")
    return "\n".join(lines)


def build_prompt(scaffold: str, sar_table: str) -> str:
    return (
        f"You are a medicinal chemist analyzing SAR data for a {scaffold} scaffold series.\n\n"
        f"Here is the activity data:\n\n{sar_table}\n\n"
        f"Based on this data, generate exactly 3 SAR hypotheses. For each hypothesis:\n"
        f"1. State the hypothesis clearly (what structural feature correlates with activity)\n"
        f"2. Provide the chemical rationale\n"
        f"3. Assign confidence: high/medium/low\n"
        f"4. List the compound names that support it\n\n"
        f"Respond in JSON format:\n"
        f'{{"scaffold_family": "{scaffold}", "n_compounds": <N>, "hypotheses": ['
        f'{{"hypothesis": "...", "rationale": "...", "confidence": "high|medium|low", '
        f'"supporting_compounds": ["...", "..."]}}, ...]}}'
    )


def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--input", required=True)
    parser.add_argument("--scaffold", default="benz", help="Scaffold family to analyze")
    parser.add_argument("--model", default="claude-sonnet-4-6")
    parser.add_argument("--thinking-budget", type=int, default=5000)
    parser.add_argument("--output-dir", default="output")
    args = parser.parse_args()
    os.makedirs(args.output_dir, exist_ok=True)

    df = pd.read_csv(args.input)
    scaffold_df = df[df["compound_name"].str.startswith(args.scaffold + "_")].copy()
    if scaffold_df.empty:
        print(f"No compounds found for scaffold '{args.scaffold}'")
        return

    print(f"\nPhase 56 — Adaptive Thinking: SAR Hypothesis Generation")
    print(f"Scaffold: {args.scaffold} ({len(scaffold_df)} compounds)")
    print(f"Model:    {args.model}")
    print(f"Thinking budget: {args.thinking_budget} tokens\n")

    client = anthropic.Anthropic()
    sar_table = build_sar_table(scaffold_df)
    prompt = build_prompt(args.scaffold, sar_table)

    response = client.messages.create(
        model=args.model,
        max_tokens=8000,
        thinking={"type": "enabled", "budget_tokens": args.thinking_budget},
        messages=[{"role": "user", "content": prompt}],
    )

    # Extract thinking and text blocks
    thinking_text = ""
    response_text = ""
    thinking_tokens = 0
    for block in response.content:
        if block.type == "thinking":
            thinking_text = block.thinking
        elif block.type == "text":
            response_text = block.text

    input_tokens = response.usage.input_tokens
    output_tokens = response.usage.output_tokens
    # Estimate thinking tokens from total - estimate
    total_tokens = input_tokens + output_tokens

    print(f"Thinking excerpt (first 500 chars):\n{thinking_text[:500]}...\n")
    print(f"Response:\n{response_text[:1000]}\n")

    # Parse JSON from response
    import re
    json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
    hypotheses_data = None
    parse_error = None
    if json_match:
        try:
            raw = json.loads(json_match.group())
            hypotheses_data = HypothesisSet(**raw)
        except Exception as e:
            parse_error = str(e)
            print(f"Parse error: {e}")
    else:
        parse_error = "No JSON found in response"
        print("No JSON found in response")

    # Save outputs
    output = {
        "scaffold_family": args.scaffold,
        "model": args.model,
        "thinking_budget": args.thinking_budget,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "thinking_excerpt": thinking_text[:2000],
        "hypotheses": hypotheses_data.model_dump() if hypotheses_data else None,
        "parse_error": parse_error,
    }
    with open(os.path.join(args.output_dir, "hypotheses.json"), "w") as f:
        json.dump(output, f, indent=2)

    # Cost estimate (Sonnet: $3/MTok in, $15/MTok out)
    cost = (input_tokens / 1e6 * 3.0) + (output_tokens / 1e6 * 15.0)

    report = (
        f"Phase 56 — Adaptive Thinking: SAR Hypothesis Generation\n"
        f"{'='*55}\n"
        f"Scaffold:       {args.scaffold} ({len(scaffold_df)} compounds)\n"
        f"Model:          {args.model}\n"
        f"Thinking budget:{args.thinking_budget} tokens\n"
        f"Input tokens:   {input_tokens}\n"
        f"Output tokens:  {output_tokens}\n"
        f"Est. cost:      ${cost:.4f}\n"
        f"Hypotheses:     {len(hypotheses_data.hypotheses) if hypotheses_data else 0}\n"
    )
    if hypotheses_data:
        report += "\nHypotheses:\n"
        for i, h in enumerate(hypotheses_data.hypotheses, 1):
            report += f"\n{i}. [{h.confidence.upper()}] {h.hypothesis}\n"
            report += f"   Rationale: {h.rationale}\n"
            report += f"   Supporting: {', '.join(h.supporting_compounds)}\n"

    print(f"\n{report}")
    with open(os.path.join(args.output_dir, "thinking_report.txt"), "w", encoding="utf-8") as f:
        f.write(report)
    print(f"Saved: {args.output_dir}/hypotheses.json")
    print(f"Saved: {args.output_dir}/thinking_report.txt")
    print("\nDone.")


if __name__ == "__main__":
    main()
