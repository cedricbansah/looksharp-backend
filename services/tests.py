import base64
from unittest.mock import Mock, patch

import pytest
import requests

from services.hubtel import send_bulk_sms, send_sms


def _mock_response(*, json_body=None, text="", status_code=200, error=None):
    response = Mock()
    response.status_code = status_code
    response.text = text
    response.json.return_value = json_body
    response.raise_for_status.side_effect = error
    return response


@patch("services.hubtel.requests.post")
def test_send_sms_normalizes_ghana_numbers_and_uses_single_send_payload(mock_post, settings):
    settings.HUBTEL_USERNAME = "hubtel-user"
    settings.HUBTEL_PASSWORD = "hubtel-pass"
    settings.HUBTEL_SENDER_ID = "LookSharp"
    mock_post.return_value = _mock_response(json_body={"messageId": "abc123"})

    result = send_sms("024 000 0000", "Hello from LookSharp")

    assert result == {"messageId": "abc123"}
    mock_post.assert_called_once_with(
        "https://sms.hubtel.com/v1/messages/send",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Basic {base64.b64encode(b'hubtel-user:hubtel-pass').decode()}",
        },
        json={
            "From": "LookSharp",
            "To": "233240000000",
            "Content": "Hello from LookSharp",
        },
        timeout=30,
    )


@patch("services.hubtel.requests.post")
def test_send_sms_accepts_existing_e164_numbers(mock_post, settings):
    settings.HUBTEL_USERNAME = "hubtel-user"
    settings.HUBTEL_PASSWORD = "hubtel-pass"
    settings.HUBTEL_SENDER_ID = "LookSharp"
    mock_post.return_value = _mock_response(json_body={"status": "ok"})

    send_sms("+233240000000", "Hello again")

    assert mock_post.call_args.kwargs["json"]["To"] == "233240000000"


@patch("services.hubtel.requests.post")
def test_send_bulk_sms_uses_batch_endpoint_and_payload(mock_post, settings):
    settings.HUBTEL_USERNAME = "hubtel-user"
    settings.HUBTEL_PASSWORD = "hubtel-pass"
    settings.HUBTEL_SENDER_ID = "LookSharp"
    mock_post.return_value = _mock_response(json_body={"status": "ok"})

    result = send_bulk_sms(["0240000000", "+233501431586"], "Bulk hello")

    assert result == {"status": "ok"}
    mock_post.assert_called_once_with(
        "https://sms.hubtel.com/v1/messages/batch/simple/send",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Basic {base64.b64encode(b'hubtel-user:hubtel-pass').decode()}",
        },
        json={
            "From": "LookSharp",
            "Recipients": ["233240000000", "233501431586"],
            "Content": "Bulk hello",
        },
        timeout=30,
    )


@patch("services.hubtel.requests.post")
def test_send_bulk_sms_chunks_large_recipient_lists(mock_post, settings):
    settings.HUBTEL_USERNAME = "hubtel-user"
    settings.HUBTEL_PASSWORD = "hubtel-pass"
    settings.HUBTEL_SENDER_ID = "LookSharp"
    mock_post.return_value = _mock_response(json_body={"status": "ok"})

    recipients = [f"23324{i:07d}" for i in range(600)]

    send_bulk_sms(recipients, "Bulk hello")

    assert mock_post.call_count == 2
    assert len(mock_post.call_args_list[0].kwargs["json"]["Recipients"]) == 500
    assert len(mock_post.call_args_list[1].kwargs["json"]["Recipients"]) == 100


@patch("services.hubtel.requests.post")
def test_send_bulk_sms_truncates_content_to_160_chars(mock_post, settings):
    settings.HUBTEL_USERNAME = "hubtel-user"
    settings.HUBTEL_PASSWORD = "hubtel-pass"
    settings.HUBTEL_SENDER_ID = "LookSharp"
    mock_post.return_value = _mock_response(json_body={"status": "ok"})

    send_bulk_sms(["0240000000"], "x" * 200)

    content = mock_post.call_args.kwargs["json"]["Content"]
    assert len(content) == 160
    assert content.endswith("...")


def test_send_sms_rejects_invalid_numbers_before_request():
    with patch("services.hubtel.requests.post") as mock_post:
        with pytest.raises(ValueError, match="international digits, E.164, or Ghana local format"):
            send_sms("abc", "Hello")

    mock_post.assert_not_called()


@patch("services.hubtel.requests.post")
def test_send_sms_includes_hubtel_error_details_in_exception(mock_post, settings):
    settings.HUBTEL_USERNAME = "hubtel-user"
    settings.HUBTEL_PASSWORD = "hubtel-pass"
    settings.HUBTEL_SENDER_ID = "LookSharp"
    response = _mock_response(
        json_body={"message": "Invalid receiver"},
        status_code=400,
        error=requests.HTTPError("400 Client Error"),
    )
    mock_post.return_value = response

    with pytest.raises(requests.HTTPError, match="Invalid receiver"):
        send_sms("0240000000", "Hello")
