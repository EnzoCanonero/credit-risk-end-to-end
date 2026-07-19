# Out-of-time split: train on the oldest vintages, tune on the middle, test on the most recent.
# Follows split from sql/05_split_design.sql

import pandas as pd

Splits = tuple[pd.DataFrame,pd.DataFrame,pd.DataFrame]

def out_of_time_split(
    df: pd.DataFrame, 
    val_frac: float=0.20, 
    test_frac: float=0.25,
    date_col: str='issue_month'
) -> Splits:

    train_frac = 1 - val_frac - test_frac

    val_start  = df[date_col].quantile(train_frac, interpolation='lower')
    test_start = df[date_col].quantile(train_frac + val_frac, interpolation='lower')

    train = df[ df[date_col] < val_start ].copy()                                    
    val   = df[ (df[date_col] >= val_start) & (df[date_col] < test_start) ].copy()  
    test  = df[ df[date_col] >= test_start ].copy()                                 

    return train, val, test