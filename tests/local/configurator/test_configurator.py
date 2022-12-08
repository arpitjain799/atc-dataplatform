import unittest

from pyspark.sql import types

from atc import Configurator
from atc.schema_manager import SchemaManager
from tests.local.configurator import sql, tables1, tables2, tables3, tables4, tables5


class TestConfigurator(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        Configurator().clear_all_configurations()

    def test_01_import_config(self):
        tc = Configurator()
        tc.add_resource_path(tables1)

        tc.reset(debug=True)
        self.assertRegex(tc.table_name("MyFirst"), "first__.*")
        self.assertRegex(tc.table_name("MyAlias"), "first__.*")
        self.assertRegex(tc.table_name("MyForked"), "another")

        tc.reset(debug=False)
        self.assertRegex(tc.table_name("MyFirst"), "first")
        self.assertRegex(tc.table_name("MyAlias"), "first")
        self.assertRegex(tc.table_name("MyForked"), "first")

    def test_02_details(self):
        tc = Configurator()

        tc.reset(debug=True)
        details = tc.get_all_details()
        self.assertRegex(details["MyFirst_path"], "/tmp/my/first__.*")

        tc.reset(debug=False)
        details = tc.get_all_details()
        self.assertRegex(details["MyFirst_path"], "/mnt/my/first")

    def test_03_json(self):
        tc = Configurator()

        with self.assertRaises(KeyError):
            tc.add_resource_path(tables2)

        tc.set_extra(ENV="dev")
        tc.add_resource_path(tables2)
        tc.reset(debug=True)
        self.assertRegex(tc.table_name("MyThird"), "first__.*")

        self.assertRegex(
            tc.get_all_details()["MyFourth_path"], "/tmp/dev/path/to/delta"
        )

    def test_04_recursing(self):
        tc = Configurator()
        tc.set_prod()
        self.assertEqual(tc.get("MyRecursing", "path"), "/mnt/tables/recursing")

    def test_05_test_self_recursion_detection(self):
        tc = Configurator()
        tc.set_prod()
        with self.assertRaises(ValueError):
            tc.add_resource_path(tables3)

    def test_06_freestyle(self):
        tc = Configurator()
        tc.set_prod()
        tc.add_resource_path(tables4)
        details = tc.get_all_details()
        self.assertTrue("MyFreeTable_eggs", details)
        self.assertEqual(tc.table_property("MyFreeTable", "bacon"), "")

    def test_07_bare_strings_and_structures(self):
        tc = Configurator()
        tc.set_prod()
        tc.add_resource_path(tables5)
        self.assertEqual(tc.get("MyPlainLiteral"), "Bar")
        self.assertEqual(tc.get_all_details()["MyCompositeLiteral"], "FooBar")
        self.assertEqual(
            tc.get("MyComposite", "schema"), {"sql": "TODO: support this\n"}
        )
        self.assertEqual(tc.table_name("MyComposite"), "ottoBar")

    def test_08_test_deprecated_import(self):
        from atc import Configurator
        from atc.config_master import TableConfigurator

        tc = TableConfigurator()
        self.assertEqual(tc.table_name("MyComposite"), "ottoBar")

        c = Configurator()

        self.assertIs(tc, c)

    def test_09_configure_from_sql(self):
        c = Configurator()
        c.clear_all_configurations()
        c.add_sql_resource_path(sql)
        c.set_prod()

        self.assertEqual(c.get("MySparkDb", "name"), "my_db1")
        self.assertEqual(c.get("MySparkDb", "path"), "/tmp/foo/bar/my_db1/")
        self.assertEqual(c.get("MySparkDb", "format"), "db")

        self.assertEqual(c.get("MySqlTable", "name"), "my_db1.tbl1")
        c.set_debug()
        self.assertEqual(c.get("MySqlTable", "path"), "/tmp/foo/bar/my_db1/tbl1/")
        self.assertEqual(c.get("MySqlTable", "format"), "delta")
        self.assertEqual(
            SchemaManager().get_schema("MySqlTable"),
            types._parse_datatype_string("""a int, b int, c string, d timestamp"""),
        )

        self.assertEqual(
            SchemaManager().get_schema_as_string("MyDetailsTable"),
            """a int, b int, c string, d timestamp, another int,""",
        )
