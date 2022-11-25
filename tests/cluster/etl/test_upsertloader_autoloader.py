from typing import List

from atc_tools.testing import DataframeTestCase

from atc import Configurator
from atc.delta import DbHandle, DeltaHandle
from atc.delta.autoloader_handle import AutoLoaderHandle
from atc.etl.loaders.UpsertLoader import UpsertLoader
from atc.functions import init_dbutils
from atc.utils import DataframeCreator
from atc.utils.FileExists import file_exists
from atc.utils.stop_all_streams import stop_all_streams
from tests.cluster.delta import extras
from tests.cluster.delta.SparkExecutor import SparkSqlExecutor


class UpsertLoaderTestsAutoloader(DataframeTestCase):
    target_id = "UpsertLoaderDummy"

    join_cols = ["col1", "col2"]

    data1 = [
        (5, 6, "foo"),
        (7, 8, "bar"),
    ]
    data2 = [
        (1, 2, "baz"),
    ]
    data3 = [(5, 6, "boo"), (5, 7, "spam")]
    # data5 is the merge result of data2 + data3 + data4
    data4 = [(1, 2, "baz"), (5, 6, "boo"), (5, 7, "spam"), (7, 8, "bar")]

    dummy_columns: List[str] = ["col1", "col2", "col3"]

    dummy_schema = None
    target_dh_dummy: DeltaHandle = None
    target_ah_dummy: AutoLoaderHandle = None

    @classmethod
    def setUpClass(cls) -> None:
        Configurator().add_resource_path(extras)
        Configurator().set_debug()

        # Test 01 view
        view1_checkpoint_path = "tmp/test1_df/_checkpoint_path"
        Configurator().register(
            "Test1View",
            {
                "name": "test1_df",
                "checkpoint_path": view1_checkpoint_path,
            },
        )

        if not file_exists(view1_checkpoint_path):
            init_dbutils().fs.mkdirs(view1_checkpoint_path)

        # Test 02 view
        view2_checkpoint_path = "tmp/test2_df/_checkpoint_path"
        Configurator().register(
            "Test2View",
            {
                "name": "test2_df",
                "checkpoint_path": view2_checkpoint_path,
            },
        )

        if not file_exists(view2_checkpoint_path):
            init_dbutils().fs.mkdirs(view2_checkpoint_path)

        # Test 03 view
        view3_checkpoint_path = "tmp/test3_df/_checkpoint_path"
        Configurator().register(
            "Test3View",
            {
                "name": "test3_df",
                "checkpoint_path": view3_checkpoint_path,
            },
        )

        if not file_exists(view3_checkpoint_path):
            init_dbutils().fs.mkdirs(view3_checkpoint_path)

        cls.target_ah_dummy = AutoLoaderHandle.from_tc("UpsertLoaderDummy")
        cls.target_dh_dummy = DeltaHandle.from_tc("UpsertLoaderDummy")

        SparkSqlExecutor().execute_sql_file("upsertloader-test")

        cls.dummy_schema = cls.target_dh_dummy.read().schema

        # make sure target is empty
        df_empty = DataframeCreator.make_partial(cls.dummy_schema, [], [])
        cls.target_dh_dummy.overwrite(df_empty)

    @classmethod
    def tearDownClass(cls) -> None:
        DbHandle.from_tc("UpsertLoaderDb").drop_cascade()
        stop_all_streams()

    def test_01_can_perform_incremental_on_empty(self):

        loader = UpsertLoader(handle=self.target_ah_dummy, join_cols=self.join_cols)

        df_source = DataframeCreator.make_partial(
            self.dummy_schema, self.dummy_columns, self.data1
        )

        df_source.createOrReplaceTempView("test1_df")

        read_tes1_df = AutoLoaderHandle.from_tc("Test1View").read()

        loader.save(read_tes1_df)
        self.assertDataframeMatches(self.target_dh_dummy.read(), None, self.data1)

    def test_02_can_perform_incremental_append(self):
        """The target table is already filled from before."""
        existing_rows = self.target_dh_dummy.read().collect()
        self.assertEqual(2, len(existing_rows))

        loader = UpsertLoader(handle=self.target_ah_dummy, join_cols=self.join_cols)

        df_source = DataframeCreator.make_partial(
            self.dummy_schema, self.dummy_columns, self.data2
        )

        df_source.createOrReplaceTempView("test2_df")

        read_tes2_df = AutoLoaderHandle.from_tc("Test2View").read()

        loader.save(read_tes2_df)

        self.assertDataframeMatches(
            self.target_dh_dummy.read(), None, self.data1 + self.data2
        )

    def test_03_can_perform_merge(self):
        """The target table is already filled from before."""
        existing_rows = self.target_dh_dummy.read().collect()
        self.assertEqual(3, len(existing_rows))

        loader = UpsertLoader(handle=self.target_dh_dummy, join_cols=self.join_cols)

        df_source = DataframeCreator.make_partial(
            self.dummy_schema, self.dummy_columns, self.data3
        )

        df_source.createOrReplaceTempView("test3_df")

        read_tes3_df = AutoLoaderHandle.from_tc("Test3View").read()

        loader.save(read_tes3_df)

        self.assertDataframeMatches(self.target_dh_dummy.read(), None, self.data4)
