# Baseline model: preprocessing + logistic regression pipeline.

from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.linear_model import LogisticRegression


NUMERIC = ['loan_amnt', 'int_rate', 'annual_inc']
CATEGORICAL = ['grade']

def build_preprocessor(
    numeric: list[str] = NUMERIC,
    categorical: list[str] = CATEGORICAL,
) -> ColumnTransformer:

    ct = ColumnTransformer(
        [('num', StandardScaler(), numeric),
        ('cat', OneHotEncoder(handle_unknown="ignore"), categorical)]
    )

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


