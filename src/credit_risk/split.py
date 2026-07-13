import pandas as pd

# Out-of-time split: train on the oldest vintages, tune on the middle, test on the most recent.
# Follows split from sql/05_split_design.sql

Splits = tuple[pd.DataFrame,pd.DataFrame,pd.DataFrame]

def out_of_time_split(
    df: pd.DataFrame, 
    val_start: str = "2015-04-01", 
    test_start: str = "2015-10-01"
) -> Splits:

    val_start  = pd.Timestamp(val_start)
    test_start = pd.Timestamp(test_start)

    train = df[ df['issue_month'] < val_start ].copy()                                    
    val   = df[ (df['issue_month'] >= val_start) & (df['issue_month'] < test_start) ].copy()  
    test  = df[ df['issue_month'] >= test_start ].copy()                                 

    return train, val, test