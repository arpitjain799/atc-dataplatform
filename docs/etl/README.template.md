# ETL Orchestrator

## Introduction

This module contains components for implementing elegant ETL operations using the **[OETL Design Pattern](#OETL)**.

## OETL

Short for **Orchestrated Extract-Transform-Load** is a pattern that takes the ideas behind variations of the 
Model-View-Whatever design pattern

![Orchestrated ETL](etl-orchestrator.png)

The **Orchestrator** is responsible for conducting the interactions between the 
**Extractor** -> **Transformer** -> **Loader**.

The **Ochestrator** reads data from the **Extractor** then uses the result as a parameter to calling the **Transformer**
and saves the transformed result into the **Loader**. The **Transformer** can be optional as there are scenarios where 
data transformation is not needed (i.e. raw data ingestion to a landing zone)

Each layer may have a single or multiple implementations, and this is handled automatically in the 
**Orchestrator**

## Orchestration Fluent Interface

This library provides common simple implementations and base classes for implementing the OETL design pattern. 
To simplify object construction, we provide the **Orchestrator** fluent interface from `atc.etl`

```python
from atc.etl import Extractor, Transformer, Loader, Orchestrator

(Orchestrator()
    .extract_from(Extractor())
    .transform_with(Transformer())
    .load_into(Loader())
    .execute())
```

## Usage examples:

Here are some example usages and implementations of the ETL class provided

### Example-1

Here's an example of reading data from a single location, transforming it once and saving to a single destination.
This is the most simple elt case, and will be used as base for the below more complex examples.

```
{basic_example}
```

The code above produces the following output:

```
Original DataFrame schema
root
 |-- id: string (nullable = true)
 |-- brand: string (nullable = true)
 |-- model: string (nullable = true)
 |-- year: string (nullable = true)

New DataFrame schema
root
 |-- id: integer (nullable = true)
 |-- brand: string (nullable = true)
 |-- model: string (nullable = true)
 |-- year: integer (nullable = true)

+---+------+----------+----+
| id| brand|     model|year|
+---+------+----------+----+
|  1|Fender|Telecaster|1950|
|  2|Gibson|  Les Paul|1959|
|  3|Ibanez|        RG|1987|
+---+------+----------+----+
```

### Example-2

Here's an example of having multiple `Transformer` implementations that is reused to change the data type of a given column,
where the column name is parameterized.

```
{multiple_transform_example}
```

### Example-3

Here's an example of having multiple `Extractor` implementations and applying transformations using 
the `process_many` method.

The `read()` function in `Extractor` will return a dictionary that uses the type name of the `Extractor` 
as the key, and a `DataFrame` as its value, the used kan can be overridden in the constructor.

`Transformer` provides the function `process_many(dataset: {{}})` and returns a single `DataFrame`.

```
{multiple_input_example}
```

The code above produces the following output:

```
root
 |-- id: string (nullable = true)
 |-- brand: string (nullable = true)
 |-- model: string (nullable = true)
 |-- year: string (nullable = true)
 |-- country: string (nullable = false)

+---+--------+----------+----+-------+
| id|   brand|     model|year|country|
+---+--------+----------+----+-------+
|  1|  Fender|Telecaster|1950|    USA|
|  2|  Gibson|  Les Paul|1959|    USA|
|  3|  Ibanez|        RG|1987|  Japan|
|  4|Takamine|Pro Series|1959|  Japan|
+---+--------+----------+----+-------+
```

### Example-4

Here's an example of data raw ingestion without applying any transformations.

```
{no_transform_example}
```

### Example-5

Here's an example of having multiple `Loader` implementations that is writing the transformed data into multiple destinations.

```
{multiple_output_example}
```

### Example-6

Using [Example-2](#Example-2), [Example-3](#Example-3) and [Example-5](#Example-5) as reference,
any combinations for single/multiple implementations of `Extractor`, `Transformer` or `Loader` can be created.

Here's an example of having both multiple `Extractor`, `Transformer` and `Loader` implementations.

It is important that the first transformer is a `MultiInputTransformer` when having multiple extractors.

```
{multi_multi_example}
```

### Example-7

In some cases a single destination dataset is not sufficient, as seen in this example.
Here we need to use the full power of the EtlBase class to return multiple datasets that
are then loaded by separate loaders.

Note that setting a key in the loader constructor allows it to pick out only one of the
inputs to save.

```
{many_to_many_example}
```

Result:
```
Orders ready to dispatch:
+--------+----------+---------+-----+--------------+
|order_id|payment_id|  product|price|charged_amount|
+--------+----------+---------+-----+--------------+
|       2|        46|Telescope|  200|           200|
|       1|        45|   Guitar|   50|            50|
+--------+----------+---------+-----+--------------+

Orders that need follow-up:
+--------+----------+-------+-----+--------------+
|order_id|payment_id|product|price|charged_amount|
+--------+----------+-------+-----+--------------+
|       3|        47| Tablet|  100|           150|
+--------+----------+-------+-----+--------------+
```
