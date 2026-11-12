from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from urllib.parse import quote

import tools


class SearchStudyCardsTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

        self._original_dir = tools.STUDY_CARDS_DIR
        self._original_max = tools.STUDY_CARD_MAX_BYTES
        tools.STUDY_CARDS_DIR = self.root
        self.addCleanup(self._restore_globals)

    def _restore_globals(self):
        tools.STUDY_CARDS_DIR = self._original_dir
        tools.STUDY_CARD_MAX_BYTES = self._original_max

    def write(self, relative, content):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def write_bytes(self, relative, data):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def search(self, query, limit=5):
        return tools.search_study_cards(query, limit=limit)

    def search_multi(self, queries, limit=5):
        return tools.search_study_cards_multi(queries, limit=limit)

    def test_strong_part_number_matches_name_alone(self):
        self.write(
            "7400 quad nand chip [74LS00-74HC00].md",
            "# 74x00 - 74LS00/74HC00\n## Quad NAND gate chip\n",
        )

        hits = self.search("what is the pin-out for the 74HC00 chip")

        self.assertEqual(
            [hit.title for hit in hits], ["7400 quad nand chip [74LS00-74HC00]"]
        )

    def test_multi_query_union_ranks_all_keyword_matches(self):
        self.write("pi pico adc.md", "analog input")
        self.write(
            "7400 quad nand chip [74LS00-74HC00].md",
            "# 74x00 - 74LS00/74HC00\n## Quad NAND gate chip\n",
        )

        hits = self.search_multi(["74HC00 pin-out", "pi pico ADC"])

        self.assertEqual(
            sorted(hit.title for hit in hits),
            ["7400 quad nand chip [74LS00-74HC00]", "pi pico adc"],
        )

    def test_multi_query_skips_blank_and_stopword_only_queries(self):
        self.write("pi pico adc.md", "analog input")

        self.assertEqual(self.search_multi(["", "   ", "the for"]), [])

    def test_matches_phrase_in_filename(self):
        self.write("Pi Pico ADC.md", "# Pi Pico ADC\n\nRP2040 analog to digital converter.")

        hits = self.search("pi pico adc")

        self.assertEqual(len(hits), 1)
        hit = hits[0]
        self.assertEqual(hit.title, "Pi Pico ADC")
        self.assertEqual(hit.engine, "study_cards")
        self.assertEqual(hit.url, f"/study_cards/{quote('Pi Pico ADC.md')}")
        self.assertTrue(hit.fetched)
        self.assertIn("RP2040", hit.content)

    def test_matches_phrase_in_content(self):
        self.write("animals.md", "The quick brown fox jumps over the lazy dog.")

        hits = self.search("quick brown fox")

        self.assertEqual([hit.title for hit in hits], ["animals"])

    def test_matches_when_half_the_terms_are_in_the_name(self):
        self.write("alpha.md", "beta is described here.")

        hits = self.search("alpha beta")

        self.assertEqual([hit.title for hit in hits], ["alpha"])

    def test_matches_by_content_coverage(self):
        self.write("misc.md", "alpha beta are covered.")

        hits = self.search("alpha beta gamma")

        self.assertEqual([hit.title for hit in hits], ["misc"])

    def test_matching_is_case_insensitive(self):
        self.write("ADC Notes.md", "Analog converter.")

        hits = self.search("adc notes")

        self.assertEqual([hit.title for hit in hits], ["ADC Notes"])

    def test_phrase_in_filename_ranks_first(self):
        self.write("keyword notes.md", "unrelated body text.")
        self.write("other.md", "keyword appears in the body.")

        hits = self.search("keyword")

        self.assertEqual([hit.title for hit in hits], ["keyword notes", "other"])

    def test_limit_is_respected(self):
        for name in ("a", "b", "c"):
            self.write(f"{name}.md", "keyword here")

        self.assertEqual(len(self.search("keyword", limit=1)), 1)

    def test_subfolder_card_url_and_title(self):
        self.write("sub/Notes.md", "quick brown fox")

        hits = self.search("quick brown fox")

        self.assertEqual(hits[0].title, "Notes")
        self.assertEqual(hits[0].url, "/study_cards/sub/Notes.md")

    def test_code_fences_are_extracted(self):
        self.write("code.md", "# Code\n\n```python\nprint('hi')\n```\n")

        hits = self.search("code")

        self.assertIn("print('hi')", hits[0].code)

    def test_snippet_is_cleaned_content(self):
        self.write("pi pico adc.md", "Line one &amp; line two\nsecond line")

        hits = self.search("pi pico adc")

        self.assertEqual(hits[0].snippet, "Line one & line two second line")

    def test_no_match_returns_empty(self):
        self.write("alpha.md", "alpha beta")

        self.assertEqual(self.search("zzzqqq"), [])

    def test_empty_query_returns_empty(self):
        self.write("a.md", "content")

        self.assertEqual(self.search("   "), [])

    def test_missing_directory_returns_empty(self):
        tools.STUDY_CARDS_DIR = self.root / "does-not-exist"

        self.assertEqual(self.search("anything"), [])

    def test_skips_non_markdown_and_hidden_files(self):
        self.write("pi pico adc.txt", "pi pico adc")
        self.write(".secret/pi pico adc.md", "pi pico adc")

        self.assertEqual(self.search("pi pico adc"), [])

    def test_skips_binary_cards(self):
        self.write_bytes("pi pico adc.md", b"pi pico adc\x00\x01\x02")

        self.assertEqual(self.search("pi pico adc"), [])

    def test_skips_oversized_cards(self):
        self.write("pi pico adc.md", "pi pico adc")
        tools.STUDY_CARD_MAX_BYTES = 4

        self.assertEqual(self.search("pi pico adc"), [])

    def test_reads_cards_from_nested_folders(self):
        self.write("deep/nested/folder/pi pico adc.md", "analog input")

        hits = self.search("pi pico adc")

        self.assertEqual(hits[0].title, "pi pico adc")
        self.assertEqual(hits[0].url, "/study_cards/deep/nested/folder/pi%20pico%20adc.md")

    def test_finds_chip_card_from_natural_question(self):
        self.write(
            "7400 quad nand chip [74LS00-74HC00].md",
            "# 74x00 - 74LS00/74HC00\n"
            "## Quad NAND gate chip\n\n"
            "### Datasheets\n"
            "[**74HC00**](https://www.ti.com/lit/ds/symlink/sn74hc00.pdf)\n",
        )

        hits = self.search("what is the pin-out for the 74HC00 chip")

        self.assertEqual(
            [hit.title for hit in hits],
            ["7400 quad nand chip [74LS00-74HC00]"],
        )


if __name__ == "__main__":
    unittest.main()
