from __future__ import annotations

import http.client
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from research_point_1_graph_evidence.stage02_triple_extraction.bailian_client import (  # noqa: E402
    call_chat_completion,
)


class _Response:
    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(
            {
                "id": "request-test",
                "model": "qwen3.7-max",
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "content": json.dumps(
                                {"triples": [], "warnings": []}
                            )
                        },
                    }
                ],
                "usage": {},
            }
        ).encode("utf-8")


class BailianClientTests(unittest.TestCase):
    @patch(
        "research_point_1_graph_evidence.stage02_triple_extraction."
        "bailian_client.time.sleep",
        return_value=None,
    )
    @patch(
        "research_point_1_graph_evidence.stage02_triple_extraction."
        "bailian_client.urllib.request.urlopen"
    )
    def test_remote_disconnect_is_retried(
        self,
        mocked_urlopen,
        _mocked_sleep,
    ) -> None:
        mocked_urlopen.side_effect = [
            http.client.RemoteDisconnected("closed"),
            _Response(),
        ]
        retries: list[tuple[int, int]] = []
        result = call_chat_completion(
            api_key="test-key",
            base_url="https://example.test/v1",
            model="qwen3.7-max",
            system_prompt="system",
            user_prompt="user",
            temperature=0,
            enable_thinking=False,
            response_format={"type": "json_object"},
            timeout_seconds=10,
            max_retries=3,
            retry_callback=lambda attempt, maximum, _reason, _wait: retries.append(
                (attempt, maximum)
            ),
        )
        self.assertEqual(result.request_id, "request-test")
        self.assertEqual(result.attempt, 2)
        self.assertEqual(retries, [(1, 3)])


if __name__ == "__main__":
    unittest.main()
