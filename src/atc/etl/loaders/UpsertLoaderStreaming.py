from typing import List

from pyspark.sql import DataFrame

from atc.etl import Loader, dataset_group
from atc.etl.loaders.stream_loader import StreamLoader
from atc.tables import TableHandle


class UpsertLoaderStreaming(Loader):
    def __init__(
        self,
        handle: TableHandle,
        format: str,
        options_dict: dict,
        trigger_type: str = None,
        loader: Loader = None,
        trigger_time_seconds: int = None,
        outputmode: str = "update",
        query_name: str = None,
        checkpoint_path: str = None,
        await_termination: bool = False,
        upsert_join_cols: List[str] = None,
    ):
        super().__init__()

        self._loader = StreamLoader(
            handle=handle,
            format=format,
            options_dict=options_dict,
            mode="upsert",
            trigger_type=trigger_type,
            trigger_time_seconds=trigger_time_seconds,
            outputmode="update",
            query_name=query_name,
            checkpoint_path=checkpoint_path,
            await_termination=await_termination,
            upsert_join_cols=upsert_join_cols,
        )

    def save_many(self, datasets: dataset_group) -> None:
        raise NotImplementedError()

    def save(self, df: DataFrame) -> None:
        """Upserts a single dataframe to the target table."""
        self._loader.save(df)
