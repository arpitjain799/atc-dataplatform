# Transformations documentation

Transformations in atc-dataplatform:

- [Transformations documentation](#transformations-documentation)
  - [Concatenate data frames](#concatenate-data-frames)
    - [Example](#example)
  - [Fuzzy Select Transformer](#fuzzy-select-transformer)
    - [Example](#example-1)
  - [Merge df into target](#merge-df-into-target)
    - [Example](#example-2)
  - [DropOldestDuplicates](#dropoldestduplicates)
  - [TimeZoneTransformer](#timezonetransformer)
  - [SelectAndCastColumnsTransformer](#selectandcastcolumnstransformer)

## Concatenate data frames

*UPDATE: Pyspark has an equivalent implementation  `.unionByName(df, allowMissingColumns=False)`, see the [documentation](https://spark.apache.org/docs/latest/api/python/reference/api/pyspark.sql.DataFrame.unionByName.html) for more information.*

The transformation unions dataframes by appending the dataframes on eachother and keep all columns.


```python
from pyspark.sql import DataFrame
from typing import List

def concat_dfs(dfs: List[DataFrame]) -> DataFrame:   
    ...
```
Usage example: 
``` python
concat_dfs([df1,df2,df3])
```

### Example

This section elaborates on how the `concat_dfs` function works with a small example.

Create three test datasets:
``` python
df1 =   Spark.get().createDataFrame(
        Spark.get().sparkContext.parallelize([
            ('1', 'Fender', 'Telecaster', '1950'),
            ('2', 'Gibson', 'Les Paul', '1959'),
            ('3', 'Ibanez', 'RG', '1987')
        ]),
        StructType([
            StructField('id', StringType()),
            StructField('brand', StringType()),
            StructField('model', StringType()),
            StructField('year', StringType()),
        ]))

df2 = Spark.get().createDataFrame(
        Spark.get().sparkContext.parallelize([
            ('1', 'Fender', 'Stratocaster', 'Small'),
            ('2', 'Gibson', 'Les Paul Junior', 'Medium'),
            ('3', 'Ibanez', 'JPM', 'Large')
        ]),
        StructType([
            StructField('id', StringType()),
            StructField('brand', StringType()),
            StructField('model', StringType()),
            StructField('size', StringType()),
        ]))
```
Concatenate (union) the two dataframes:
``` python
 # ATC's "concat_dfs"
 result = concat_dfs([df1,df2])
 
 # pyspark's unionByName
 result = df1.unionByName(df2, allowMissingColumns=True)
```

Print the dataframe:

``` python
 result.show()
```

The output is then:
``` python
+------+---+---------------+------+----+
| brand| id|          model|  size|year|
+------+---+---------------+------+----+
|Fender|  1|     Telecaster|  null|1950|
|Gibson|  2|       Les Paul|  null|1959|
|Ibanez|  3|             RG|  null|1987|
|Fender|  1|   Stratocaster| Small|null|
|Gibson|  2|Les Paul Junior|Medium|null|
|Ibanez|  3|            JPM| Large|null|
+------+---+---------------+------+----+
```
See that the columns "brand", "id", "model", "size" (from df2) and "year" (from df1) are added to the dataframe consisting of the union of df1 and df2.

## Fuzzy Select Transformer

The `FuzzySelectTransformer` is an ETL transformer that can process a single dataframe. Its purpose is to help create
short concise select code that is somewhat insensitive to source columns that are misspelled 
or use different capitalization.

To use, construct the `FuzzySelectTransformer` with the following arguments:
- `columns` The list of column names in the final dataframe in order.
- `match_cutoff` A cutoff quality in the range [0,1] below which matches will not be accepted. 
  See [difflib arguments](https://docs.python.org/3/library/difflib.html#difflib.get_close_matches) for details.

Under the hood, [difflib](https://docs.python.org/3/library/difflib.html) is used to find a suitable unique mapping
from source to target columns. All column names are converted to lower case before matching.

The association of target to source columns is required to be unique. If the algorithm identifies
multiple matching source columns to a target name, an exception will be raised.

### Example

Given a dataframe `df`, this code renames all columns:
```
>>> df.show()
+----+-----+------+
|inex|count|lables|
+----+-----+------+
|   1|    2|   foo|
|   3|    4|   bar|
+----+-----+------+
>>> from atc.transformers.fuzzy_select import FuzzySelectTransformer
>>> ft = FuzzySelectTransformer(["Index", "Count", "Label"])
>>> ft.process(df).show()
+-----+-----+-----+
|Index|Count|Label|
+-----+-----+-----+
|    1|    2|  foo|
|    3|    4|  bar|
+-----+-----+-----+
```

## Merge df into target
The transformation merges a databricks dataframe into a target database table. 

``` python
def merge_df_into_target(df: DataFrame,
    table_name: str,
    database_name: str,
    join_cols: List[str]) -> None:    
    ...
```
Usage example: 
``` python
merge_df_into_target(df_new, "testTarget", "test", ["Id"])
```

### Example

The following queries crate a test table with two rows containing guitar data:
``` python
CREATE DATABASE IF NOT EXISTS test
COMMENT "A test database"
LOCATION "/tmp/test/";

CREATE TABLE IF NOT EXISTS test.testTarget(
  Id STRING,
  Brand STRING,
  Model STRING
)
USING DELTA
COMMENT "Contains merge test target rows"
LOCATION "/tmp/test/testTarget";

insert into test.testTarget values ("2","Gibson","Les Paul");

select * from testTarget.test
+----+-----+----+-----------+
|Id  |    Brand |      Model|
+----+-----+----+-----------+
|   2|    Gibson|   Les Paul|
+----+----------+-----------+

```
The following dataframe has one row that will be merged with Id=2, and the other rows are going to be inserted:
``` python 
from pyspark.sql.types import StructType, StructField, IntegerType, StringType
df_new=spark.createDataFrame(
        spark.sparkContext.parallelize([
            ("1", "Fender", "Jaguar"),
            ("2", "Gibson","Starfire"),
            ("3", "Ibanez", "RG")
        ]),
        StructType([
            StructField("Id", StringType(), False),
            StructField("Brand", StringType(), True),
          StructField("Model", StringType(), True),
        ]))

```
Use the transformation to merge data into the test delta table:
``` python 
merge_df_into_target(df_new, "testTarget", "test", ["Id"])

%sql

select * from test.testTarget order by Id

+----+-----+----+-----------+
|Id  |    Brand |      Model|
+----+-----+----+-----------+
|   1|    Fender|     Jaguar|
|   2|    Gibson|   Starfire|
|   3|    Ibanez|         RG|
+----+----------+-----------+

```

As one can see, the row with id=2 is now merged such that the model went from "Les Paul" to "Starfire". 
The two other rows where inserted. 

## DropOldestDuplicates

This transformation helps dropping duplicates based on time. If there is multiple duplicates, 
only the newest row remain. In the example below, a dataframe has several duplicates - since a unique record is 
defined by a combination of a guitar-id, model and brand. As times go by the amount
of guitars available in a store changes. Lets assume that we only want the newest record
and dropping the oldest duplicates:

``` python 
from atc.utils.DropOldestDuplicates import DropOldestDuplicates
data =

| id| model|     brand|amount|         timecolumn|
+---+------+----------+------+-------------------+
|  1|Fender|Telecaster|     5|2021-07-01 10:00:00|
|  1|Fender|Telecaster|     4|2021-07-01 11:00:00|
|  2|Gibson|  Les Paul|    27|2021-07-01 11:00:00|
|  3|Ibanez|        RG|    22|2021-08-01 11:00:00|
|  3|Ibanez|        RG|    26|2021-09-01 11:00:00|
|  3|Ibanez|        RG|    18|2021-10-01 11:00:00|
+---+------+----------+------+-------------------+

df = DropOldestDuplicatesTransformer( 
            cols=["id", "model", "brand"], 
            orderByColumn="timecolumn"
            ).process(data)
df.show()

| id| model|     brand|amount|         timecolumn|
+---+------+----------+------+-------------------+
|  1|Fender|Telecaster|     4|2021-07-01 11:00:00|
|  2|Gibson|  Les Paul|    27|2021-07-01 11:00:00|
|  3|Ibanez|        RG|    18|2021-10-01 11:00:00|
+---+------+----------+------+-------------------+
```

Notice, the oldest duplicates are dropped. 

## TimeZoneTransformer

This transformation uses latitude and longitude values to determine the timezone
of a specific location. The example below shows how to apply the transformer
of an input DataFrame to get a column with timezones. Notice, when either the
latitude or longitude value is *None*, the returned timezone will also be *None*.


``` python 
from atc.transformers import TimeZoneTransformer
data =

|   latitude| longitude|
+-----------+----------+
| 51.519487 | -0.083069|
| 55.6761   |   12.5683|
| None      |      None|
| None      | -0.083069|
| 51.519487 |      None|
+-----------+----------+

df = TimeZoneTransformer( 
            latitude_col="latitude",
            longitude_col="longitude",
            column_output_name="timezone"
        ).process(data)
df.show()

|   latitude| longitude|            timezone|
+-----------+----------+--------------------+
| 51.519487 | -0.083069|     "Europe/London"|
| 55.6761   |   12.5683| "Europe/Copenhagen"|
| None      |      None|                None|
| None      | -0.083069|                None|
| 51.519487 |      None|                None|
+-----------+----------+--------------------+
```

## SelectAndCastColumnsTransformer

This transformation is selecting and casting columns in dataframe based
on pyspark schema.
If case-insensitive matching is desired, caseInsensitiveMatching can be set to True

``` python 
from atc.transformers import SelectAndCastColumnsTransformer
data =

|         id|    number|     value|
+-----------+----------+----------+
|         1 |       42 |        1 |
|         2 |      355 |        0 |
+-----------+----------+----------+

desired_schema = T.StructType(
    [
        T.StructField("id", T.StringType(), True),
        T.StructField("value", T.BooleanType(), True),
    ]
)

df = SelectAndCastColumnsTransformer( 
      schema=desired_schema,
      caseInsensitiveMatching=False
  ).process(data)
df.show()

|         id|     value|
+-----------+----------+
|       "1" |     True |
|       "2" |    False |
+-----------+----------+
```