import unittest

from pyspark.sql import DataFrame
from pyspark.sql.types import StructType, StructField, IntegerType

from atc.config_master import TableConfigurator
from atc.functions import get_unique_tempview_name
from atc.utils import DataframeCreator
from tests.cluster.sql.DeliverySqlServer import DeliverySqlServer
from . import extras


class DeliverySqlServerTests(unittest.TestCase):
    tc = None
    sql_server = None
    table_name = get_unique_tempview_name()
    view_name = get_unique_tempview_name()

    @classmethod
    def setUpClass(cls):
        cls.sql_server = DeliverySqlServer()
        tc = TableConfigurator()

        tc.add_resource_path(extras)
        tc.reset(debug=True)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.sql_server.drop_table_by_name(cls.table_name)
        t1 = cls.tc.table_name("SqlTestTable1")
        t2 = cls.tc.table_name("SqlTestTable2")
        v1 = cls.tc.table_name("SqlTestView")
        cls.sql_server.drop_table_by_name(t1)
        cls.sql_server.drop_table_by_name(t2)
        cls.sql_server.drop_view_by_name(v1)

        cls.tc.reset(debug=False)

    def test01_can_connect(self):
        self.sql_server.test_odbc_connection()
        self.assertTrue(True)

    def test02_can_create_dummy(self):
        self.create_test_table()
        self.assertTrue(True)

    def test03_can_read_dummy(self):
        self.sql_server.read_table_by_name(self.table_name)
        self.assertTrue(True)

    def test03_can_truncate_dummy(self):

        self.insert_single_row()
        df_with_data = self.sql_server.read_table_by_name(self.table_name)
        self.assertEqual(df_with_data.count(), 1)

        # Truncate
        self.sql_server.truncate_table_by_name(self.table_name)
        df_without_data = self.sql_server.read_table_by_name(self.table_name)
        self.assertEqual(df_without_data.count(), 0)

    def test04_can_load_sql_spark_dummy(self):
        sql_argument = f"""
                (select * from {self.table_name}) target
                                """
        self.insert_single_row()
        df_with_data = self.sql_server.load_sql(sql_argument)
        self.assertEqual(df_with_data.count(), 1)

    def test05_can_drop_table_dummy(self):
        self.sql_server.drop_table_by_name(self.table_name)

        sql_argument = f"""
        SELECT *
                 FROM INFORMATION_SCHEMA.TABLES
                 WHERE
                 TABLE_NAME = '{self.table_name}'
        """
        table_exists = self.sql_server.load_sql(sql_argument)
        self.assertEqual(table_exists.count(), 0)

    def test06_write_table_spark_dummy(self):
        df_export = self.create_data()
        self.sql_server.write_table(df_export, self.table_name)
        df_with_data = self.sql_server.read_table_by_name(self.table_name)
        self.assertEqual(df_with_data.count(), 1)

    def test07_write_table_spark_no_table_exists_dummy(self):
        # Drop the table
        self.sql_server.drop_table_by_name(self.table_name)

        # Create data to export
        df_export = self.create_data()
        self.sql_server.write_table(df_export, self.table_name)

        # Load data
        df_with_data = self.sql_server.read_table_by_name(self.table_name)
        self.assertEqual(df_with_data.count(), 1)

    def test08_get_table_name(self):
        test_name1 = self.sql_server.table_name("SqlTestTable1")
        self.assertIn("dbo.test1", test_name1)
        test_name2 = self.sql_server.table_name("SqlTestTable2")
        self.assertIn("dbo.test2", test_name1)

    def test09_execute_sql_file(self):

        file_name = "test1.sql"
        path_name = "tests.cluster.sql.extras"
        sql_arguments = {
            "table_name1": TableConfigurator().table_name("SqlTestTable1"),
            "table_name2": TableConfigurator().table_name("SqlTestTable2"),
        }

        # Create the table
        self.sql_server.execute_sql_file(file_name, path_name, sql_arguments)
        self.assertTrue(True)

    def test10_read_w_id(self):
        # Read by id
        self.sql_server.read_table("SqlTestTable1")
        self.sql_server.read_table("SqlTestTable2")
        self.assertTrue(True)

    def test11_write_w_id(self):
        df = self.create_data()
        self.sql_server.write_table(df, "SqlTestTable1")
        df_with_data = self.sql_server.read_table("SqlTestTable1")
        self.assertEqual(df_with_data.count(), 1)

    def test12_truncate_w_id(self):

        # Truncate
        self.sql_server.truncate_table("SqlTestTable1")
        df_without_data = self.sql_server.read_table("SqlTestTable1")
        self.assertEqual(df_without_data.count(), 0)

    def test13_drop_w_id(self):
        self.sql_server.drop_table("SqlTestTable1")

        table1_name = self.tc.table_name("SqlTestTable1")
        sql_argument = f"""
                SELECT *
                         FROM INFORMATION_SCHEMA.TABLES
                         WHERE
                         TABLE_NAME = '{table1_name}'
                """
        table_exists = self.sql_server.load_sql(sql_argument)
        self.assertEqual(table_exists.count(), 0)

    def test14_can_drop_view_w_id(self):
        # Create view
        view_name = self.tc.table_name("SqlTestView")
        self.assertIn("viewtest1", view_name)
        table_from = self.tc.table_name("SqlTestTable2")
        self.create_test_view(view_name, table_from)
        self.assertTrue(True)

        # Drop view by id
        self.sql_server.drop_view("SqlTestView")

        sql_argument = f"""
        select
                    *
                    from
                    INFORMATION_SCHEMA.VIEWS
                    where
                    table_name = '{view_name}'
        """
        table_exists = self.sql_server.load_sql(sql_argument)
        self.assertEqual(table_exists.count(), 0)

    def test15_can_drop_view_by_name(self):
        table_from = self.tc.table_name("SqlTestTable2")
        self.create_test_view(self.view_name, table_from)
        self.sql_server.drop_view_by_name(self.view_name)
        sql_argument = f"""
                select
                            *
                            from
                            INFORMATION_SCHEMA.VIEWS
                            where
                            table_name = '{self.view_name}'
                """
        table_exists = self.sql_server.load_sql(sql_argument)
        self.assertEqual(table_exists.count(), 0)

    def create_test_table(self):
        sql_argument = f"""
                IF OBJECT_ID('{self.table_name}', 'U') IS NULL
                BEGIN
                CREATE TABLE {self.table_name}
                (
                testcolumn INT NULL
                )
                END
                                """
        self.sql_server.execute_sql(sql_argument)

    def insert_single_row(self):
        insert_data = 123

        sql_argument = f"""
                            INSERT INTO {self.table_name} values ({insert_data})
                                        """
        self.sql_server.execute_sql(sql_argument)

    def create_data(self) -> DataFrame:
        schema = StructType(
            [
                StructField("testcolumn", IntegerType(), True),
            ]
        )
        cols = ["testcolumn"]
        df_new = DataframeCreator.make_partial(
            schema=schema, columns=cols, data=[(456,)]
        )

        return df_new.orderBy("testcolumn")

    def create_test_view(self, view_name, select_from_table):
        sql_argument = f"""

                    CREATE OR ALTER VIEW {view_name} as
                    (
                    select * from {select_from_table}
                    )
                      """
        self.sql_server.execute_sql(sql_argument)
