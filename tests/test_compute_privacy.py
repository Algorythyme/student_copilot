import unittest

from privacy_utils import (
    WebSearchRequiredError,
    public_chat_result,
    run_required_web_search,
    sanitize_public_reply,
    sanitize_web_results,
)


class ComputePrivacyTests(unittest.IsolatedAsyncioTestCase):
    def test_public_reply_removes_markdown_and_raw_urls(self):
        reply = (
            "Read [this source](https://example.com/a).\n"
            "Sources: Private publisher\n- https://private.example/item"
        )

        cleaned = sanitize_public_reply(reply)

        self.assertEqual(cleaned, "Read this source.")
        self.assertNotIn("http", cleaned)

    def test_search_results_drop_urls_and_source_titles(self):
        cleaned = sanitize_web_results(
            {
                "results": [
                    {
                        "title": "Private publisher",
                        "url": "https://example.com/a",
                        "content": "A fact from https://example.com/a",
                    }
                ]
            }
        )

        self.assertEqual(
            cleaned,
            [{"label": "Web result 1", "content": "A fact from"}],
        )

    async def test_required_search_uses_sanitized_minimal_query(self):
        queries = []

        async def search(query):
            queries.append(query)
            return [{"label": "Web result 1", "content": "A safe fact"}]

        context, used = await run_required_web_search(
            {
                "input": "What is photosynthesis? email me at child@example.com",
                "has_private_context": False,
            },
            True,
            search,
        )

        self.assertTrue(used)
        self.assertNotIn("child@example.com", queries[0])
        self.assertIn("Web result 1", context)

    async def test_required_search_failure_is_controlled(self):
        async def fail(_query):
            raise RuntimeError("provider URL and secret details")

        with self.assertRaisesRegex(
            WebSearchRequiredError,
            "Required web search failed",
        ):
            await run_required_web_search(
                {
                    "input": "Who is the current president?",
                    "has_private_context": False,
                },
                True,
                fail,
            )

    async def test_required_search_rejects_empty_results(self):
        async def empty(_query):
            return []

        with self.assertRaisesRegex(
            WebSearchRequiredError,
            "no usable results",
        ):
            await run_required_web_search(
                {"input": "What happened today?", "has_private_context": False},
                True,
                empty,
            )

    async def test_private_context_is_never_sent_to_search(self):
        called = False

        async def search(_query):
            nonlocal called
            called = True
            return [{"content": "unused"}]

        context, used = await run_required_web_search(
            {
                "input": "Explain this private class note",
                "has_private_context": True,
            },
            True,
            search,
        )

        self.assertEqual(context, "")
        self.assertFalse(used)
        self.assertFalse(called)

    def test_compute_chat_never_returns_sources_or_urls(self):
        result = public_chat_result(
            {
                "output": "Answer https://private.example/source",
                "sources": ["https://private.example/source"],
                "search_used": True,
            }
        )

        self.assertNotIn("sources", result)
        self.assertNotIn("http", result["reply"])
        self.assertTrue(result["search_used"])


if __name__ == "__main__":
    unittest.main()
