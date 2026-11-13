from __future__ import annotations

import os
import threading
import time
import unittest

import download_and_check_model
import tools
from agent import Agent


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
        self.assertEqual(agent.get_health(), "inactive")

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
        self.assertIn("7400 quad nand chip [74LS00-74HC00]", titles)
        self.assertEqual(result["sources"][0]["engine"], "study_cards")

    def test_no_card_match_is_reported_as_done(self):
        agent = Agent()
        self.addCleanup(agent.close)

        result = agent.run("flurble wibble")

        step = next(step for step in result["steps"] if step["label"] == "study cards check")
        self.assertEqual(step["status"], "done")
        self.assertIn("No cards matched", step["detail"])

        tool = next(tool for tool in result["tools"] if tool["name"] == "study_cards")
        self.assertEqual(tool["status"], "done")

        self.assertIn("answer Composing", [step["label"] for step in result["steps"]])

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


class StudyCardSearchTests(unittest.TestCase):
    def test_natural_question_finds_chip_card(self):
        hits = tools.search_study_cards("what is the pin-out for the 74HC00 chip")

        self.assertIn(
            "7400 quad nand chip [74LS00-74HC00]",
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
