import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build


class CoreTests(unittest.TestCase):
    def test_esc_escapes_markup(self):
        self.assertEqual(build.esc('a<b & "c"'), "a&lt;b &amp; &quot;c&quot;")

    def test_validate_rejects_bad_xml(self):
        with self.assertRaises(ValueError):
            build.validate("<svg><g></svg>")

    def test_validate_rejects_oversize(self):
        big = '<svg xmlns="http://www.w3.org/2000/svg">' + "x" * build.MAX_BYTES + "</svg>"
        with self.assertRaises(ValueError):
            build.validate(big)

    def test_validate_accepts_small_svg(self):
        build.validate('<svg xmlns="http://www.w3.org/2000/svg"/>')

    def test_write_atomic_replaces_content(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "a.svg"
            p.write_text("old", encoding="utf-8")
            build.write_atomic(p, "new")
            self.assertEqual(p.read_text(encoding="utf-8"), "new")
            self.assertEqual(sorted(x.name for x in Path(d).iterdir()), ["a.svg"])

    def test_icons_vendored(self):
        self.assertEqual(len(list((build.ASSETS / "icons").glob("*.svg"))), 15)


if __name__ == "__main__":
    unittest.main()
