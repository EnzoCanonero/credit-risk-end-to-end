# Baseline model: preprocessing + logistic regression pipeline.

from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.linear_model import LogisticRegression


NUMERIC = ['loan_amnt', 'int_rate', 'annual_inc']
CATEGORICAL = ['grade']


def build_preprocessor() -> ColumnTransformer:
    
    ct = ColumnTransformer(
        [('numic', StandardScaler(), NUMERIC),  
        ('categorical', OneHotEncoder(handle_unknown="ignore"), CATEGORICAL)]
    )

    return ct

def build_logistic() -> Pipeline:
    
    pipe = Pipeline(
        [('prep', build_preprocessor()),
        ('clf', LogisticRegression(max_iter=1000))]
    )

    return pipe


