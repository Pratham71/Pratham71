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


STATS = {"total": 412, "current": 1, "longest": 9, "repos": 13,
         "langs": [("Python", 70.0), ("Java", 20.0), ("Shell", 10.0)], "updated": "2026-09-25"}


class TemplateTests(unittest.TestCase):
    def test_all_templates_valid(self):
        c = build.CONTENT
        for svg in (build.render_header(c), build.render_card(c["projects"]["homelab"]),
                    build.render_card(c["projects"]["vessel"]), build.render_stack(c["stack"]),
                    build.render_stats(STATS)):
            build.validate(svg)

    def test_card_escapes_text(self):
        svg = build.render_card({"name": "a<b", "desc": "x & y", "lang": "C", "status": "active"})
        self.assertIn("a&lt;b", svg)
        self.assertIn("x &amp; y", svg)
        build.validate(svg)

    def test_card_rejects_overlong_desc(self):
        with self.assertRaisesRegex(ValueError, "toolong"):
            build.render_card({"name": "toolong", "desc": "word " * 60, "lang": "C", "status": "active"})

    def test_unknown_status_rejected(self):
        with self.assertRaises(ValueError):
            build.status_mark("paused", 0, 0)

    def test_days_pluralises(self):
        self.assertEqual((build.days(0), build.days(1), build.days(2)), ("0 days", "1 day", "2 days"))

    def test_stats_without_languages(self):
        svg = build.render_stats(dict(STATS, langs=[], total=0, current=0, longest=0))
        self.assertIn("no language data", svg)
        build.validate(svg)

    def test_stats_labels_do_not_collide(self):
        longest = max(len(l) for l in ("contributions, last year", "current streak", "longest streak, last year", "public repos"))
        self.assertGreaterEqual(build.STATS_COL - longest * build.char_w(12), 16)

    def test_header_text_visible_without_animation(self):
        svg = build.render_header(build.CONTENT)
        self.assertNotIn("opacity:0;", svg)
        self.assertIn(" backwards", svg)

    def test_longest_streak_label_scoped_to_last_year(self):
        self.assertIn("longest streak, last year", build.render_stats(STATS))

    def test_header_has_reduced_motion(self):
        self.assertIn("prefers-reduced-motion", build.render_header(build.CONTENT))


class MainTests(unittest.TestCase):
    def test_build_all_names(self):
        self.assertEqual(sorted(build.build_all(STATS)),
                         ["card-homelab.svg", "card-vessel.svg", "header.svg", "stack.svg", "stats.svg"])

    def test_fetch_failure_leaves_assets_untouched(self):
        with tempfile.TemporaryDirectory() as d:
            old = Path(d) / "stats.svg"
            old.write_text("previous", encoding="utf-8")
            orig_fetch, orig_out, orig_token = build.fetch, build.OUT, build.token

            def boom(*a):
                raise RuntimeError("api down")
            build.fetch, build.OUT, build.token = boom, Path(d), lambda: "t"
            try:
                with self.assertRaises(RuntimeError):
                    build.main()
            finally:
                build.fetch, build.OUT, build.token = orig_fetch, orig_out, orig_token
            self.assertEqual(old.read_text(encoding="utf-8"), "previous")


if __name__ == "__main__":
    unittest.main()
