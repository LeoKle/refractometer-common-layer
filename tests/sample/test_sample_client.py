import json
import uuid

import httpx2
import pytest
import respx

from refractometer_common.sample.interfaces.sample_client_interface import (
    CreateSampleRequest,
    SampleClientConnectionException,
    SampleClientException,
    SampleClientInvalidResponseException,
    SampleClientTimeoutException,
    SampleNotFoundException,
)
from refractometer_common.sample.sample import Sample, SellmeierCoefficients
from refractometer_common.sample.sample_client import SampleClient

BASE_URL = "http://sample-service"

SAMPLE_ID = "6f1c2f8e-2b5c-4d0e-9a57-0d6f3a1d9c11"
OTHER_SAMPLE_ID = "0b9c5f4a-7d3e-4a8b-8f21-5c1e9d2a7b33"

SAMPLE_RESPONSE = {
    "id": SAMPLE_ID,
    "name": "BK7",
    "sellmeier_coefficients": {
        "B": [1.03961212, 0.231792344, 1.01046945],
        "C": [0.00600069867, 0.0200179144, 103.560653],
    },
}

NOT_FOUND_RESPONSE = {"detail": "Sample not found"}


@pytest.fixture
def client() -> SampleClient:
    return SampleClient(BASE_URL)


@pytest.fixture
def domain_sample() -> Sample:
    return Sample(
        id=uuid.UUID(SAMPLE_ID),
        name="Updated BK7",
        sellmeier_coefficients=SellmeierCoefficients(
            B=[1.0, 2.0, 3.0],
            C=[0.1, 0.2, 0.3],
        ),
    )


@pytest.fixture
def create_request() -> CreateSampleRequest:
    return CreateSampleRequest(name="BK7", B=[1.0, 2.0, 3.0], C=[0.1, 0.2, 0.3])


def test_get_all_samples(client: SampleClient, httpx2_mock: respx.Router):
    httpx2_mock.get(f"{BASE_URL}/api/samples").respond(
        status_code=200,
        json=[
            SAMPLE_RESPONSE,
            {**SAMPLE_RESPONSE, "id": OTHER_SAMPLE_ID, "name": "Fused silica"},
        ],
    )

    result = client.get_all_samples()

    assert len(result) == 2
    assert all(isinstance(element, Sample) for element in result)
    assert result[0].id == uuid.UUID(SAMPLE_ID)
    assert result[0].name == "BK7"
    assert SAMPLE_RESPONSE["sellmeier_coefficients"]["B"] == result[0].sellmeier_coefficients.B
    assert SAMPLE_RESPONSE["sellmeier_coefficients"]["C"] == result[0].sellmeier_coefficients.C
    assert result[1].id == uuid.UUID(OTHER_SAMPLE_ID)
    assert result[1].name == "Fused silica"


def test_get_all_samples_empty(client: SampleClient, httpx2_mock: respx.Router):
    httpx2_mock.get(f"{BASE_URL}/api/samples").respond(status_code=200, json=[])

    assert client.get_all_samples() == []


@pytest.mark.parametrize("status_code", [400, 401, 403, 500, 502, 503])
def test_get_all_samples_http_error(
    client: SampleClient, status_code: int, httpx2_mock: respx.Router
):
    httpx2_mock.get(f"{BASE_URL}/api/samples").respond(
        status_code=status_code,
        text="Something went wrong",
    )

    with pytest.raises(SampleClientException, match="Something went wrong") as exc_info:
        client.get_all_samples()

    assert exc_info.value.status_code == status_code


def test_get_all_samples_invalid_json(client: SampleClient, httpx2_mock: respx.Router):
    httpx2_mock.get(f"{BASE_URL}/api/samples").respond(
        status_code=200,
        text="<html>nope</html>",
    )

    with pytest.raises(SampleClientInvalidResponseException, match="not valid JSON"):
        client.get_all_samples()


def test_get_all_samples_not_a_list(client: SampleClient, httpx2_mock: respx.Router):
    httpx2_mock.get(f"{BASE_URL}/api/samples").respond(
        status_code=200,
        json=SAMPLE_RESPONSE,
    )

    with pytest.raises(SampleClientInvalidResponseException, match="Expected a list"):
        client.get_all_samples()


def test_get_all_samples_unprocessable_element(client: SampleClient, httpx2_mock: respx.Router):
    httpx2_mock.get(f"{BASE_URL}/api/samples").respond(
        status_code=200,
        json=[{"not": "serializable"}],
    )

    with pytest.raises(SampleClientInvalidResponseException, match="Validation error"):
        client.get_all_samples()


# --------------------------------------------------------------------------- #
# get_sample
# --------------------------------------------------------------------------- #


def test_get_sample(client: SampleClient, httpx2_mock: respx.Router):
    httpx2_mock.get(f"{BASE_URL}/api/sample/{SAMPLE_ID}").respond(
        status_code=200,
        json=SAMPLE_RESPONSE,
    )

    result = client.get_sample(SAMPLE_ID)

    assert isinstance(result, Sample)
    assert result.id == uuid.UUID(SAMPLE_ID)
    assert result.name == SAMPLE_RESPONSE["name"]
    assert SAMPLE_RESPONSE["sellmeier_coefficients"]["B"] == result.sellmeier_coefficients.B
    assert SAMPLE_RESPONSE["sellmeier_coefficients"]["C"] == result.sellmeier_coefficients.C


def test_get_sample_not_found(client: SampleClient, httpx2_mock: respx.Router):
    httpx2_mock.get(f"{BASE_URL}/api/sample/{SAMPLE_ID}").respond(
        status_code=404,
        json=NOT_FOUND_RESPONSE,
    )

    with pytest.raises(
        SampleNotFoundException,
        match=f"Sample '{SAMPLE_ID}' not found",
    ) as exc_info:
        client.get_sample(SAMPLE_ID)

    assert exc_info.value.status_code == 404


def test_get_sample_not_found_is_client_exception(client: SampleClient, httpx2_mock: respx.Router):
    httpx2_mock.get(f"{BASE_URL}/api/sample/{SAMPLE_ID}").respond(
        status_code=404,
        json=NOT_FOUND_RESPONSE,
    )

    with pytest.raises(SampleClientException):
        client.get_sample(SAMPLE_ID)


def test_get_sample_http_error(client: SampleClient, httpx2_mock: respx.Router):
    httpx2_mock.get(f"{BASE_URL}/api/sample/{SAMPLE_ID}").respond(
        status_code=500,
        text="Internal server error",
    )

    with pytest.raises(
        SampleClientException,
        match="returned 500: Internal server error",
    ) as exc_info:
        client.get_sample(SAMPLE_ID)

    assert not isinstance(exc_info.value, SampleNotFoundException)
    assert exc_info.value.status_code == 500


def test_get_sample_unprocessable(client: SampleClient, httpx2_mock: respx.Router):
    httpx2_mock.get(f"{BASE_URL}/api/sample/{SAMPLE_ID}").respond(
        status_code=200,
        json={"not": "serializable"},
    )

    with pytest.raises(SampleClientInvalidResponseException, match="Validation error"):
        client.get_sample(SAMPLE_ID)


def test_get_sample_invalid_uuid_in_response(client: SampleClient, httpx2_mock: respx.Router):
    httpx2_mock.get(f"{BASE_URL}/api/sample/{SAMPLE_ID}").respond(
        status_code=200,
        json={**SAMPLE_RESPONSE, "id": "not-a-uuid"},
    )

    with pytest.raises(SampleClientInvalidResponseException):
        client.get_sample(SAMPLE_ID)


def test_get_sample_missing_id_in_response(client: SampleClient, httpx2_mock: respx.Router):
    """The DTO allows id=None, but the domain model requires a UUID."""
    response = {k: v for k, v in SAMPLE_RESPONSE.items() if k != "id"}
    httpx2_mock.get(f"{BASE_URL}/api/sample/{SAMPLE_ID}").respond(
        status_code=200,
        json=response,
    )

    with pytest.raises(SampleClientInvalidResponseException, match="Validation error"):
        client.get_sample(SAMPLE_ID)


@pytest.mark.parametrize("status_code", [200, 201])
def test_create_sample(
    client: SampleClient,
    create_request: CreateSampleRequest,
    status_code: int,
    httpx2_mock: respx.Router,
):
    route = httpx2_mock.post(f"{BASE_URL}/api/sample").respond(status_code=status_code)

    result = client.create_sample(create_request)

    assert result is None
    assert route.call_count == 1


def test_create_sample_sends_expected_body(
    client: SampleClient, create_request: CreateSampleRequest, httpx2_mock: respx.Router
):
    route = httpx2_mock.post(f"{BASE_URL}/api/sample").respond(status_code=200)

    client.create_sample(create_request)

    body = json.loads(route.calls.last.request.content)
    # Must be a JSON *object*, not a JSON-encoded string (no double encoding)
    assert isinstance(body, dict)
    assert body["name"] == "BK7"
    assert body["sellmeier_coefficients"] == {"B": [1.0, 2.0, 3.0], "C": [0.1, 0.2, 0.3]}
    assert body.get("id") is None


def test_create_sample_http_error(
    client: SampleClient, create_request: CreateSampleRequest, httpx2_mock: respx.Router
):
    httpx2_mock.post(f"{BASE_URL}/api/sample").respond(
        status_code=500,
        text="Internal server error",
    )

    with pytest.raises(
        SampleClientException,
        match="returned 500: Internal server error",
    ):
        client.create_sample(create_request)


def test_create_sample_validation_error_from_service(
    client: SampleClient, create_request: CreateSampleRequest, httpx2_mock: respx.Router
):
    httpx2_mock.post(f"{BASE_URL}/api/sample").respond(
        status_code=422,
        json={"detail": [{"msg": "field required"}]},
    )

    with pytest.raises(SampleClientException, match="field required") as exc_info:
        client.create_sample(create_request)

    assert exc_info.value.status_code == 422


@pytest.mark.parametrize(
    "overrides",
    [
        {"B": [1.0, 2.0]},
        {"B": [1.0, 2.0, 3.0, 4.0]},
        {"C": [0.1]},
        {"C": []},
    ],
    ids=["B_too_short", "B_too_long", "C_too_short", "C_empty"],
)
def test_create_sample_request_requires_three_coefficients(overrides: dict):
    from pydantic import ValidationError

    payload = {"name": "BK7", "B": [1.0, 2.0, 3.0], "C": [0.1, 0.2, 0.3], **overrides}

    with pytest.raises(ValidationError):
        CreateSampleRequest(**payload)


def test_update_sample(client: SampleClient, domain_sample: Sample, httpx2_mock: respx.Router):
    route = httpx2_mock.patch(f"{BASE_URL}/api/sample").respond(status_code=200)

    result = client.update_sample(domain_sample)

    assert result is None
    assert route.call_count == 1


def test_update_sample_sends_expected_body(
    client: SampleClient, domain_sample: Sample, httpx2_mock: respx.Router
):
    route = httpx2_mock.patch(f"{BASE_URL}/api/sample").respond(status_code=200)

    client.update_sample(domain_sample)

    body = json.loads(route.calls.last.request.content)
    assert isinstance(body, dict)
    assert body == {
        "id": SAMPLE_ID,
        "name": "Updated BK7",
        "sellmeier_coefficients": {"B": [1.0, 2.0, 3.0], "C": [0.1, 0.2, 0.3]},
    }


def test_update_sample_not_found(
    client: SampleClient, domain_sample: Sample, httpx2_mock: respx.Router
):
    httpx2_mock.patch(f"{BASE_URL}/api/sample").respond(
        status_code=404,
        json=NOT_FOUND_RESPONSE,
    )

    with pytest.raises(
        SampleNotFoundException,
        match=f"Sample '{SAMPLE_ID}' not found",
    ):
        client.update_sample(domain_sample)


def test_update_sample_bad_request(
    client: SampleClient, domain_sample: Sample, httpx2_mock: respx.Router
):
    httpx2_mock.patch(f"{BASE_URL}/api/sample").respond(
        status_code=400,
        json={"detail": "Missing id"},
    )

    with pytest.raises(SampleClientException, match="Missing id") as exc_info:
        client.update_sample(domain_sample)

    assert exc_info.value.status_code == 400


def test_update_sample_http_error(
    client: SampleClient, domain_sample: Sample, httpx2_mock: respx.Router
):
    httpx2_mock.patch(f"{BASE_URL}/api/sample").respond(
        status_code=500,
        text="Internal server error",
    )

    with pytest.raises(
        SampleClientException,
        match="returned 500: Internal server error",
    ):
        client.update_sample(domain_sample)


# --------------------------------------------------------------------------- #
# delete_sample
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("status_code", [200, 204])
def test_delete_sample(client: SampleClient, status_code: int, httpx2_mock: respx.Router):
    route = httpx2_mock.delete(f"{BASE_URL}/api/sample/{SAMPLE_ID}").respond(
        status_code=status_code,
    )

    result = client.delete_sample(SAMPLE_ID)

    assert result is None
    assert route.call_count == 1


def test_delete_sample_not_found(client: SampleClient, httpx2_mock: respx.Router):
    httpx2_mock.delete(f"{BASE_URL}/api/sample/{SAMPLE_ID}").respond(
        status_code=404, json=NOT_FOUND_RESPONSE
    )

    with pytest.raises(SampleNotFoundException, match="Sample not found") as exc_info:
        client.delete_sample(SAMPLE_ID)

    assert exc_info.value.status_code == 404


def test_delete_sample_http_error(client: SampleClient, httpx2_mock: respx.Router):
    httpx2_mock.delete(f"{BASE_URL}/api/sample/{SAMPLE_ID}").respond(
        status_code=500, text="Internal server error"
    )

    with pytest.raises(
        SampleClientException,
        match="returned 500: Internal server error",
    ):
        client.delete_sample(SAMPLE_ID)


# --------------------------------------------------------------------------- #
# transport-level errors
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "call",
    [
        lambda c: c.get_all_samples(),
        lambda c: c.get_sample(SAMPLE_ID),
        lambda c: c.create_sample(CreateSampleRequest(name="BK7", B=[1, 2, 3], C=[1, 2, 3])),
        lambda c: c.delete_sample(SAMPLE_ID),
    ],
    ids=["get_all_samples", "get_sample", "create_sample", "delete_sample"],
)
def test_connection_error(client: SampleClient, call, httpx2_mock: respx.Router):
    httpx2_mock.route().mock(side_effect=httpx2.ConnectError("connection refused"))

    with pytest.raises(SampleClientConnectionException, match="connection refused") as exc_info:
        call(client)

    assert exc_info.value.status_code is None
    assert isinstance(exc_info.value.__cause__, httpx2.ConnectError)


def test_update_sample_connection_error(
    client: SampleClient, domain_sample: Sample, httpx2_mock: respx.Router
):
    httpx2_mock.route().mock(side_effect=httpx2.ConnectError("connection refused"))

    with pytest.raises(SampleClientConnectionException, match="connection refused"):
        client.update_sample(domain_sample)


def test_timeout_error(client: SampleClient, httpx2_mock: respx.Router):
    httpx2_mock.route().mock(side_effect=httpx2.ReadTimeout("too slow"))

    with pytest.raises(SampleClientTimeoutException, match="timed out"):
        client.get_all_samples()


def test_timeout_is_also_a_connection_error(client: SampleClient, httpx2_mock: respx.Router):
    httpx2_mock.route().mock(side_effect=httpx2.ConnectTimeout("too slow"))

    with pytest.raises(SampleClientConnectionException):
        client.get_all_samples()


def test_other_transport_error_is_wrapped(client: SampleClient, httpx2_mock: respx.Router):
    httpx2_mock.route().mock(side_effect=httpx2.RemoteProtocolError("protocol error"))

    with pytest.raises(SampleClientException):
        client.get_all_samples()


def test_invalid_url_is_wrapped():
    client = SampleClient("http://[invalid-host")

    with pytest.raises(SampleClientConnectionException):
        client.get_all_samples()


def test_base_url_trailing_slash_is_stripped():
    client = SampleClient(f"{BASE_URL}/")

    assert client.base_url == BASE_URL


def test_custom_timeout_is_stored():
    client = SampleClient(BASE_URL, timeout=2.5)

    assert client.timeout == 2.5
