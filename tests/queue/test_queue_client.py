import json
import re
import uuid
from datetime import UTC, datetime

import httpx2
import pytest
import respx

from refractometer_common.queue import (
    QueueClient,
    QueueClientConnectionException,
    QueueClientElementNotFoundException,
    QueueClientException,
    QueueClientInterface,
    QueueClientInvalidResponseException,
    QueueClientTimeoutException,
    SimulationQueueElement,
    SimulationQueueElementCreate,
)

BASE_URL = "http://queue-service"

ELEMENT_ID = "3fa85f64-5717-4562-b3fc-2c963f66afa6"
OTHER_ELEMENT_ID = "9b2d4c1e-8f3a-4e7b-a6d5-1c0e2f3a4b5c"

QUEUE_RESPONSE = {
    "parameters": {"foo": "bar"},
    "index": 0,
    "being_processed": False,
    "issuer": "test",
    "callback_url": "http://callback",
    "id": ELEMENT_ID,
    "name": "test-simulation",
    "issued_at": "2026-09-18T10:00:00Z",
}

NOT_FOUND_RESPONSE = {"detail": "Queue element not found"}
EMPTY_QUEUE_RESPONSE = {"detail": "No queued simulations available"}


@pytest.fixture
def client() -> QueueClient:
    return QueueClient(BASE_URL)


@pytest.fixture
def create_request() -> SimulationQueueElementCreate:
    return SimulationQueueElementCreate(
        parameters={"foo": "bar"},
        issuer="test",
        callback_url="http://callback",
        name="test-simulation",
    )


def test_claim_element(client: QueueClient, httpx2_mock: respx.Router):
    route = httpx2_mock.get(f"{BASE_URL}/api/queue/claim").respond(
        status_code=200, json=QUEUE_RESPONSE
    )

    result = client.claim_element()

    assert route.called
    assert isinstance(result, SimulationQueueElement)
    assert result.id == uuid.UUID(ELEMENT_ID)
    assert result.parameters == {"foo": "bar"}
    assert result.issuer == "test"
    assert result.callback_url == "http://callback"
    assert result.name == "test-simulation"
    assert result.index == 0
    assert result.being_processed is False
    assert result.issued_at == datetime(2026, 9, 18, 10, 0, tzinfo=UTC)


def test_claim_element_without_optional_fields(client: QueueClient, httpx2_mock: respx.Router):
    httpx2_mock.get(f"{BASE_URL}/api/queue/claim").respond(
        status_code=200,
        json={"id": ELEMENT_ID, "parameters": {}, "issued_at": "2026-09-18T10:00:00Z"},
    )

    result = client.claim_element()

    assert result.name is None
    assert result.issuer is None
    assert result.callback_url is None


def test_claim_element_empty_queue(client: QueueClient, httpx2_mock: respx.Router):
    httpx2_mock.get(f"{BASE_URL}/api/queue/claim").respond(
        status_code=404, json=EMPTY_QUEUE_RESPONSE
    )

    with pytest.raises(
        QueueClientElementNotFoundException, match="No queued simulations available"
    ) as exc_info:
        client.claim_element()

    assert exc_info.value.status_code == 404


@pytest.mark.parametrize("status_code", [400, 401, 403, 500, 502, 503])
def test_claim_element_http_error(client: QueueClient, status_code: int, httpx2_mock: respx.Router):
    httpx2_mock.get(f"{BASE_URL}/api/queue/claim").respond(
        status_code=status_code, text="Something went wrong"
    )

    with pytest.raises(
        QueueClientException, match=f"returned {status_code}: Something went wrong"
    ) as exc_info:
        client.claim_element()

    assert not isinstance(exc_info.value, QueueClientElementNotFoundException)
    assert exc_info.value.status_code == status_code


def test_claim_element_extracts_detail(client: QueueClient, httpx2_mock: respx.Router):
    httpx2_mock.get(f"{BASE_URL}/api/queue/claim").respond(
        status_code=500, json={"detail": "database unavailable"}
    )

    with pytest.raises(QueueClientException, match="returned 500: database unavailable"):
        client.claim_element()


def test_claim_element_invalid_json(client: QueueClient, httpx2_mock: respx.Router):
    httpx2_mock.get(f"{BASE_URL}/api/queue/claim").respond(
        status_code=200, text="<html>nope</html>"
    )

    with pytest.raises(QueueClientInvalidResponseException, match="not valid JSON") as exc_info:
        client.claim_element()

    assert exc_info.value.status_code == 200


def test_claim_element_unprocessable(client: QueueClient, httpx2_mock: respx.Router):
    httpx2_mock.get(f"{BASE_URL}/api/queue/claim").respond(
        status_code=200, json={"not": "serializable"}
    )

    with pytest.raises(QueueClientInvalidResponseException, match="Validation error"):
        client.claim_element()


@pytest.mark.parametrize(
    "body",
    [
        {**QUEUE_RESPONSE, "id": "not-a-uuid"},
        {**QUEUE_RESPONSE, "id": None},
        {k: v for k, v in QUEUE_RESPONSE.items() if k != "id"},
    ],
    ids=["invalid_uuid", "null_id", "missing_id"],
)
def test_claim_element_invalid_id_in_response(
    client: QueueClient, body: dict, httpx2_mock: respx.Router
):
    httpx2_mock.get(f"{BASE_URL}/api/queue/claim").respond(status_code=200, json=body)

    with pytest.raises(QueueClientInvalidResponseException):
        client.claim_element()


def test_get_queued_simulations(client: QueueClient, httpx2_mock: respx.Router):
    httpx2_mock.get(f"{BASE_URL}/api/queued").respond(
        status_code=200,
        json=[QUEUE_RESPONSE, {**QUEUE_RESPONSE, "id": OTHER_ELEMENT_ID, "index": 1}],
    )

    result = client.get_queued_simulations()

    assert [element.id for element in result] == [
        uuid.UUID(ELEMENT_ID),
        uuid.UUID(OTHER_ELEMENT_ID),
    ]
    assert [element.index for element in result] == [0, 1]


def test_get_queued_simulations_empty(client: QueueClient, httpx2_mock: respx.Router):
    httpx2_mock.get(f"{BASE_URL}/api/queued").respond(status_code=200, json=[])

    assert client.get_queued_simulations() == []


@pytest.mark.parametrize("status_code", [400, 401, 403, 500, 502, 503])
def test_get_queued_simulations_http_error(
    client: QueueClient, status_code: int, httpx2_mock: respx.Router
):
    httpx2_mock.get(f"{BASE_URL}/api/queued").respond(
        status_code=status_code, text="Something went wrong"
    )

    with pytest.raises(QueueClientException) as exc_info:
        client.get_queued_simulations()

    assert exc_info.value.status_code == status_code


def test_get_queued_simulations_invalid_json(client: QueueClient, httpx2_mock: respx.Router):
    httpx2_mock.get(f"{BASE_URL}/api/queued").respond(status_code=200, text="<html>nope</html>")

    with pytest.raises(QueueClientInvalidResponseException, match="not valid JSON"):
        client.get_queued_simulations()


def test_get_queued_simulations_not_a_list(client: QueueClient, httpx2_mock: respx.Router):
    httpx2_mock.get(f"{BASE_URL}/api/queued").respond(status_code=200, json=QUEUE_RESPONSE)

    with pytest.raises(QueueClientInvalidResponseException, match="Expected a list"):
        client.get_queued_simulations()


def test_get_queued_simulations_unprocessable_element(
    client: QueueClient, httpx2_mock: respx.Router
):
    httpx2_mock.get(f"{BASE_URL}/api/queued").respond(
        status_code=200, json=[QUEUE_RESPONSE, {"not": "serializable"}]
    )

    with pytest.raises(QueueClientInvalidResponseException, match="Validation error"):
        client.get_queued_simulations()


def test_get_queued_simulation(client: QueueClient, httpx2_mock: respx.Router):
    route = httpx2_mock.get(f"{BASE_URL}/api/queue/{ELEMENT_ID}").respond(
        status_code=200, json=QUEUE_RESPONSE
    )

    result = client.get_queued_simulation(ELEMENT_ID)

    assert route.called
    assert result.id == uuid.UUID(ELEMENT_ID)
    assert result.name == "test-simulation"


def test_get_queued_simulation_accepts_uuid(client: QueueClient, httpx2_mock: respx.Router):
    route = httpx2_mock.get(f"{BASE_URL}/api/queue/{ELEMENT_ID}").respond(
        status_code=200, json=QUEUE_RESPONSE
    )

    client.get_queued_simulation(uuid.UUID(ELEMENT_ID))

    assert route.called


def test_get_queued_simulation_not_found(client: QueueClient, httpx2_mock: respx.Router):
    httpx2_mock.get(f"{BASE_URL}/api/queue/{ELEMENT_ID}").respond(
        status_code=404, json=NOT_FOUND_RESPONSE
    )

    with pytest.raises(
        QueueClientElementNotFoundException, match=f"Queue element '{ELEMENT_ID}' not found"
    ) as exc_info:
        client.get_queued_simulation(ELEMENT_ID)

    assert exc_info.value.status_code == 404


def test_get_queued_simulation_not_found_is_client_exception(
    client: QueueClient, httpx2_mock: respx.Router
):
    httpx2_mock.get(f"{BASE_URL}/api/queue/{ELEMENT_ID}").respond(
        status_code=404, json=NOT_FOUND_RESPONSE
    )

    with pytest.raises(QueueClientException):
        client.get_queued_simulation(ELEMENT_ID)


def test_get_queued_simulation_http_error(client: QueueClient, httpx2_mock: respx.Router):
    httpx2_mock.get(f"{BASE_URL}/api/queue/{ELEMENT_ID}").respond(
        status_code=500, text="Internal server error"
    )

    with pytest.raises(QueueClientException, match="returned 500: Internal server error") as (
        exc_info
    ):
        client.get_queued_simulation(ELEMENT_ID)

    assert not isinstance(exc_info.value, QueueClientElementNotFoundException)
    assert exc_info.value.status_code == 500


def test_get_queued_simulation_unprocessable(client: QueueClient, httpx2_mock: respx.Router):
    httpx2_mock.get(f"{BASE_URL}/api/queue/{ELEMENT_ID}").respond(
        status_code=200, json={"not": "serializable"}
    )

    with pytest.raises(QueueClientInvalidResponseException, match="Validation error"):
        client.get_queued_simulation(ELEMENT_ID)


@pytest.mark.parametrize("status_code", [200, 201])
def test_post_queued_simulation(
    client: QueueClient,
    create_request: SimulationQueueElementCreate,
    status_code: int,
    httpx2_mock: respx.Router,
):
    httpx2_mock.post(f"{BASE_URL}/api/queue").respond(
        status_code=status_code, json={"id": ELEMENT_ID}
    )

    assert client.post_queued_simulation(create_request) == ELEMENT_ID


def test_post_queued_simulation_sends_expected_body(
    client: QueueClient,
    create_request: SimulationQueueElementCreate,
    httpx2_mock: respx.Router,
):
    route = httpx2_mock.post(f"{BASE_URL}/api/queue").respond(
        status_code=201, json={"id": ELEMENT_ID}
    )

    client.post_queued_simulation(create_request)

    body = json.loads(route.calls.last.request.content)
    assert body == {
        "parameters": {"foo": "bar"},
        "issuer": "test",
        "callback_url": "http://callback",
        "name": "test-simulation",
    }


def test_post_queued_simulation_minimal_request(client: QueueClient, httpx2_mock: respx.Router):
    route = httpx2_mock.post(f"{BASE_URL}/api/queue").respond(
        status_code=201, json={"id": ELEMENT_ID}
    )

    client.post_queued_simulation(SimulationQueueElementCreate(parameters={"a": 1}))

    body = json.loads(route.calls.last.request.content)
    assert body == {"parameters": {"a": 1}, "issuer": None, "callback_url": None, "name": None}


def test_post_queued_simulation_http_error(
    client: QueueClient,
    create_request: SimulationQueueElementCreate,
    httpx2_mock: respx.Router,
):
    httpx2_mock.post(f"{BASE_URL}/api/queue").respond(
        status_code=422, json={"detail": "parameters: field required"}
    )

    with pytest.raises(QueueClientException, match="returned 422: parameters") as exc_info:
        client.post_queued_simulation(create_request)

    assert exc_info.value.status_code == 422


def test_post_queued_simulation_invalid_json(
    client: QueueClient,
    create_request: SimulationQueueElementCreate,
    httpx2_mock: respx.Router,
):
    httpx2_mock.post(f"{BASE_URL}/api/queue").respond(status_code=201, text="created")

    with pytest.raises(QueueClientInvalidResponseException, match="not valid JSON"):
        client.post_queued_simulation(create_request)


@pytest.mark.parametrize(
    "body",
    [{}, {"id": None}, {"id": 123}, [ELEMENT_ID]],
    ids=["missing_id", "null_id", "non_string_id", "not_an_object"],
)
def test_post_queued_simulation_unprocessable_response(
    client: QueueClient,
    create_request: SimulationQueueElementCreate,
    body,
    httpx2_mock: respx.Router,
):
    httpx2_mock.post(f"{BASE_URL}/api/queue").respond(status_code=201, json=body)

    with pytest.raises(QueueClientInvalidResponseException) as exc_info:
        client.post_queued_simulation(create_request)

    assert exc_info.value.status_code == 201


def test_update_queued_simulation(client: QueueClient, httpx2_mock: respx.Router):
    updated = {**QUEUE_RESPONSE, "parameters": {"updated": True}, "name": "renamed"}
    route = httpx2_mock.patch(f"{BASE_URL}/api/queue/{ELEMENT_ID}").respond(
        status_code=200, json=updated
    )

    result = client.update_queued_simulation(
        ELEMENT_ID, {"updated": True}, issuer="test", name="renamed"
    )

    assert route.called
    assert result.parameters == {"updated": True}
    assert result.name == "renamed"


def test_update_queued_simulation_sends_expected_body(
    client: QueueClient, httpx2_mock: respx.Router
):
    route = httpx2_mock.patch(f"{BASE_URL}/api/queue/{ELEMENT_ID}").respond(
        status_code=200, json=QUEUE_RESPONSE
    )

    client.update_queued_simulation(
        uuid.UUID(ELEMENT_ID), {"x": 1}, issuer="me", callback_url="http://cb", name="n"
    )

    body = json.loads(route.calls.last.request.content)
    assert body == {
        "parameters": {"x": 1},
        "issuer": "me",
        "callback_url": "http://cb",
        "name": "n",
    }


def test_update_queued_simulation_not_found(client: QueueClient, httpx2_mock: respx.Router):
    httpx2_mock.patch(f"{BASE_URL}/api/queue/{ELEMENT_ID}").respond(
        status_code=404, json=NOT_FOUND_RESPONSE
    )

    with pytest.raises(
        QueueClientElementNotFoundException, match=f"Queue element '{ELEMENT_ID}' not found"
    ):
        client.update_queued_simulation(ELEMENT_ID, {"x": 1})


def test_update_queued_simulation_http_error(client: QueueClient, httpx2_mock: respx.Router):
    httpx2_mock.patch(f"{BASE_URL}/api/queue/{ELEMENT_ID}").respond(
        status_code=500, text="Internal server error"
    )

    with pytest.raises(QueueClientException, match="returned 500") as exc_info:
        client.update_queued_simulation(ELEMENT_ID, {"x": 1})

    assert exc_info.value.status_code == 500


def test_update_queued_simulation_unprocessable(client: QueueClient, httpx2_mock: respx.Router):
    httpx2_mock.patch(f"{BASE_URL}/api/queue/{ELEMENT_ID}").respond(
        status_code=200, json={"not": "serializable"}
    )

    with pytest.raises(QueueClientInvalidResponseException, match="Validation error"):
        client.update_queued_simulation(ELEMENT_ID, {"x": 1})


@pytest.mark.parametrize("status_code", [200, 204])
def test_delete_queued_element(client: QueueClient, status_code: int, httpx2_mock: respx.Router):
    route = httpx2_mock.delete(f"{BASE_URL}/api/queue/{ELEMENT_ID}").respond(
        status_code=status_code
    )

    assert client.delete_queued_element(ELEMENT_ID) is True
    assert route.called


def test_delete_queued_element_accepts_uuid(client: QueueClient, httpx2_mock: respx.Router):
    route = httpx2_mock.delete(f"{BASE_URL}/api/queue/{ELEMENT_ID}").respond(status_code=204)

    client.delete_queued_element(uuid.UUID(ELEMENT_ID))

    assert route.called


def test_delete_queued_element_not_found(client: QueueClient, httpx2_mock: respx.Router):
    httpx2_mock.delete(f"{BASE_URL}/api/queue/{ELEMENT_ID}").respond(
        status_code=404, json=NOT_FOUND_RESPONSE
    )

    with pytest.raises(
        QueueClientElementNotFoundException, match=f"Queue element '{ELEMENT_ID}' not found"
    ) as exc_info:
        client.delete_queued_element(ELEMENT_ID)

    assert exc_info.value.status_code == 404


def test_delete_queued_element_http_error(client: QueueClient, httpx2_mock: respx.Router):
    httpx2_mock.delete(f"{BASE_URL}/api/queue/{ELEMENT_ID}").respond(
        status_code=500, text="Internal server error"
    )

    with pytest.raises(QueueClientException, match="returned 500") as exc_info:
        client.delete_queued_element(ELEMENT_ID)

    assert not isinstance(exc_info.value, QueueClientElementNotFoundException)
    assert exc_info.value.status_code == 500


ALL_CALLS = [
    lambda c: c.claim_element(),
    lambda c: c.get_queued_simulations(),
    lambda c: c.get_queued_simulation(ELEMENT_ID),
    lambda c: c.post_queued_simulation(SimulationQueueElementCreate(parameters={})),
    lambda c: c.update_queued_simulation(ELEMENT_ID, {}),
    lambda c: c.delete_queued_element(ELEMENT_ID),
]
ALL_CALL_IDS = [
    "claim_element",
    "get_queued_simulations",
    "get_queued_simulation",
    "post_queued_simulation",
    "update_queued_simulation",
    "delete_queued_element",
]


@pytest.mark.parametrize("call", ALL_CALLS, ids=ALL_CALL_IDS)
def test_connection_error(client: QueueClient, call, httpx2_mock: respx.Router):
    httpx2_mock.route().mock(side_effect=httpx2.ConnectError("connection refused"))

    with pytest.raises(QueueClientConnectionException, match="connection refused") as exc_info:
        call(client)

    assert exc_info.value.status_code is None
    assert isinstance(exc_info.value.__cause__, httpx2.ConnectError)


@pytest.mark.parametrize("call", ALL_CALLS, ids=ALL_CALL_IDS)
def test_timeout_error(client: QueueClient, call, httpx2_mock: respx.Router):
    httpx2_mock.route().mock(side_effect=httpx2.ReadTimeout("too slow"))

    with pytest.raises(
        QueueClientTimeoutException, match=re.escape("timed out after 10.0s")
    ) as exc_info:
        call(client)

    assert isinstance(exc_info.value.__cause__, httpx2.ReadTimeout)


def test_timeout_is_also_a_connection_error(client: QueueClient, httpx2_mock: respx.Router):
    httpx2_mock.route().mock(side_effect=httpx2.ConnectTimeout("too slow"))

    with pytest.raises(QueueClientConnectionException):
        client.claim_element()


def test_custom_timeout_is_reported(httpx2_mock: respx.Router):
    client = QueueClient(BASE_URL, timeout=2.5)
    httpx2_mock.route().mock(side_effect=httpx2.ReadTimeout("too slow"))

    assert client.timeout == pytest.approx(2.5)
    with pytest.raises(QueueClientTimeoutException, match=re.escape("timed out after 2.5s")):
        client.claim_element()


def test_other_transport_error_is_wrapped(client: QueueClient, httpx2_mock: respx.Router):
    httpx2_mock.route().mock(side_effect=httpx2.RemoteProtocolError("broken"))

    with pytest.raises(QueueClientException):
        client.claim_element()


def test_invalid_url_is_wrapped():
    client = QueueClient("http://[invalid-host")

    with pytest.raises(QueueClientConnectionException):
        client.claim_element()


def test_base_url_trailing_slash_is_stripped(httpx2_mock: respx.Router):
    client = QueueClient(f"{BASE_URL}/")
    route = httpx2_mock.get(f"{BASE_URL}/api/queue/claim").respond(
        status_code=200, json=QUEUE_RESPONSE
    )

    client.claim_element()

    assert client.base_url == BASE_URL
    assert route.called


@pytest.mark.parametrize(
    "exception_type",
    [
        QueueClientConnectionException,
        QueueClientTimeoutException,
        QueueClientElementNotFoundException,
        QueueClientInvalidResponseException,
    ],
)
def test_exceptions_derive_from_base(exception_type: type[Exception]):
    assert issubclass(exception_type, QueueClientException)


def test_timeout_exception_derives_from_connection_exception():
    assert issubclass(QueueClientTimeoutException, QueueClientConnectionException)


def test_exception_status_code_defaults_to_none():
    assert QueueClientException("boom").status_code is None


def test_exception_keeps_status_code_and_message():
    ex = QueueClientException("boom", 418)

    assert str(ex) == "boom"
    assert ex.status_code == 418


def test_client_implements_interface(client: QueueClient):
    assert isinstance(client, QueueClientInterface)
