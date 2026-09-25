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


class DataTests(unittest.TestCase):
    def test_streak_ending_today(self):
        self.assertEqual(build.streaks([0, 1, 1, 0, 2, 3, 1]), (3, 3))

    def test_streak_today_zero_counts_from_yesterday(self):
        self.assertEqual(build.streaks([1, 1, 0, 4, 4, 0]), (2, 2))

    def test_streak_broken_before_yesterday(self):
        self.assertEqual(build.streaks([5, 5, 5, 0, 0]), (0, 3))

    def test_streak_all_zero(self):
        self.assertEqual(build.streaks([0, 0, 0]), (0, 0))

    def test_streak_empty(self):
        self.assertEqual(build.streaks([]), (0, 0))

    def test_lang_shares_top5_sum_100(self):
        nodes = [
            {"languages": {"edges": [{"size": 600, "node": {"name": "Python"}}, {"size": 100, "node": {"name": "Shell"}}]}},
            {"languages": {"edges": [{"size": 200, "node": {"name": "Java"}}, {"size": 50, "node": {"name": "C"}},
                                     {"size": 40, "node": {"name": "TypeScript"}}, {"size": 10, "node": {"name": "Go"}}]}},
        ]
        shares = build.lang_shares(nodes)
        self.assertEqual([n for n, _ in shares], ["Python", "Java", "Shell", "C", "TypeScript"])
        self.assertAlmostEqual(sum(p for _, p in shares), 100, delta=0.3)

    def test_lang_shares_empty(self):
        self.assertEqual(build.lang_shares([{"languages": {"edges": []}}]), [])

    def test_summarize(self):
        user = {
            "contributionsCollection": {"contributionCalendar": {"totalContributions": 7, "weeks": [
                {"contributionDays": [{"date": "2026-09-24", "contributionCount": 3}, {"date": "2026-09-25", "contributionCount": 4}]}]}},
            "repositories": {"totalCount": 13, "nodes": []},
        }
        s = build.summarize(user)
        self.assertEqual((s["total"], s["current"], s["longest"], s["repos"], s["langs"], s["updated"]),
                         (7, 2, 2, 13, [], "2026-09-25"))


class FontTests(unittest.TestCase):
    def test_font_face_embeds_woff2(self):
        css = build.font_face("abc $~@", "pm")
        self.assertIn("font-family:pm", css)
        self.assertIn("data:font/woff2;base64,", css)
        self.assertLess(len(css), 20_000)

    def test_missing_glyph_is_named(self):
        with self.assertRaisesRegex(ValueError, "中"):
            build.font_face("ok 中", "pm")

    def test_name_path(self):
        d, width = build.name_path("PRATHAM NAGPAL", 40)
        self.assertTrue(d.startswith("M"))
        self.assertGreater(width, 200)
        self.assertLess(width, 780)

    def test_char_w_positive(self):
        self.assertGreater(build.char_w(14), 5)


if __name__ == "__main__":
    unittest.main()
