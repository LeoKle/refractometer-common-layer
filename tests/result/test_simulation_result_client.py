import uuid
from datetime import UTC, datetime

import httpx2
import pytest
import respx

from refractometer_common.result.simulation_result import SimulationResult
from refractometer_common.result.simulation_result_client import (
    SimulationResultClient,
    SimulationResultClientConnectionException,
    SimulationResultClientException,
    SimulationResultClientInvalidResponseException,
    SimulationResultClientTimeoutException,
    SimulationResultNotFoundException,
)

BASE_URL = "http://result-service"

RESULT_ID = "6f1c2f8e-2b5c-4d0e-9a57-0d6f3a1d9c11"
OTHER_RESULT_ID = "0b9c5f4a-7d3e-4a8b-8f21-5c1e9d2a7b33"

RESULT_RESPONSE = {
    "id": RESULT_ID,
    "parameters": {"foo": "bar"},
    "image_id": "image-123",
    "issued_at": "2026-09-18T10:00:00Z",
    "completed_at": "2026-09-18T10:05:00Z",
}

NOT_FOUND_RESPONSE = {"detail": "Simulation result not found"}


@pytest.fixture
def client() -> SimulationResultClient:
    return SimulationResultClient(BASE_URL)


@pytest.fixture
def domain_result() -> SimulationResult:
    return SimulationResult(
        id=uuid.UUID(RESULT_ID),
        parameters={"updated": True},
        image_id="image-456",
        issued_at=datetime(2026, 9, 18, 10, 0, tzinfo=UTC),
        completed_at=datetime(2026, 9, 18, 10, 5, tzinfo=UTC),
    )


def test_get_results(client: SimulationResultClient, httpx2_mock: respx.Router):
    httpx2_mock.get(f"{BASE_URL}/api/results").respond(
        status_code=200,
        json=[
            RESULT_RESPONSE,
            {**RESULT_RESPONSE, "id": OTHER_RESULT_ID, "image_id": "image-456"},
        ],
    )
    result = client.get_results()

    assert len(result) == 2
    assert all(isinstance(element, SimulationResult) for element in result)
    assert result[0].id == uuid.UUID(RESULT_ID)
    assert result[0].parameters == RESULT_RESPONSE["parameters"]
    assert result[0].image_id == "image-123"
    assert result[1].id == uuid.UUID(OTHER_RESULT_ID)
    assert result[1].image_id == "image-456"


def test_get_results_empty(client: SimulationResultClient, httpx2_mock: respx.Router):
    httpx2_mock.get(f"{BASE_URL}/api/results").respond(
        status_code=200,
        json=[],
    )

    assert client.get_results() == []


@pytest.mark.parametrize("status_code", [400, 401, 403, 500, 502, 503])
def test_get_results_http_error(
    client: SimulationResultClient, status_code: int, httpx2_mock: respx.Router
):
    httpx2_mock.get(f"{BASE_URL}/api/results").respond(
        status_code=status_code,
        text="Something went wrong",
    )

    with pytest.raises(SimulationResultClientException, match="Something went wrong") as exc_info:
        client.get_results()

    assert exc_info.value.status_code == status_code


def test_get_results_invalid_json(client: SimulationResultClient, httpx2_mock: respx.Router):
    httpx2_mock.get(f"{BASE_URL}/api/results").respond(
        status_code=200,
        text="<html>nope</html>",
    )

    with pytest.raises(SimulationResultClientInvalidResponseException, match="not valid JSON"):
        client.get_results()


def test_get_results_not_a_list(client: SimulationResultClient, httpx2_mock: respx.Router):
    httpx2_mock.get(f"{BASE_URL}/api/results").respond(
        status_code=200,
        json=RESULT_RESPONSE,
    )

    with pytest.raises(SimulationResultClientInvalidResponseException, match="Expected a list"):
        client.get_results()


def test_get_results_unprocessable_element(
    client: SimulationResultClient, httpx2_mock: respx.Router
):
    httpx2_mock.get(f"{BASE_URL}/api/results").respond(
        status_code=200,
        json=[{"not": "serializable"}],
    )

    with pytest.raises(SimulationResultClientInvalidResponseException, match="Validation error"):
        client.get_results()


def test_get_result(client: SimulationResultClient, httpx2_mock: respx.Router):
    httpx2_mock.get(f"{BASE_URL}/api/result/{RESULT_ID}").respond(
        status_code=200,
        json=RESULT_RESPONSE,
    )

    result = client.get_result(RESULT_ID)

    assert isinstance(result, SimulationResult)
    assert result.id == uuid.UUID(RESULT_ID)
    assert result.parameters == RESULT_RESPONSE["parameters"]
    assert result.image_id == RESULT_RESPONSE["image_id"]
    assert result.issued_at == datetime(2026, 9, 18, 10, 0, tzinfo=UTC)
    assert result.completed_at == datetime(2026, 9, 18, 10, 5, tzinfo=UTC)


def test_get_result_accepts_uuid(client: SimulationResultClient, httpx2_mock: respx.Router):
    httpx2_mock.get(f"{BASE_URL}/api/result/{RESULT_ID}").respond(
        status_code=200,
        json=RESULT_RESPONSE,
    )

    result = client.get_result(uuid.UUID(RESULT_ID))

    assert result.id == uuid.UUID(RESULT_ID)


def test_get_result_not_found(client: SimulationResultClient, httpx2_mock: respx.Router):
    httpx2_mock.get(f"{BASE_URL}/api/result/{RESULT_ID}").respond(
        status_code=404,
        json=NOT_FOUND_RESPONSE,
    )

    with pytest.raises(
        SimulationResultNotFoundException,
        match=f"Simulation result '{RESULT_ID}' not found",
    ) as exc_info:
        client.get_result(RESULT_ID)

    assert exc_info.value.status_code == 404


def test_get_result_not_found_is_client_exception(
    client: SimulationResultClient, httpx2_mock: respx.Router
):
    httpx2_mock.get(f"{BASE_URL}/api/result/{RESULT_ID}").respond(
        status_code=404,
        json=NOT_FOUND_RESPONSE,
    )

    with pytest.raises(SimulationResultClientException):
        client.get_result(RESULT_ID)


def test_get_result_http_error(client: SimulationResultClient, httpx2_mock: respx.Router):
    httpx2_mock.get(f"{BASE_URL}/api/result/{RESULT_ID}").respond(
        status_code=500,
        text="Internal server error",
    )

    with pytest.raises(
        SimulationResultClientException,
        match="returned 500: Internal server error",
    ) as exc_info:
        client.get_result(RESULT_ID)

    assert not isinstance(exc_info.value, SimulationResultNotFoundException)
    assert exc_info.value.status_code == 500


def test_get_result_unprocessable(client: SimulationResultClient, httpx2_mock: respx.Router):
    httpx2_mock.get(f"{BASE_URL}/api/result/{RESULT_ID}").respond(
        status_code=200,
        json={"not": "serializable"},
    )

    with pytest.raises(SimulationResultClientInvalidResponseException, match="Validation error"):
        client.get_result(RESULT_ID)


def test_get_result_invalid_uuid_in_response(
    client: SimulationResultClient, httpx2_mock: respx.Router
):
    httpx2_mock.get(f"{BASE_URL}/api/result/{RESULT_ID}").respond(
        status_code=200,
        json={**RESULT_RESPONSE, "id": "not-a-uuid"},
    )

    with pytest.raises(SimulationResultClientInvalidResponseException):
        client.get_result(RESULT_ID)


@pytest.mark.parametrize("status_code", [200, 201])
def test_create_result(client: SimulationResultClient, status_code: int, httpx2_mock: respx.Router):
    httpx2_mock.post(f"{BASE_URL}/api/result").respond(
        status_code=status_code,
        json=RESULT_RESPONSE,
    )

    result = client.create_result(
        parameters={"foo": "bar"},
        image_id="image-123",
        issued_at=datetime(2026, 9, 18, 10, 0, tzinfo=UTC),
        completed_at=datetime(2026, 9, 18, 10, 5, tzinfo=UTC),
    )

    assert result.id == uuid.UUID(RESULT_ID)
    assert result.image_id == "image-123"


def test_create_result_http_error(client: SimulationResultClient, httpx2_mock: respx.Router):
    httpx2_mock.post(f"{BASE_URL}/api/result").respond(
        status_code=500,
        text="Internal server error",
    )

    with pytest.raises(
        SimulationResultClientException,
        match="returned 500: Internal server error",
    ):
        client.create_result(
            parameters={"foo": "bar"},
            image_id="image-123",
            issued_at=datetime(2026, 9, 18, 10, 0, tzinfo=UTC),
            completed_at=datetime(2026, 9, 18, 10, 5, tzinfo=UTC),
        )


def test_create_result_validation_error_from_service(
    client: SimulationResultClient, httpx2_mock: respx.Router
):
    httpx2_mock.post(f"{BASE_URL}/api/result").respond(
        status_code=422,
        json={"detail": [{"msg": "field required"}]},
    )

    with pytest.raises(SimulationResultClientException, match="field required") as exc_info:
        client.create_result(
            parameters={},
            image_id="image-123",
            issued_at=datetime(2026, 9, 18, 10, 0, tzinfo=UTC),
            completed_at=datetime(2026, 9, 18, 10, 5, tzinfo=UTC),
        )

    assert exc_info.value.status_code == 422


def test_create_result_unprocessable_response(
    client: SimulationResultClient, httpx2_mock: respx.Router
):
    httpx2_mock.post(f"{BASE_URL}/api/result").respond(
        status_code=200,
        json={"not": "valid"},
    )

    with pytest.raises(SimulationResultClientInvalidResponseException):
        client.create_result(
            parameters={},
            image_id="image-123",
            issued_at=datetime(2026, 9, 18, 10, 0, tzinfo=UTC),
            completed_at=datetime(2026, 9, 18, 10, 5, tzinfo=UTC),
        )


def test_update_result(
    client: SimulationResultClient, domain_result: SimulationResult, httpx2_mock: respx.Router
):
    new_image_id = str(uuid.uuid4())
    httpx2_mock.patch(f"{BASE_URL}/api/result").respond(
        status_code=200,
        json={**RESULT_RESPONSE, "parameters": {"updated": True}, "image_id": new_image_id},
    )

    result = client.update_result(domain_result)

    assert result.id == uuid.UUID(RESULT_ID)
    assert result.parameters == {"updated": True}
    assert result.image_id == new_image_id


def test_update_result_not_found(
    client: SimulationResultClient, domain_result: SimulationResult, httpx2_mock: respx.Router
):
    httpx2_mock.patch(f"{BASE_URL}/api/result").respond(
        status_code=404,
        json=NOT_FOUND_RESPONSE,
    )

    with pytest.raises(
        SimulationResultNotFoundException,
        match=f"Simulation result '{RESULT_ID}' not found",
    ):
        client.update_result(domain_result)


def test_update_result_http_error(
    client: SimulationResultClient,
    domain_result: SimulationResult,
    httpx2_mock: respx.Router,
):
    httpx2_mock.patch(f"{BASE_URL}/api/result").respond(
        status_code=500,
        text="Internal server error",
    )

    with pytest.raises(
        SimulationResultClientException,
        match="returned 500: Internal server error",
    ):
        client.update_result(domain_result)


@pytest.mark.parametrize("status_code", [200, 204])
def test_delete_result(client: SimulationResultClient, status_code: int, httpx2_mock: respx.Router):
    httpx2_mock.delete(f"{BASE_URL}/api/result/{RESULT_ID}").respond(
        status_code=status_code,
    )

    result = client.delete_result(RESULT_ID)

    assert result is None


def test_delete_result_not_found(client: SimulationResultClient, httpx2_mock: respx.Router):
    httpx2_mock.delete(f"{BASE_URL}/api/result/{RESULT_ID}").respond(
        status_code=404, json=NOT_FOUND_RESPONSE
    )

    with pytest.raises(SimulationResultNotFoundException):
        client.delete_result(RESULT_ID)


def test_delete_result_http_error(client: SimulationResultClient, httpx2_mock: respx.Router):
    httpx2_mock.delete(f"{BASE_URL}/api/result/{RESULT_ID}").respond(
        status_code=500, text="Internal server error"
    )

    with pytest.raises(
        SimulationResultClientException,
        match="returned 500: Internal server error",
    ):
        client.delete_result(RESULT_ID)


@pytest.mark.parametrize(
    "call",
    [
        lambda c: c.get_results(),
        lambda c: c.get_result(RESULT_ID),
        lambda c: c.delete_result(RESULT_ID),
    ],
    ids=["get_results", "get_result", "delete_result"],
)
def test_connection_error(client: SimulationResultClient, call, httpx2_mock: respx.Router):
    httpx2_mock.route().mock(side_effect=httpx2.ConnectError("connection refused"))

    with pytest.raises(SimulationResultClientConnectionException, match="connection refused") as (
        exc_info
    ):
        call(client)

    assert exc_info.value.status_code is None
    assert isinstance(exc_info.value.__cause__, httpx2.ConnectError)


def test_timeout_error(client: SimulationResultClient, httpx2_mock: respx.Router):
    httpx2_mock.route().mock(side_effect=httpx2.ReadTimeout("too slow"))

    with pytest.raises(SimulationResultClientTimeoutException, match="timed out"):
        client.get_results()


def test_timeout_is_also_a_connection_error(
    client: SimulationResultClient, httpx2_mock: respx.Router
):
    httpx2_mock.route().mock(side_effect=httpx2.ConnectTimeout("too slow"))

    with pytest.raises(SimulationResultClientConnectionException):
        client.get_results()


def test_other_transport_error_is_wrapped(
    client: SimulationResultClient, httpx2_mock: respx.Router
):
    httpx2_mock.route().mock(side_effect=httpx2.RemoteProtocolError("too slow"))

    with pytest.raises(SimulationResultClientException):
        client.get_results()


def test_invalid_url_is_wrapped():
    client = SimulationResultClient("http://[invalid-host")

    with pytest.raises(SimulationResultClientConnectionException):
        client.get_results()


def test_base_url_trailing_slash_is_stripped(httpx2_mock: respx.Router):
    client = SimulationResultClient(f"{BASE_URL}/")

    assert client.base_url == BASE_URL
