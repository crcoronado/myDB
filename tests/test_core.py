import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mydb.data import CsvDatabase, detect_column, PART_NUMBER_ALIASES, PRICE_ALIASES, format_all, \
    format_part_number, format_price
from mydb.hotkey import parse_hotkey, pretty_hotkey

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


class TestDetect(unittest.TestCase):
    def test_english_and_spanish_headers(self):
        self.assertEqual(detect_column(["Desc", "P/N", "Cost"], PART_NUMBER_ALIASES), "P/N")
        self.assertEqual(detect_column(["Número de Parte", "Precio Lista USD"], PART_NUMBER_ALIASES), "Número de Parte")
        self.assertEqual(detect_column(["Número de Parte", "Precio Lista USD"], PRICE_ALIASES), "Precio Lista USD")
        self.assertIsNone(detect_column(["Foo", "Bar"], PRICE_ALIASES))


class TestDatabase(unittest.TestCase):
    def setUp(self):
        self.db = CsvDatabase("simple", os.path.join(DATA, "sample_simple.csv"))
        self.db.load()

    def test_load(self):
        self.assertEqual(self.db.headers, ["Part Number", "Description", "Price"])
        self.assertEqual(len(self.db.rows), 15)
        self.assertEqual(self.db.pn_col, "Part Number")
        self.assertEqual(self.db.price_col, "Price")

    def test_search_multi_word_any_order(self):
        idx, total = self.db.search("wi-fi xgs")
        pns = {self.db.rows[i]["Part Number"] for i in idx}
        self.assertEqual(pns, {"ONU-XGS-10G-W6", "ONU-XGS-10G-W7"})
        self.assertEqual(total, 2)

    def test_part_number_prefix_ranked_first(self):
        idx, _ = self.db.search("sfp")
        self.assertTrue(self.db.rows[idx[0]]["Part Number"].startswith("SFP"))

    def test_limit(self):
        idx, total = self.db.search("", limit=5)
        self.assertEqual((len(idx), total), (5, 15))

    def test_formats(self):
        row = self.db.rows[0]
        self.assertEqual(format_part_number(self.db, row), "CM-D31-24X8")
        self.assertEqual(format_price(self.db, row), "89.00")
        self.assertIn("Price: 89.00", format_all(self.db, row, "lines"))
        self.assertEqual(format_all(self.db, row, "tsv").splitlines()[1].split("\t")[0], "CM-D31-24X8")
        self.assertIn('"Price": "89.00"', format_all(self.db, row, "json"))

    def test_semicolon_cp1252_and_override(self):
        with tempfile.NamedTemporaryFile("wb", suffix=".csv", delete=False) as fh:
            fh.write("Código;Descripción;Precio\nA-1;Módem;10,50\n".encode("cp1252"))
        try:
            db = CsvDatabase("x", fh.name, part_number_column="Código")
            db.load()
            self.assertEqual(db.rows[0]["Descripción"], "Módem")
            self.assertEqual(format_price(db, db.rows[0]), "10,50")
            self.assertEqual(format_part_number(db, db.rows[0]), "A-1")
        finally:
            os.unlink(fh.name)

    def test_reload_on_change(self):
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8") as fh:
            fh.write("SKU,Price\nA,1\n")
        try:
            db = CsvDatabase("x", fh.name)
            db.load()
            self.assertEqual(len(db.rows), 1)
            with open(fh.name, "a", encoding="utf-8") as out:
                out.write("B,2\n")
            os.utime(fh.name, (0, os.path.getmtime(fh.name) + 5))
            db.load()
            self.assertEqual(len(db.rows), 2)
        finally:
            os.unlink(fh.name)


class TestHotkey(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(parse_hotkey("<ctrl>+<shift>+s"), (frozenset({"ctrl", "shift"}), "s"))
        self.assertEqual(pretty_hotkey("<ctrl>+<shift>+s"), "Ctrl+Shift+S")
        with self.assertRaises(ValueError):
            parse_hotkey("<ctrl>+<shift>")


class FakeNSEvent:
    def __init__(self, flags, chars):
        self._f, self._c = flags, chars

    def modifierFlags(self):
        return self._f

    def charactersIgnoringModifiers(self):
        return self._c


class TestMacHotkeyMatching(unittest.TestCase):
    def test_ctrl_shift_s(self):
        from mydb.system import MacHotkey
        hk = MacHotkey("<ctrl>+<shift>+s", lambda: None)
        ctrl, shift, cmd = 1 << 18, 1 << 17, 1 << 20
        caps_lock, fn = 1 << 16, 1 << 23  # must not break matching
        self.assertTrue(hk._matches(FakeNSEvent(ctrl | shift, "S")))
        self.assertTrue(hk._matches(FakeNSEvent(ctrl | shift | caps_lock | fn | 0x100, "S")))
        self.assertFalse(hk._matches(FakeNSEvent(cmd | shift, "S")))      # ⌘⇧S (Save As) ignored
        self.assertFalse(hk._matches(FakeNSEvent(ctrl | shift | cmd, "S")))
        self.assertFalse(hk._matches(FakeNSEvent(ctrl | shift, "D")))


if __name__ == "__main__":
    unittest.main()
