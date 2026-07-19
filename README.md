# Credit risk on Lending Club

A default model on Lending Club's 36-month loans, built around one question: using only what was
known about a borrower at origination, can we match — or beat — Lending Club's own risk pricing?

`int_rate` is that pricing. The rate they set is the output of their internal risk model, so a
model that reads it is copying their grade, not measuring risk. The interesting comparison is not
"how high can the AUC go" but "can borrower data stand on its own against the price, and where
does it add something the price missed?"

## What's here

The target is lifetime default (charged off vs fully paid) on 36-month loans. One decision shapes
everything: a loan is labelled only once it has been observed for its full 36 months. Without
that maturity filter, recent vintages look artificially safe — their defaults simply haven't
happened yet — and a random split hides it. This is the subtle half of the leakage story, and it
is handled in SQL where the modelling table is built.

Two rules keep the features honest:

- **SQL enforces time.** Post-origination columns (payments, recoveries, last FICO) never enter
  the modelling table. This is Lending Club's documented leakage trap.
- **Python enforces framing.** `int_rate` and `grade` are honest origination-time data, but they
  are Lending Club's verdict, so the underwriter model excludes them and keeps only what
  describes the borrower.

The split is out-of-time: train on the oldest vintages, tune on the middle, test on the most
recent, so evaluation mimics scoring future loans instead of a random shuffle. Two models,
logistic regression and LightGBM, are each run on three feature sets — Lending Club's verdict,
the borrower data, and the union.

## Results (validation)

```
               roc_auc   pr_auc   brier
logistic
  lc_verdict     0.679    0.252   0.122
  underwriter    0.663    0.244   0.122
  union          0.691    0.266   0.121
lgbm
  lc_verdict     0.675    0.247   0.122
  underwriter    0.674    0.253   0.122
  union          0.696    0.275   0.120
```

- Borrower data alone (underwriter) nearly matches the price, and the union beats it — so the
  features carry risk the price left out.
- It cannot rebuild the price from scratch: an LGBMRegressor recovers only ~40% of `int_rate`'s
  variance, so most of what set the rate is information the public data never had.
- The tree pays off only where features interact. It wins on the borrower and union sets and
  loses on the single, monotone price column, where the smooth logistic fit is better.
- The winning model is well calibrated out of the box, with a mild under-prediction in the
  high-risk tail — a residue of out-of-time drift, as lending standards loosened and bad rates
  rose from 2013 to 2016.

## Layout

```
sql/        ingestion, the modelling table, and the EDA behind every feature choice
src/        data loading, out-of-time split, model pipelines, evaluation
scripts/    train_baseline.py: the reproducible run, two models by three feature sets
notebooks/  the underwriter-vs-Lending-Club story, end to end
reports/    saved figures
```

## Running

```
pip install -e .                 # into a Python 3.11 environment
# build data/credit_risk.duckdb from the raw CSVs by running the files in sql/ in order
python scripts/train_baseline.py
```

## Roadmap

- **Validation rigor.** Quantify the out-of-time drift instead of just noting it: compare the
  temporal split against a random one to see how much a shuffle inflates AUC, and measure
  per-feature shift with PSI and adversarial validation. → a `drift` module in `src`, a random
  split alongside the temporal one, and a notebook.
- **Selection bias.** The model only ever sees accepted loans. The rejected file is ingested but
  unused; bring it into a comparable table and characterise how accepted and rejected applicants
  differ on the shared fields (amount, DTI, risk score, employment). → SQL staging and a notebook.
- **Hyperparameter tuning.** A principled Optuna pass on the LightGBM union model. Kept last and
  kept light: the reconstruction ceiling means there is little AUC left to win, so this is polish.
- **Final test.** The test set has stayed untouched throughout. Score the tuned model on it once,
  for the honest headline number, and stop.
