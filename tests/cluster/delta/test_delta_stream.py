import unittest

from pyspark.sql.utils import AnalysisException

from atc import Configurator
from atc.delta import DbHandle, DeltaHandle
from atc.etl import Orchestrator
from atc.etl.extractors.stream_extractor import StreamExtractor
from atc.etl.loaders.stream_loader import StreamLoader
from atc.spark import Spark
from atc.utils.stop_all_streams import stop_all_streams


@unittest.skipUnless(
    Spark.version() >= Spark.DATABRICKS_RUNTIME_10_4,
    f"DeltaStreamHandle not available for Spark version {Spark.version()}",
)
class DeltaStreamTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        Configurator().clear_all_configurations()
        Configurator().set_debug()

    @classmethod
    def tearDownClass(cls) -> None:
        DbHandle.from_tc("MyDb").drop_cascade()
        stop_all_streams()

    def test_01_configure(self):
        tc = Configurator()
        tc.register(
            "MyDb", {"name": "TestDb{ID}", "path": "/mnt/atc/silver/testdb{ID}"}
        )

        tc.register(
            "MyTbl",
            {
                "name": "TestDb{ID}.TestTbl",
                "path": "/mnt/atc/silver/testdb{ID}/testtbl",
                "format": "delta",
                "checkpoint_path": "/mnt/atc/silver/testdb{ID}/_checkpoint_path_tbl",
            },
        )

        mirror_cp_path = "/mnt/atc/silver/testdb{ID}/_checkpoint_path_tblmirror"
        tc.register(
            "MyTblMirror",
            {
                "name": "TestDb{ID}.TestTblMirror",
                "path": "/mnt/atc/silver/testdb{ID}/testtblmirror",
                "format": "delta",
                "checkpoint_path": mirror_cp_path,
                "await_termination": True,
            },
        )

        tc.register(
            "MyTbl2",
            {
                "name": "TestDb{ID}.TestTbl2",
                "format": "delta",
                "checkpoint_path": "/mnt/atc/silver/testdb{ID}/_checkpoint_path_tbl2",
            },
        )

        tc.register(
            "MyTbl3",
            {
                "path": "/mnt/atc/silver/testdb{ID}/testtbl3",
                "format": "delta",
                "checkpoint_path": "/mnt/atc/silver/testdb{ID}/_checkpoint_path_tbl3",
                "await_termination": True,
            },
        )

        tc.register(
            "MyTbl4",
            {
                "name": "TestDb{ID}.TestTbl4",
                "path": "/mnt/atc/silver/testdb{ID}/testtbl4",
                "format": "delta",
                "checkpoint_path": "/mnt/atc/silver/testdb{ID}/_checkpoint_path_tbl4",
            },
        )

        tc.register(
            "MyTbl5",
            {
                "name": "TestDb{ID}.TestTbl5",
                "path": "/mnt/atc/silver/testdb{ID}/testtbl5",
                "format": "delta",
                "checkpoint_path": "/mnt/atc/silver/testdb{ID}/_checkpoint_path_tbl5",
            },
        )

        # test instantiation without error
        DbHandle.from_tc("MyDb")
        DeltaHandle.from_tc("MyTbl")
        DeltaHandle.from_tc("MyTblMirror")
        DeltaHandle.from_tc("MyTbl2")
        DeltaHandle.from_tc("MyTbl3")
        DeltaHandle.from_tc("MyTbl4")
        DeltaHandle.from_tc("MyTbl5")

    def test_02_write_data_with_deltahandle(self):
        self._overwrite_two_rows_to_table("MyTbl")

    def test_03_create(self):
        db = DbHandle.from_tc("MyDb")
        db.create()

        dh = DeltaHandle.from_tc("MyTbl")
        dh.create_hive_table()

        # test hive access:
        df = dh.read()
        self.assertEqual(2, df.count())

    def test_04_read(self):
        df = DeltaHandle.from_tc("MyTbl").read_stream()
        self.assertTrue(df.isStreaming)

    def test_05_truncate(self):
        dsh = DeltaHandle.from_tc("MyTbl")
        dsh.truncate()

        result = DeltaHandle.from_tc("MyTbl").read()
        self.assertEqual(0, result.count())

    def test_06_etl(self):
        self._overwrite_two_rows_to_table("MyTbl")
        self._create_tbl_mirror()

        dh = DeltaHandle.from_tc("MyTbl")
        dh_target = DeltaHandle.from_tc("MyTblMirror")

        o = Orchestrator()
        o.extract_from(StreamExtractor(dh, dataset_key="MyTbl"))
        o.load_into(
            StreamLoader(
                handle=dh_target,
                options_dict={},
                format="delta",
                await_termination=True,
                mode="append",
                checkpoint_path=Configurator().get("MyTblMirror", "checkpoint_path"),
            )
        )
        o.execute()

        result = DeltaHandle.from_tc("MyTblMirror").read()
        self.assertEqual(2, result.count())

    def test_07_write_path_only(self):
        self._overwrite_two_rows_to_table("MyTbl")
        # check that we can write to the table with no "name" property
        dh1 = DeltaHandle.from_tc("MyTbl")

        dh3 = DeltaHandle.from_tc("MyTbl3")

        # dsh3.append(ah, mergeSchema=True)

        o = Orchestrator()
        o.extract_from(StreamExtractor(dh1, dataset_key="MyTbl"))
        o.load_into(
            StreamLoader(
                handle=dh3,
                options_dict={},
                format="delta",
                await_termination=True,
                mode="append",
                checkpoint_path=Configurator().get("MyTbl3", "checkpoint_path"),
            ),
        )
        o.execute()

        # Read data from mytbl3
        result = dh3.read()
        self.assertEqual(2, result.count())

    def test_08_delete(self):
        dh = DeltaHandle.from_tc("MyTbl")
        dh.drop_and_delete()
        with self.assertRaises(AnalysisException):
            dh.read()

    def _overwrite_two_rows_to_table(self, tblid: str):
        dh = DeltaHandle.from_tc(tblid)

        df = Spark.get().createDataFrame([(1, "a"), (2, "b")], "id int, name string")

        dh.overwrite(df, mergeSchema=True)

    def _create_tbl_mirror(self):
        dh = DeltaHandle.from_tc("MyTblMirror")
        Spark.get().sql(
            f"""
                            CREATE TABLE {dh.get_tablename()}
                            (
                            id int,
                            name string
                            )
                            LOCATION '{Configurator().get("MyTblMirror","path")}'
                        """
        )
