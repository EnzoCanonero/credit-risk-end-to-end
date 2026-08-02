# Scores a CSV of loans and writes the batch decisions.

import argparse
from pathlib import Path

import pandas as pd

from credit_risk.serving import score
from credit_risk.evaluate import breakeven_probability


# Reads the input file, scores each loan, and saves the results.
def main():
    parser = argparse.ArgumentParser(description="Score a CSV of loans, writing probabilities and decisions.")
    parser.add_argument("input", type=Path, help="CSV of loans with an id and the feature columns")
    parser.add_argument("output", type=Path, help="where to write id, proba and approve")
    args = parser.parse_args()

    df = pd.read_csv(args.input)

    df["proba"] = score(df)
    df["approve"] = df["proba"] < breakeven_probability(df["int_rate"])

    df[["id", "proba", "approve"]].to_csv(args.output, index=False)
    print(f"scored {len(df)} loans -> {args.output}")


if __name__ == "__main__":
    main()
