CREATE SCHEMA IF NOT EXISTS raw;

CREATE OR REPLACE TABLE raw.loans_accepted AS
SELECT * 
FROM read_csv_auto( 
  'data/raw/accepted_2007_to_2018Q4.csv.gz',
  sample_size = -1,
  ignore_errors = true
 );

 CREATE OR REPLACE TABLE raw.loans_rejected AS
 SELECT *
 FROM read_csv_auto( 
  'data/raw/rejected_2007_to_2018Q4.csv.gz',
  sample_size = -1,
  ignore_errors= true
  );
