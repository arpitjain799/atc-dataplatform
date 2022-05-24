import sys
from datetime import datetime, timezone
from random import randint
from typing import List, Optional

import pyspark.sql.functions as f
import pyspark.sql.types as t
from pyspark.sql import DataFrame, Window

from atc.etl import Loader

from ..spark import Spark
from .CachedLoaderParameters import CachedLoaderParameters


class CachedLoader(Loader):
    """
    Remember to override self.write_operation and/or self.delete_operation
    Any variable rows need to be added in this function.
    """

    class ReductionResult:
        to_be_written: DataFrame
        to_be_deleted: DataFrame

    def __init__(self, params: CachedLoaderParameters):
        super().__init__()
        self.params = params
        self.validate()

        self.n_rows_all_writes = 0
        self.n_rows_last_write = 0

    def validate(self):
        # validate cache table schema
        p = self.params
        df = Spark.get().table(p.cache_table_name)
        try:

            assert set(df.columns) == set(
                p.key_cols + p.cache_id_cols + [p.rowHash, p.loadedTime, p.deletedTime]
            )
        except AssertionError:
            print(
                "ERROR: The cache table needs to have precisely the correct schema."
                " Found:",
                df.columns,
                file=sys.stderr,
            )
            raise

        # validate overloading
        write_overloaded = "write_operation" in self.__class__.__dict__
        delete_overloaded = "delete_operation" in self.__class__.__dict__
        if not (write_overloaded or delete_overloaded):
            raise AssertionError(
                "overload of write_operation " "or delete_operation required"
            )

        if self.__class__ is CachedLoader:
            raise AssertionError("You should inherit from this class")

    def write_operation(self, df: DataFrame) -> Optional[DataFrame]:
        """Abstract Method to be overridden in child."""
        return None

    def delete_operation(self, df: DataFrame) -> Optional[DataFrame]:
        """Abstract Method to be overridden in child."""
        return df

    def save(self, df: DataFrame) -> None:
        in_cols = df.columns

        if not set(self.params.key_cols).issubset(in_cols):
            raise AssertionError(
                "The key columns must be given in the input dataframe."
            )

        # ensure that no duplicates exist. The keys have to be a unique set.
        df = df.dropDuplicates(self.params.key_cols)

        cache = self._extract_cache()

        result = self._discard_non_new_rows_against_cache(df, cache)

        # write branch
        df_written = self.write_operation(result.to_be_written)
        if df_written:
            self.n_rows_last_write = df_written.count()
            self.n_rows_all_writes += self.n_rows_last_write

            # this line only executes if the line above does not raise an exception.
            df_written_cache_update = self._prepare_written_cache_update(
                df_written, in_cols
            )
            self._load_cache(df_written_cache_update)

        # delete branch
        df_deleted = self.delete_operation(result.to_be_deleted)
        if df_deleted:
            df_deleted_cache_update = self._prepare_deleted_cache_update(df_deleted)

            self._load_cache(df_deleted_cache_update)
            # this method is called a again separately in order to ensure that the
            # written cache is saved even if the delete operation fails.

        return

    def _extract_cache(self) -> DataFrame:
        # here we fix the version,
        # so we don't overwrite the cache before we might want to use it.
        version = (
            Spark.get()
            .sql(f"DESCRIBE HISTORY {self.params.cache_table_name} LIMIT 1")
            .select("version")
            .take(1)[0][0]
        )
        cache = Spark.get().sql(
            f"SELECT * FROM {self.params.cache_table_name} VERSION AS OF {version}"
            f" WHERE {self.params.deletedTime} IS NULL"
            f" AND {self.params.rowHash} IS NOT NULL"
            f" AND {self.params.loadedTime} IS NOT NULL"
        )

        return cache

    def _prepare_written_cache_update(self, df: DataFrame, columns_to_hash: List[str]):
        # re-hash the input row
        return df.select(
            *self.params.key_cols,
            f.hash(*columns_to_hash).alias(self.params.rowHash),
            f.current_timestamp().alias(self.params.loadedTime),
            f.lit(None).cast("timestamp").alias(self.params.deletedTime),
            *self.params.cache_id_cols,
        )

    def _prepare_deleted_cache_update(self, df: DataFrame):
        return df.select(
            *self.params.key_cols,
            self.params.rowHash,
            self.params.loadedTime,
            f.current_timestamp().alias(self.params.deletedTime),
            *self.params.cache_id_cols,
        )

    def _load_cache(self, cache_to_load: DataFrame) -> None:

        view_name = (
            self.params.cache_table_name.replace(".", "_")
            + f"_Update{randint(0, 1000):03}"
        )
        merge_sql_statement = (
            f"MERGE INTO {self.params.cache_table_name} AS target "
            f"USING {view_name} as source "
            f"ON "
            + (
                " AND ".join(
                    f"(source.{col} = target.{col})" for col in self.params.key_cols
                )
            )
            +
            # update existing records
            "WHEN MATCHED THEN UPDATE SET * "
            # insert new records.
            "WHEN NOT MATCHED THEN INSERT * "
        )
        cache_to_load.createOrReplaceTempView(view_name)
        Spark.get().sql(merge_sql_statement)

    def _discard_non_new_rows_against_cache(
        self, df_in: DataFrame, cache: DataFrame
    ) -> ReductionResult:
        """
        Returns:
            to_be_written contains only rows that
             - are new in the cache, or
             - are a mismatch against the cache, or
             - have been loaded longer ago than max_ttl, or
             - have been loaded longer ago than refresh_ttl,
                - but only if there is budget left within refresh_row_limit
                - prioritization is done based on loadedTime, oldest first.

        """

        # ensure no null keys:
        df_in = df_in.filter(
            " AND ".join(f"({col} is NOT NULL)" for col in self.params.key_cols)
        )

        # prepare hash of row
        df_hashed = df_in.withColumn("rowHash", f.hash("*"))

        # add a column to distinguish rows after the join
        df_hashed = df_hashed.withColumn("fromPayload", f.lit(True))

        # join with cache
        joined_df = (
            df_hashed.alias("df")
            .join(cache.alias("cache"), self.params.key_cols, "full")
            .cache()
        )

        # rows coming from the original df will have a non-null fromPayload column
        joined_df_incoming = (
            joined_df.filter("fromPayload IS NOT NULL")
            .select(
                *self.params.key_cols,
                "df.*",
                "cache.loadedTime",
                (f.col("df.rowHash") == f.col("cache.rowHash")).alias("hashMatch"),
            )
            .drop("fromPayload")
        )

        # cached rows with no incoming match will have a null fromPayload column
        to_be_deleted = (
            joined_df.filter("fromPayload IS NULL")
            .select(*self.params.key_cols, "cache.*")
            .drop("fromPayload")
        )

        # add a priority column
        now = datetime.now(timezone.utc).timestamp()
        filtered_df = (
            joined_df_incoming.withColumn(
                "_lived", now - f.col("loadedTime").cast(t.LongType())
            )
            .withColumn(
                "__cachePriority",
                # new rows without cache hit
                f.when(f.col("loadedTime").isNull(), 1)
                # rows that are known to be different
                .when(f.col("hashMatch") == f.lit(False), 1)
                # rows that are old enough to warrant a refresh
                .when(
                    (f.lit(self.params.max_ttl) > 0)
                    & (f.col("_lived") > self.params.max_ttl),
                    2,
                )
                .when(
                    (f.lit(self.params.refresh_ttl) > 0)
                    & (f.col("_lived") > self.params.refresh_ttl),
                    3,
                )
                .otherwise(1000),
            )
            .drop("_lived")
            .filter(f.col("__cachePriority") < 100)
        )

        if self.params.refresh_row_limit > 0:
            # if there is a row_limit, order the columns
            w = Window.orderBy("__cachePriority", "loadedTime")
            filtered_df = (
                filtered_df.withColumn("__cacheOrder", f.row_number().over(w))
                .filter(
                    # take all priority 1 (new, mismatch) and 2 (max_ttl)
                    (f.col("__cachePriority") < 3)
                    |
                    # only take lower ranked items up to row_limit
                    (f.col("__cacheOrder") <= self.params.refresh_row_limit)
                )
                .drop("__cacheOrder")
            )

        result = self.ReductionResult()
        result.to_be_written = filtered_df.drop(
            "__cachePriority", "rowHash", "hashMatch", "loadedTime"
        )
        result.to_be_deleted = to_be_deleted

        return result
