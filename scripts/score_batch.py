# Step 3 — batch scoring: score a table of loans offline and write the results.
#
# The simplest kind of serving: no server, no request. Read many rows, score them, write a file.
# This is how a lender re-scores a whole portfolio on a schedule, and the easiest way to watch the
# artifact work end to end.

import argparse
from pathlib import Path

import pandas as pd

from credit_risk.serving import score
from credit_risk.evaluate import breakeven_probability


def main():
    # An input CSV of loans and an output path for the scored result.
    parser = argparse.ArgumentParser(description="Score a CSV of loans, writing probabilities and decisions.")
    parser.add_argument("input", type=Path, help="CSV of loans with an id and the feature columns")
    parser.add_argument("output", type=Path, help="where to write id, proba and approve")
    args = parser.parse_args()

    df = pd.read_csv(args.input)

    df["proba"] = score(df)
    # Approve when the predicted default is below the loan's own break-even, the rule the final
    # test validated.
    df["approve"] = df["proba"] < breakeven_probability(df["int_rate"])

    df[["id", "proba", "approve"]].to_csv(args.output, index=False)
    print(f"scored {len(df)} loans -> {args.output}")


if __name__ == "__main__":
    main()
