# Baseline model: preprocessing + logistic regression pipeline.

from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.linear_model import LogisticRegression


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

NUMERIC = UNDERWRITER_NUMERIC
CATEGORICAL = UNDERWRITER_CATEGORICAL

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
