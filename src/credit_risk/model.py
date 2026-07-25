# Baseline model: preprocessing + logistic regression pipeline.

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

# The builders default to the union set, the model the project carries forward past notebook 21.
# The comparison code in train_baseline and notebook 21 still passes each set explicitly, so this
# only decides what a bare build_*() means. A caller that feeds underwriter-only data now gets a
# loud error on the missing int_rate/grade columns, instead of the union columns being dropped.
NUMERIC = UNDERWRITER_NUMERIC + LC_VERDICT_NUMERIC
CATEGORICAL = UNDERWRITER_CATEGORICAL + LC_VERDICT_CATEGORICAL

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


def build_logistic(
    numeric: list[str] = NUMERIC,
    categorical: list[str] = CATEGORICAL,
) -> Pipeline:

    pipe = Pipeline(
        [('prep', build_preprocessor(numeric, categorical)),
        ('clf', LogisticRegression(max_iter=1000))]
    )

    return pipe


def build_tree_preprocessor(
    numeric: list[str] = NUMERIC,
    categorical: list[str] = CATEGORICAL,
) -> ColumnTransformer:
    # Trees want the opposite of the logistic preprocessing: numeric passthrough (LightGBM
    # sends NaN down a learned branch, and splits are rank-based, so no impute or scale) and
    # ordinal-encoded categoricals (integer codes, not one-hot, so 50 states stay one column).
    ct = ColumnTransformer([
        ('num', 'passthrough', numeric),
        ('cat',
        OrdinalEncoder(handle_unknown='use_encoded_value', unknown_value=-1),
        categorical)
    ])

    # Emit a named DataFrame instead of a bare array: silences the fit/predict feature-name
    # mismatch, and keeps real names on LightGBM's feature_importances_ (not Column_0...).
    return ct.set_output(transform="pandas")


def build_lgbm(
    numeric: list[str] = NUMERIC,
    categorical: list[str] = CATEGORICAL,
    params: dict | None = None,
) -> Pipeline:
    # No class_weight: imbalance is handled at the threshold, same choice as the logistic.
    # The hand-set defaults are the baseline. A params dict overrides them, so the same builder
    # serves both the baseline and the tuned model from scripts/tune_lgbm.py. verbose stays in the
    # defaults, so a passed dict does not have to carry it.
    settings = {
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