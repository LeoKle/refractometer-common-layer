import pytest
import respx
from httpx import Response
from pydantic import ValidationError

from refractometer_common.queue import (
    QueueClient,
    QueueClientElementNotFoundException,
    QueueClientException,
)
from refractometer_common.queue.queue_element import SimulationQueueElementCreate

BASE_URL = "http://queue-service"

QUEUE_RESPONSE = {
    "parameters": {"foo": "bar"},
    "index": 0,
    "being_processed": False,
    "issuer": "test",
    "callback_url": "http://callback",
    "id": "123",
    "name": "test-simulation",
    "image_id": "image-123",
    "issued_at": "2026-09-18T10:00:00Z",
    "completed_at": None,
}

QUEUE_404_RESPONSE = {"detail": "No queued simulations available"}


@pytest.fixture
def client() -> QueueClient:
    return QueueClient(BASE_URL)


@respx.mock
def test_claim_element(client: QueueClient):
    route = respx.get(f"{BASE_URL}/api/queue/claim").mock(
        return_value=Response(200, json=QUEUE_RESPONSE)
    )

    result = client.claim_element()

    assert route.called
    assert result.id == QUEUE_RESPONSE["id"]
    assert result.parameters == QUEUE_RESPONSE["parameters"]
    assert result.issuer == QUEUE_RESPONSE["issuer"]
    assert result.name == QUEUE_RESPONSE["name"]


@respx.mock
def test_claim_element_404(client: QueueClient):
    route = respx.get(f"{BASE_URL}/api/queue/claim").mock(
        return_value=Response(404, json=QUEUE_404_RESPONSE)
    )

    with pytest.raises(QueueClientElementNotFoundException):
        client.claim_element()

    assert route.called


@pytest.mark.parametrize("status_code", [400, 401, 403, 500, 502, 503])
@respx.mock
def test_claim_element_http_error(
    client: QueueClient,
    status_code: int,
):
    respx.get(f"{BASE_URL}/api/queue/claim").mock(
        return_value=Response(status_code, text="Something went wrong")
    )

    with pytest.raises(
        QueueClientException,
    ):
        client.claim_element()


@respx.mock
def test_claim_element_unprocessable(client: QueueClient):
    route = respx.get(f"{BASE_URL}/api/queue/claim").mock(
        return_value=Response(200, json={"not": "serializable"})
    )

    with pytest.raises((QueueClientException, ValidationError)):
        # content is not of type SimulationQueueResponse
        client.claim_element()

    assert route.called


@respx.mock
def test_get_queued_simulations(client: QueueClient):
    route = respx.get(f"{BASE_URL}/api/queued").mock(
        return_value=Response(
            200,
            json=[
                QUEUE_RESPONSE,
                {
                    **QUEUE_RESPONSE,
                    "id": "456",
                    "name": "second-simulation",
                },
            ],
        )
    )

    result = client.get_queued_simulations()

    assert route.called
    assert len(result) == 2
    assert result[0].id == "123"
    assert result[1].id == "456"


@respx.mock
def test_get_queued_simulations_http_error(client: QueueClient):
    respx.get(f"{BASE_URL}/api/queued").mock(
        return_value=Response(500, text="Internal server error")
    )

    with pytest.raises(
        QueueClientException,
    ):
        client.get_queued_simulations()


@respx.mock
def test_get_queued_simulation(client: QueueClient):
    route = respx.get(f"{BASE_URL}/api/queue/123").mock(
        return_value=Response(200, json=QUEUE_RESPONSE)
    )

    result = client.get_queued_simulation("123")

    assert route.called
    assert result.id == "123"


@respx.mock
def test_get_queued_simulation_not_found(client: QueueClient):
    respx.get(f"{BASE_URL}/api/queue/123").mock(
        return_value=Response(
            404,
            json={"detail": "Queue element '123' not found"},
        )
    )

    with pytest.raises(
        QueueClientElementNotFoundException,
        match="Queue element '123' not found",
    ):
        client.get_queued_simulation("123")


@respx.mock
def test_get_queued_simulation_http_error(client: QueueClient):
    respx.get(f"{BASE_URL}/api/queue/123").mock(
        return_value=Response(500, text="Internal server error")
    )

    with pytest.raises(
        QueueClientException,
        match="Failed to get queued simulation: Internal server error",
    ):
        client.get_queued_simulation("123")


@respx.mock
def test_post_queued_simulation(client: QueueClient):
    route = respx.post(f"{BASE_URL}/api/queue").mock(return_value=Response(201, json={"id": "123"}))

    request = SimulationQueueElementCreate(
        parameters={"foo": "bar"},
        issuer="test",
        callback_url="http://callback",
        name="my-simulation",
    )

    result = client.post_queued_simulation(request)

    assert route.called
    assert result == "123"


@respx.mock
def test_post_queued_simulation_http_error(client: QueueClient):
    respx.post(f"{BASE_URL}/api/queue").mock(
        return_value=Response(500, text="Internal server error")
    )

    request = SimulationQueueElementCreate(
        parameters={"foo": "bar"},
    )
    with pytest.raises(
        QueueClientException,
        match="Failed to post queued simulation: Internal server error",
    ):
        client.post_queued_simulation(request)


@respx.mock
def test_update_queued_simulation(client: QueueClient):
    route = respx.patch(f"{BASE_URL}/api/queue/123").mock(
        return_value=Response(
            200,
            json=QUEUE_RESPONSE,
        )
    )

    result = client.update_queued_simulation(
        queued_element_id="123",
        parameters={"updated": True},
        issuer="new-issuer",
        callback_url="http://new-callback",
        name="updated-name",
    )

    assert route.called
    assert result.id == "123"


@respx.mock
def test_update_queued_simulation_not_found(client: QueueClient):
    respx.patch(f"{BASE_URL}/api/queue/123").mock(
        return_value=Response(
            404,
            json={"detail": "Queue element '123' not found"},
        )
    )

    with pytest.raises(
        QueueClientElementNotFoundException,
        match="Queue element '123' not found",
    ):
        client.update_queued_simulation(
            queued_element_id="123",
            parameters={"foo": "bar"},
        )


@respx.mock
def test_update_queued_simulation_http_error(client: QueueClient):
    respx.patch(f"{BASE_URL}/api/queue/123").mock(
        return_value=Response(500, text="Internal server error")
    )

    with pytest.raises(
        QueueClientException,
        match="Failed to update queued simulation: Internal server error",
    ):
        client.update_queued_simulation(
            queued_element_id="123",
            parameters={"foo": "bar"},
        )


@respx.mock
def test_delete_queued_element(client: QueueClient):
    route = respx.delete(f"{BASE_URL}/api/queue/123").mock(return_value=Response(204))

    result = client.delete_queued_element("123")

    assert route.called
    assert result is True


@respx.mock
def test_delete_queued_element_not_found(client: QueueClient):
    respx.delete(f"{BASE_URL}/api/queue/123").mock(
        return_value=Response(
            404,
            json={"detail": "Queue element '123' not found"},
        )
    )

    with pytest.raises(
        QueueClientElementNotFoundException,
        match="Queue element '123' not found",
    ):
        client.delete_queued_element("123")


@respx.mock
def test_delete_queued_element_http_error(client: QueueClient):
    respx.delete(f"{BASE_URL}/api/queue/123").mock(
        return_value=Response(500, text="Internal server error")
    )

    with pytest.raises(
        QueueClientException,
        match="Failed to delete queued element: Internal server error",
    ):
        client.delete_queued_element("123")
