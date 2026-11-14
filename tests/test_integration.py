from __future__ import annotations

import json
import os
import threading
import time
import unittest

import download_and_check_model
import tools
from agent import Agent, _context_block


def server_is_running() -> bool:
    return Agent().server_available()


requires_server = unittest.skipUnless(
    server_is_running(),
    "llama.cpp server is not running (start it with ./run.sh)",
)


def setUpModule():
    os.environ.setdefault("N_CTX", "2048")
    os.environ.setdefault("MAX_TOKENS", "64")


class ModelFileTests(unittest.TestCase):
    def test_model_is_ready(self):
        self.assertTrue(download_and_check_model.model_ready())

    def test_ensure_model_returns_existing_file(self):
        path = download_and_check_model.ensure_model()
        self.assertTrue(path.is_file())


@requires_server
class AgentTests(unittest.TestCase):
    def test_generates_answer_and_transitions_health(self):
        agent = Agent()
        self.addCleanup(agent.close)
        expected = "ready" if agent.server_available() else "inactive"
        self.assertEqual(agent.get_health(), expected)

        result = agent.run("hello there friend")

        self.assertFalse(result["llm_failed"], result["answer"])
        self.assertTrue(result["answer"].strip())
        self.assertEqual(result["model"], agent.model_name)
        self.assertEqual(agent.get_health(), "ready")

        agent.close()
        self.assertEqual(agent.get_health(), "inactive")

    def test_study_card_match_uses_model_keywords(self):
        agent = Agent()
        self.addCleanup(agent.close)

        result = agent.run("pi pico ADC")

        self.assertTrue(result["sources"])
        self.assertEqual(result["sources"][0]["engine"], "study_cards")
        self.assertIn("search_keywords", [tool["name"] for tool in result["tools"]])
        self.assertTrue(agent.server_available())

    def test_extract_keywords_returns_tool_call(self):
        agent = Agent()
        self.addCleanup(agent.close)

        tool_call = agent.extract_keywords("what is the pin-out for the 74HC00 chip")

        self.assertIsNotNone(tool_call)
        self.assertEqual(tool_call["function"]["name"], "search_keywords")
        self.assertTrue(agent._keywords_from_tool_call(tool_call))

    def test_chip_question_finds_card_via_keywords(self):
        agent = Agent()
        self.addCleanup(agent.close)

        result = agent.run("what is the pin-out for the 74HC00 chip")

        titles = [source["title"] for source in result["sources"]]
        self.assertIn("7400 Quad Nand Chip [74LS00-74HC00]", titles)
        self.assertEqual(result["sources"][0]["engine"], "study_cards")

    def test_no_card_match_is_reported_as_done(self):
        agent = Agent()
        self.addCleanup(agent.close)

        result = agent.run("flurble wibble")

        step = next(step for step in result["steps"] if step["label"] == "Study Cards Check")
        self.assertEqual(step["status"], "done")
        self.assertIn("No cards matched", step["detail"])

        tool = next(tool for tool in result["tools"] if tool["name"] == "study_cards")
        self.assertEqual(tool["status"], "done")

        self.assertIn("Composing answer", [step["label"] for step in result["steps"]])

    def test_stop_cancels_generation(self):
        agent = Agent()
        self.addCleanup(agent.close)
        previous = os.environ.get("MAX_TOKENS")
        os.environ["MAX_TOKENS"] = "512"

        def restore_max_tokens():
            if previous is None:
                os.environ.pop("MAX_TOKENS", None)
            else:
                os.environ["MAX_TOKENS"] = previous

        self.addCleanup(restore_max_tokens)

        outcome = {}
        thread = threading.Thread(
            target=lambda: outcome.update(agent.run("flurble wibble"))
        )
        thread.start()

        deadline = time.monotonic() + 120
        while time.monotonic() < deadline and agent.get_health() != "loading response":
            time.sleep(0.1)

        agent.close()
        thread.join(timeout=120)

        self.assertFalse(thread.is_alive())
        self.assertTrue(outcome.get("stopped"))
        self.assertEqual(agent.get_health(), "inactive")
        self.assertTrue(agent.server_available())


class KeywordToolCallTests(unittest.TestCase):
    def test_parses_and_cleans_keywords(self):
        tool_call = {
            "function": {
                "arguments": '{"keywords": ["74HC00 pin-out", "c", "74HC00 pin-out", ""]}'
            }
        }

        self.assertEqual(Agent._keywords_from_tool_call(tool_call), ["74HC00 pin-out"])

    def test_bad_arguments_yield_no_keywords(self):
        self.assertEqual(Agent._keywords_from_tool_call({"function": {"arguments": "nope"}}), [])
        self.assertEqual(Agent._keywords_from_tool_call({"function": {}}), [])
        self.assertEqual(
            Agent._keywords_from_tool_call({"function": {"arguments": '{"keywords": "x"}'}}),
            [],
        )

    def test_strips_tool_markup_and_prose(self):
        tool_call = {
            "function": {
                "arguments": (
                    '{"keywords": ['
                    '"</param></function>> I need more context from the user",'
                    '"electric Ferrari", "Ferrari EV specs"]}'
                    "</param></function>"
                )
            }
        }

        self.assertEqual(
            Agent._keywords_from_tool_call(tool_call),
            ["electric Ferrari", "Ferrari EV specs"],
        )

    def test_recovers_keywords_from_wrapped_arguments(self):
        tool_call = {
            "function": {
                "arguments": '> "keywords": ["electric Ferrari"]</function>'
            }
        }

        self.assertEqual(Agent._keywords_from_tool_call(tool_call), ["electric Ferrari"])


class SourceSummaryTests(unittest.TestCase):
    def test_summary_is_cleaned_and_clamped(self):
        summary = Agent._clean_summary(
            "1. </param>Ferrari Luce makes 1,035 hp</function>", 200
        )
        self.assertEqual(summary, "Ferrari Luce makes 1,035 hp")

        long = Agent._clean_summary("x" * 300, 200)
        self.assertEqual(len(long), 200)
        self.assertTrue(long.endswith("…"))

    def test_context_block_uses_summaries(self):
        hit = tools.SearchHit(
            title="Ferrari Luce",
            url="https://example.com/luce",
            snippet="short",
            engine="duckduckgo",
            content="C" * 3000,
        )

        block = _context_block([hit], ["Luce: 1,035 hp, 122 kWh battery."])

        self.assertIn("Summary: Luce: 1,035 hp, 122 kWh battery.", block)
        self.assertNotIn("Excerpt:", block)

    def test_context_block_falls_back_to_excerpt(self):
        hit = tools.SearchHit(
            title="Ferrari Luce",
            url="https://example.com/luce",
            snippet="short",
            engine="duckduckgo",
            content="C" * 3000,
        )

        block = _context_block([hit])

        self.assertIn("Excerpt: ", block)
        self.assertNotIn("C" * 1401, block)
        self.assertIn("C" * 1400, block)


class CardRelevanceTests(unittest.TestCase):
    def test_tool_call_booleans(self):
        cases = [
            (True, True),
            (False, False),
            ("true", True),
            ("false", False),
            ("yes", True),
            ("no", False),
            ("maybe", None),
        ]
        for value, expected in cases:
            tool_call = {"function": {"arguments": json.dumps({"relevant": value})}}
            self.assertIs(
                Agent._relevance_from_tool_call(tool_call),
                expected,
                f"relevant={value!r}",
            )

    def test_accepts_alternate_argument_names(self):
        tool_call = {"function": {"arguments": '{"answers_question": false}'}}
        self.assertIs(Agent._relevance_from_tool_call(tool_call), False)

    def test_plain_text_fallback(self):
        self.assertIs(Agent._relevance_from_text('{"relevant": false}'), False)
        self.assertIs(Agent._relevance_from_text("relevant: no"), False)
        self.assertIs(Agent._relevance_from_text("This is irrelevant to the question."), None)

    def test_false_removes_card_from_matches(self):
        agent = Agent()
        cards = [
            tools.SearchHit(title="A", url="/a", snippet="", engine="study_cards"),
            tools.SearchHit(title="B", url="/b", snippet="", engine="study_cards"),
        ]
        agent.check_card_relevance = lambda message, hit: hit.title != "A"

        kept, rejected = agent._filter_relevant_cards("q", cards)

        self.assertEqual([hit.title for hit in kept], ["B"])
        self.assertEqual([hit.title for hit in rejected], ["A"])

    def test_all_rejected_empties_matches(self):
        agent = Agent()
        cards = [
            tools.SearchHit(title="A", url="/a", snippet="", engine="study_cards"),
            tools.SearchHit(title="B", url="/b", snippet="", engine="study_cards"),
        ]
        agent.check_card_relevance = lambda message, hit: False

        kept, rejected = agent._filter_relevant_cards("q", cards)

        self.assertEqual(kept, [])
        self.assertEqual(len(rejected), 2)

    def test_unknown_relevance_keeps_card(self):
        agent = Agent()
        cards = [
            tools.SearchHit(title="A", url="/a", snippet="", engine="study_cards"),
        ]
        agent.check_card_relevance = lambda message, hit: None

        kept, rejected = agent._filter_relevant_cards("q", cards)

        self.assertEqual([hit.title for hit in kept], ["A"])
        self.assertEqual(rejected, [])


class CardRelevanceModelTests(unittest.TestCase):
    """How well the model keeps useful cards and drops the rest.

    Each case is (question, real study card, expected relevance). A case only
    checks the relevance decision, not the final answer.
    """

    CASES = [
        # Cards that do answer the question.
        ("pi pico ADC", "Pi Pico SDK/Pi Pico ADC Example.md", True),
        ("what is the maximum ADC value on the pi pico?", "Pi Pico SDK/Pi Pico ADC Example.md", True),
        ("how do I use a for loop in C?", "C Programing Language/Loops in the C Language.md", True),
        ("what is the pinout for the pi pico?", "Pi Pico Pinout/Raspberry Pi Pico Pin-out.md", True),
        (
            "what does the 74HC00 chip do?",
            "7400 Series Chips/7400 Quad Nand Chip [74LS00-74HC00].md",
            True,
        ),
        # Cards that share keywords but do not answer the question.
        ("what is the pinout for the pi pico?", "Pi Pico SDK/Pi Pico ADC Example.md", False),
        (
            "what is the pin-out for the 74HC00 chip?",
            "Pi Pico SDK/Pi Pico ADC Example.md",
            False,
        ),
        (
            "what is the pinout for the pi pico?",
            "C Programing Language/Loops in the C Language.md",
            False,
        ),
        ("what is the pinout for the pi pico?", "Sample Card Folder/Sample Card.md", False),
        ("how do I use a for loop in C?", "Pi Pico SDK/Pi Pico ADC Example.md", False),
        (
            "how do I use a for loop in C?",
            "7400 Series Chips/7400 Quad Nand Chip [74LS00-74HC00].md",
            False,
        ),
    ]

    def _card(self, relative) -> tools.SearchHit:
        path = tools.STUDY_CARDS_DIR / relative
        content = path.read_text(encoding="utf-8")
        return tools.SearchHit(
            title=path.stem,
            url="",
            snippet="",
            engine="study_cards",
            content=content,
        )

    def test_relevance_decisions_on_real_cards(self):
        agent = Agent()
        self.addCleanup(agent.close)

        results = []
        for question, relative, expected in self.CASES:
            card = self._card(relative)
            actual = agent.check_card_relevance(question, card)
            results.append((question, card.title, expected, actual))

        correct = sum(1 for _, _, expected, actual in results if actual is expected)
        print(f"\ncard relevance: {correct}/{len(results)} correct")
        for question, title, expected, actual in results:
            mark = "ok " if actual is expected else "BAD"
            print(
                f"  {mark} expected={expected!s:5} got={actual!s:5} | "
                f"{question!r} + {title}"
            )

        for question, title, expected, actual in results:
            with self.subTest(question=question, card=title):
                self.assertIs(actual, expected)


class StudyCardSearchTests(unittest.TestCase):
    def test_natural_question_finds_chip_card(self):
        hits = tools.search_study_cards("what is the pin-out for the 74HC00 chip")

        self.assertIn(
            "7400 Quad Nand Chip [74LS00-74HC00]",
            [hit.title for hit in hits],
        )


class AppTests(unittest.TestCase):
    def setUp(self):
        import app as app_module

        self.app_module = app_module
        self.client = app_module.app.test_client()

    def tearDown(self):
        self.app_module.agent.close()

    def test_index_renders_trace_time(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn('id="traceTime"', response.get_data(as_text=True))

    def test_index_renders_image_lightbox(self):
        html = self.client.get("/").get_data(as_text=True)
        self.assertIn('id="lightboxOverlay"', html)
        self.assertIn('id="lightboxImage"', html)

    def test_health_reports_inactive_before_use(self):
        self.client.post("/api/stop")
        body = self.client.get("/api/health").get_json()
        self.assertEqual(body["status"], "inactive")
        self.assertFalse(body["loading"])

    @requires_server
    def test_chat_round_trip_then_stop(self):
        response = self.client.post("/api/chat", json={"message": "hello there friend"})
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertFalse(body["llm_failed"], body["answer"])
        self.assertTrue(body["answer"].strip())

        self.assertEqual(self.client.get("/api/health").get_json()["status"], "ready")

        stop = self.client.post("/api/stop")
        self.assertEqual(stop.status_code, 200)
        self.assertEqual(self.client.get("/api/health").get_json()["status"], "inactive")

    def test_chat_rejects_empty_message(self):
        response = self.client.post("/api/chat", json={"message": "   "})
        self.assertEqual(response.status_code, 400)

    def test_config_lists_groups(self):
        body = self.client.get("/api/config").get_json()
        self.assertEqual(len(body["groups"]), 3)

    def test_study_cards_are_listed(self):
        body = self.client.get("/api/study-cards").get_json()
        self.assertTrue(body["cards"])
        self.assertIn("Pi Pico SDK", body["folders"])


if __name__ == "__main__":
    unittest.main()
