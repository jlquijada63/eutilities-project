import os
import unittest
from unittest.mock import AsyncMock, patch

import async_eutilities as mod


class TestConfig(unittest.TestCase):
    def setUp(self) -> None:
        self.original = mod.get_config()

    def tearDown(self) -> None:
        mod.configure(
            api_key=self.original.get("api_key"),
            email=self.original.get("email"),
            tool=self.original.get("tool"),
            base_url=self.original.get("base_url", mod.BASE_URL),
            timeout=self.original.get("timeout", 30.0),
            max_retries=self.original.get("max_retries", 2),
            retry_backoff=self.original.get("retry_backoff", 0.5),
        )

    def test_configure_and_get_config(self) -> None:
        mod.configure(
            api_key="k1",
            email="test@example.com",
            tool="tool-test",
            base_url="https://example.org/eutils",
            timeout=12.0,
            max_retries=3,
            retry_backoff=0.25,
        )
        cfg = mod.get_config()
        self.assertEqual(cfg["api_key"], "k1")
        self.assertEqual(cfg["email"], "test@example.com")
        self.assertEqual(cfg["tool"], "tool-test")
        self.assertEqual(cfg["base_url"], "https://example.org/eutils")
        self.assertEqual(cfg["timeout"], 12.0)
        self.assertEqual(cfg["max_retries"], 3)
        self.assertEqual(cfg["retry_backoff"], 0.25)

    def test_reset_config_defaults(self) -> None:
        mod.configure(api_key="temp", timeout=10.0, max_retries=4, retry_backoff=1.0)
        mod.reset_config()
        cfg = mod.get_config()

        self.assertEqual(cfg["base_url"], mod.BASE_URL)
        self.assertEqual(cfg["timeout"], 30.0)
        self.assertEqual(cfg["max_retries"], 2)
        self.assertEqual(cfg["retry_backoff"], 0.5)
        self.assertEqual(cfg["api_key"], os.getenv("NCBI_API_KEY"))


class TestValidations(unittest.IsolatedAsyncioTestCase):
    async def test_esearch_empty_term_raises(self) -> None:
        with self.assertRaises(ValueError):
            await mod.esearch("")

    async def test_einfo_empty_db_raises(self) -> None:
        with self.assertRaises(ValueError):
            await mod.einfo("")

    async def test_epost_empty_ids_raises(self) -> None:
        with self.assertRaises(ValueError):
            await mod.epost("   ")

    async def test_ecitmatch_empty_bdata_raises(self) -> None:
        with self.assertRaises(ValueError):
            await mod.ecitmatch("")


class TestDelegation(unittest.IsolatedAsyncioTestCase):
    async def test_esearch_calls_request(self) -> None:
        with patch("async_eutilities._request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = "ok"
            result = await mod.esearch("asthma", db="pubmed")

            self.assertEqual(result, "ok")
            mock_request.assert_awaited_once()
            self.assertEqual(mock_request.await_args.args[0], "esearch.fcgi")
            self.assertEqual(mock_request.await_args.kwargs["params"], {"db": "pubmed", "term": "asthma"})

    async def test_esearch_hip_replacement_term(self) -> None:
        with patch("async_eutilities._request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = "ok"
            result = await mod.esearch("hip replacement")

            self.assertEqual(result, "ok")
            self.assertEqual(mock_request.await_args.args[0], "esearch.fcgi")
            self.assertEqual(
                mock_request.await_args.kwargs["params"],
                {"db": "pubmed", "term": "hip replacement"},
            )

    async def test_efetch_normalizes_ids(self) -> None:
        with patch("async_eutilities._request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = "ok"
            await mod.efetch(ids=[1, "2", 3], db="pubmed")

            self.assertEqual(mock_request.await_args.args[0], "efetch.fcgi")
            self.assertEqual(mock_request.await_args.kwargs["params"], {"db": "pubmed", "id": "1,2,3"})

    async def test_esummary_accepts_history_options(self) -> None:
        with patch("async_eutilities._request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = "ok"
            await mod.esummary(options={"query_key": 1, "WebEnv": "abc"})

            self.assertEqual(mock_request.await_args.args[0], "esummary.fcgi")
            self.assertEqual(mock_request.await_args.kwargs["params"], {"db": "pubmed"})
            self.assertEqual(mock_request.await_args.kwargs["options"], {"query_key": 1, "WebEnv": "abc"})

    async def test_ecitmatch_sets_default_rettype(self) -> None:
        with patch("async_eutilities._request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = "ok"
            await mod.ecitmatch("proc natl acad sci u s a|1991|88|7|3248|mann bj|")

            self.assertEqual(mock_request.await_args.args[0], "ecitmatch.cgi")
            self.assertEqual(
                mock_request.await_args.kwargs["params"],
                {
                    "db": "pubmed",
                    "bdata": "proc natl acad sci u s a|1991|88|7|3248|mann bj|",
                },
            )
            self.assertEqual(mock_request.await_args.kwargs["options"], {"rettype": "xml"})


if __name__ == "__main__":
    unittest.main()
