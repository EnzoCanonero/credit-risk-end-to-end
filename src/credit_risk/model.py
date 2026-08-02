# Builds the project model pipelines.

from collections.abc import Mapping
from typing import Any

from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler, OneHotEncoder, OrdinalEncoder
from sklearn.linear_model import LogisticRegression
from lightgbm import LGBMClassifier 


LC_VERDICT_NUMERIC = ['int_rate']
LC_VERDICT_CATEGORICAL = ['grade']

UNDERWRITER_NUMERIC = [
    'loan_amnt',
    'annual_inc',
    'dti',
    'fico_range_low',
    'inq_last_6mths',
    'open_acc',
    'pub_rec',
    'revol_bal',
    'revol_util',
    'total_acc',
    'delinq_2yrs',
    'pub_rec_bankruptcies',
    'credit_history_months',
    'loan_to_income',
    'active_acct_ratio',
    'collections_12_mths_ex_med',
    'tax_liens',
    'delinq_amnt',
    'acc_now_delinq',
    'chargeoff_within_12_mths',
    'mths_since_last_delinq',
]
UNDERWRITER_CATEGORICAL = [
    'home_ownership',
    'purpose',
    'addr_state',
    'verification_status',
    'application_type',
    'emp_length',
]

NUMERIC = UNDERWRITER_NUMERIC + LC_VERDICT_NUMERIC
CATEGORICAL = UNDERWRITER_CATEGORICAL + LC_VERDICT_CATEGORICAL

# Builds preprocessing for the logistic model.
def build_preprocessor(
    numeric: list[str] = NUMERIC,
    categorical: list[str] = CATEGORICAL,
) -> ColumnTransformer:

    ct = ColumnTransformer([
        ('num', Pipeline([
            ('impute', SimpleImputer(strategy='median', add_indicator=True)),
            ('scale', StandardScaler()),
        ]), numeric),
        ('cat', OneHotEncoder(handle_unknown="ignore"), categorical),
    ])

    return ct


# Builds the logistic regression pipeline.
def build_logistic(
    numeric: list[str] = NUMERIC,
    categorical: list[str] = CATEGORICAL,
) -> Pipeline:

    pipe = Pipeline(
        [('prep', build_preprocessor(numeric, categorical)),
        ('clf', LogisticRegression(max_iter=1000))]
    )

    return pipe


# Builds preprocessing for the LightGBM model.
def build_tree_preprocessor(
    numeric: list[str] = NUMERIC,
    categorical: list[str] = CATEGORICAL,
) -> ColumnTransformer:
    ct = ColumnTransformer([
        ('num', 'passthrough', numeric),
        ('cat',
        OrdinalEncoder(handle_unknown='use_encoded_value', unknown_value=-1),
        categorical)
    ])

    return ct.set_output(transform="pandas")


# Builds the LightGBM pipeline.
def build_lgbm(
    numeric: list[str] = NUMERIC,
    categorical: list[str] = CATEGORICAL,
    params: Mapping[str, object] | None = None,
) -> Pipeline:
    settings: dict[str, Any] = {
        'n_estimators': 300,
        'learning_rate': 0.05,
        'num_leaves': 31,
        'verbose': -1,
    }
    if params:
        settings.update(params)

    pipe = Pipeline([
        ('prep', build_tree_preprocessor(numeric, categorical)),
        ('clf', LGBMClassifier(**settings))
    ])

    return pipe
