from __future__ import annotations

import json
import logging

from app.core.logging import EXTRA_FIELDS, JsonFormatter


def test_extra_fields_are_strings() -> None:
    assert EXTRA_FIELDS
    assert all(isinstance(field, str) for field in EXTRA_FIELDS)


def test_json_formatter_includes_structured_extra_fields() -> None:
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello %s",
        args=("world",),
        exc_info=None,
    )
    record.request_id = "request-123"
    record.status_code = 200

    payload = json.loads(JsonFormatter().format(record))

    assert payload["message"] == "hello world"
    assert payload["request_id"] == "request-123"
    assert payload["status_code"] == 200
