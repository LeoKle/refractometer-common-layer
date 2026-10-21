import json
import uuid

import httpx2
import pytest
import respx

from refractometer_common.spectrum.interfaces.spectrum_client_interface import (
    CreateSpectrumRequest,
    SpectrumClientConnectionException,
    SpectrumClientException,
    SpectrumClientInvalidResponseException,
    SpectrumClientTimeoutException,
    SpectrumNotFoundException,
)
from refractometer_common.spectrum.spectrum import Spectrum
from refractometer_common.spectrum.spectrum_client import SpectrumClient

BASE_URL = "http://spectrum-service"

SPECTRUM_ID = "6f1c2f8e-2b5c-4d0e-9a57-0d6f3a1d9c11"
OTHER_SPECTRUM_ID = "0b9c5f4a-7d3e-4a8b-8f21-5c1e9d2a7b33"

SPECTRUM_RESPONSE = {
    "id": SPECTRUM_ID,
    "name": "Sodium D-line",
    "wavelengths": [588.0, 589.0, 590.0],
    "intensities": [0.1, 1.0, 0.2],
}

NOT_FOUND_RESPONSE = {"detail": "Spectrum not found"}


@pytest.fixture
def client() -> SpectrumClient:
    return SpectrumClient(BASE_URL)


@pytest.fixture
def domain_spectrum() -> Spectrum:
    return Spectrum(
        id=uuid.UUID(SPECTRUM_ID),
        name="Updated spectrum",
        wavelengths=[400.0, 500.0, 600.0],
        intensities=[0.3, 0.6, 0.9],
    )


@pytest.fixture
def create_request() -> CreateSpectrumRequest:
    return CreateSpectrumRequest(
        name="Sodium D-line",
        wavelengths=[588.0, 589.0, 590.0],
        intensities=[0.1, 1.0, 0.2],
    )


def test_get_all_spectrums(client: SpectrumClient, httpx2_mock: respx.Router):
    httpx2_mock.get(f"{BASE_URL}/api/spectrums").respond(
        status_code=200,
        json=[
            SPECTRUM_RESPONSE,
            {**SPECTRUM_RESPONSE, "id": OTHER_SPECTRUM_ID, "name": "Mercury"},
        ],
    )

    result = client.get_all_spectrums()

    assert len(result) == 2
    assert all(isinstance(element, Spectrum) for element in result)
    assert result[0].id == uuid.UUID(SPECTRUM_ID)
    assert result[0].name == "Sodium D-line"
    assert result[0].wavelengths == SPECTRUM_RESPONSE["wavelengths"]
    assert result[0].intensities == SPECTRUM_RESPONSE["intensities"]
    assert result[1].id == uuid.UUID(OTHER_SPECTRUM_ID)
    assert result[1].name == "Mercury"


def test_get_all_spectrums_empty(client: SpectrumClient, httpx2_mock: respx.Router):
    httpx2_mock.get(f"{BASE_URL}/api/spectrums").respond(status_code=200, json=[])

    assert client.get_all_spectrums() == []


@pytest.mark.parametrize("status_code", [400, 401, 403, 500, 502, 503])
def test_get_all_spectrums_http_error(
    client: SpectrumClient, status_code: int, httpx2_mock: respx.Router
):
    httpx2_mock.get(f"{BASE_URL}/api/spectrums").respond(
        status_code=status_code,
        text="Something went wrong",
    )

    with pytest.raises(SpectrumClientException, match="Something went wrong") as exc_info:
        client.get_all_spectrums()

    assert exc_info.value.status_code == status_code


def test_get_all_spectrums_invalid_json(client: SpectrumClient, httpx2_mock: respx.Router):
    httpx2_mock.get(f"{BASE_URL}/api/spectrums").respond(
        status_code=200,
        text="<html>nope</html>",
    )

    with pytest.raises(SpectrumClientInvalidResponseException, match="not valid JSON"):
        client.get_all_spectrums()


def test_get_all_spectrums_not_a_list(client: SpectrumClient, httpx2_mock: respx.Router):
    httpx2_mock.get(f"{BASE_URL}/api/spectrums").respond(
        status_code=200,
        json=SPECTRUM_RESPONSE,
    )

    with pytest.raises(SpectrumClientInvalidResponseException, match="Expected a list"):
        client.get_all_spectrums()


def test_get_all_spectrums_unprocessable_element(client: SpectrumClient, httpx2_mock: respx.Router):
    httpx2_mock.get(f"{BASE_URL}/api/spectrums").respond(
        status_code=200,
        json=[{"not": "serializable"}],
    )

    with pytest.raises(SpectrumClientInvalidResponseException, match="Validation error"):
        client.get_all_spectrums()


def test_get_spectrum(client: SpectrumClient, httpx2_mock: respx.Router):
    httpx2_mock.get(f"{BASE_URL}/api/spectrum/{SPECTRUM_ID}").respond(
        status_code=200,
        json=SPECTRUM_RESPONSE,
    )

    result = client.get_spectrum(SPECTRUM_ID)

    assert isinstance(result, Spectrum)
    assert result.id == uuid.UUID(SPECTRUM_ID)
    assert result.name == SPECTRUM_RESPONSE["name"]
    assert result.wavelengths == SPECTRUM_RESPONSE["wavelengths"]
    assert result.intensities == SPECTRUM_RESPONSE["intensities"]


def test_get_spectrum_not_found(client: SpectrumClient, httpx2_mock: respx.Router):
    httpx2_mock.get(f"{BASE_URL}/api/spectrum/{SPECTRUM_ID}").respond(
        status_code=404,
        json=NOT_FOUND_RESPONSE,
    )

    with pytest.raises(
        SpectrumNotFoundException,
        match=f"Spectrum '{SPECTRUM_ID}' not found",
    ) as exc_info:
        client.get_spectrum(SPECTRUM_ID)

    assert exc_info.value.status_code == 404


def test_get_spectrum_not_found_is_client_exception(
    client: SpectrumClient, httpx2_mock: respx.Router
):
    httpx2_mock.get(f"{BASE_URL}/api/spectrum/{SPECTRUM_ID}").respond(
        status_code=404,
        json=NOT_FOUND_RESPONSE,
    )

    with pytest.raises(SpectrumClientException):
        client.get_spectrum(SPECTRUM_ID)


def test_get_spectrum_http_error(client: SpectrumClient, httpx2_mock: respx.Router):
    httpx2_mock.get(f"{BASE_URL}/api/spectrum/{SPECTRUM_ID}").respond(
        status_code=500,
        text="Internal server error",
    )

    with pytest.raises(
        SpectrumClientException,
        match="returned 500: Internal server error",
    ) as exc_info:
        client.get_spectrum(SPECTRUM_ID)

    assert not isinstance(exc_info.value, SpectrumNotFoundException)
    assert exc_info.value.status_code == 500


def test_get_spectrum_unprocessable(client: SpectrumClient, httpx2_mock: respx.Router):
    httpx2_mock.get(f"{BASE_URL}/api/spectrum/{SPECTRUM_ID}").respond(
        status_code=200,
        json={"not": "serializable"},
    )

    with pytest.raises(SpectrumClientInvalidResponseException, match="Validation error"):
        client.get_spectrum(SPECTRUM_ID)


def test_get_spectrum_invalid_uuid_in_response(client: SpectrumClient, httpx2_mock: respx.Router):
    httpx2_mock.get(f"{BASE_URL}/api/spectrum/{SPECTRUM_ID}").respond(
        status_code=200,
        json={**SPECTRUM_RESPONSE, "id": "not-a-uuid"},
    )

    with pytest.raises(SpectrumClientInvalidResponseException):
        client.get_spectrum(SPECTRUM_ID)


def test_get_spectrum_missing_id_in_response(client: SpectrumClient, httpx2_mock: respx.Router):
    response = {k: v for k, v in SPECTRUM_RESPONSE.items() if k != "id"}
    httpx2_mock.get(f"{BASE_URL}/api/spectrum/{SPECTRUM_ID}").respond(
        status_code=200,
        json=response,
    )

    with pytest.raises(SpectrumClientInvalidResponseException, match="Validation error"):
        client.get_spectrum(SPECTRUM_ID)


@pytest.mark.parametrize("missing", ["name", "wavelengths", "intensities"])
def test_get_spectrum_missing_field_in_response(
    client: SpectrumClient, missing: str, httpx2_mock: respx.Router
):
    response = {k: v for k, v in SPECTRUM_RESPONSE.items() if k != missing}
    httpx2_mock.get(f"{BASE_URL}/api/spectrum/{SPECTRUM_ID}").respond(
        status_code=200,
        json=response,
    )

    with pytest.raises(SpectrumClientInvalidResponseException, match="Validation error"):
        client.get_spectrum(SPECTRUM_ID)


def test_get_spectrum_non_numeric_values_in_response(
    client: SpectrumClient, httpx2_mock: respx.Router
):
    httpx2_mock.get(f"{BASE_URL}/api/spectrum/{SPECTRUM_ID}").respond(
        status_code=200,
        json={**SPECTRUM_RESPONSE, "wavelengths": ["a", "b", "c"]},
    )

    with pytest.raises(SpectrumClientInvalidResponseException, match="Validation error"):
        client.get_spectrum(SPECTRUM_ID)


@pytest.mark.parametrize("status_code", [200, 201])
def test_create_spectrum(
    client: SpectrumClient,
    create_request: CreateSpectrumRequest,
    status_code: int,
    httpx2_mock: respx.Router,
):
    route = httpx2_mock.post(f"{BASE_URL}/api/spectrum").respond(status_code=status_code)

    result = client.create_spectrum(create_request)

    assert result is None
    assert route.call_count == 1


def test_create_spectrum_sends_expected_body(
    client: SpectrumClient, create_request: CreateSpectrumRequest, httpx2_mock: respx.Router
):
    route = httpx2_mock.post(f"{BASE_URL}/api/spectrum").respond(status_code=200)

    client.create_spectrum(create_request)

    body = json.loads(route.calls.last.request.content)
    # Must be a JSON *object*, not a JSON-encoded string (no double encoding)
    assert body == {
        "name": "Sodium D-line",
        "wavelengths": [588.0, 589.0, 590.0],
        "intensities": [0.1, 1.0, 0.2],
    }


def test_create_spectrum_http_error(
    client: SpectrumClient, create_request: CreateSpectrumRequest, httpx2_mock: respx.Router
):
    httpx2_mock.post(f"{BASE_URL}/api/spectrum").respond(
        status_code=500,
        text="Internal server error",
    )

    with pytest.raises(
        SpectrumClientException,
        match="returned 500: Internal server error",
    ):
        client.create_spectrum(create_request)


def test_create_spectrum_validation_error_from_service(
    client: SpectrumClient, create_request: CreateSpectrumRequest, httpx2_mock: respx.Router
):
    httpx2_mock.post(f"{BASE_URL}/api/spectrum").respond(
        status_code=422,
        json={"detail": [{"msg": "field required"}]},
    )

    with pytest.raises(SpectrumClientException, match="field required") as exc_info:
        client.create_spectrum(create_request)

    assert exc_info.value.status_code == 422


def test_update_spectrum(
    client: SpectrumClient, domain_spectrum: Spectrum, httpx2_mock: respx.Router
):
    route = httpx2_mock.patch(f"{BASE_URL}/api/spectrum").respond(status_code=200)

    result = client.update_spectrum(domain_spectrum)

    assert result is None
    assert route.call_count == 1


def test_update_spectrum_sends_expected_body(
    client: SpectrumClient, domain_spectrum: Spectrum, httpx2_mock: respx.Router
):
    route = httpx2_mock.patch(f"{BASE_URL}/api/spectrum").respond(status_code=200)

    client.update_spectrum(domain_spectrum)

    body = json.loads(route.calls.last.request.content)
    assert body == {
        "id": SPECTRUM_ID,
        "name": "Updated spectrum",
        "wavelengths": [400.0, 500.0, 600.0],
        "intensities": [0.3, 0.6, 0.9],
    }


def test_update_spectrum_not_found(
    client: SpectrumClient, domain_spectrum: Spectrum, httpx2_mock: respx.Router
):
    httpx2_mock.patch(f"{BASE_URL}/api/spectrum").respond(
        status_code=404,
        json=NOT_FOUND_RESPONSE,
    )

    with pytest.raises(
        SpectrumNotFoundException,
        match=f"Spectrum '{SPECTRUM_ID}' not found",
    ) as exc_info:
        client.update_spectrum(domain_spectrum)

    assert exc_info.value.status_code == 404


def test_update_spectrum_bad_request(
    client: SpectrumClient, domain_spectrum: Spectrum, httpx2_mock: respx.Router
):
    httpx2_mock.patch(f"{BASE_URL}/api/spectrum").respond(
        status_code=400,
        json={"detail": "Missing id"},
    )

    with pytest.raises(SpectrumClientException, match="Missing id") as exc_info:
        client.update_spectrum(domain_spectrum)

    assert exc_info.value.status_code == 400


def test_update_spectrum_http_error(
    client: SpectrumClient, domain_spectrum: Spectrum, httpx2_mock: respx.Router
):
    httpx2_mock.patch(f"{BASE_URL}/api/spectrum").respond(
        status_code=500,
        text="Internal server error",
    )

    with pytest.raises(
        SpectrumClientException,
        match="returned 500: Internal server error",
    ):
        client.update_spectrum(domain_spectrum)


@pytest.mark.parametrize("status_code", [200, 204])
def test_delete_spectrum(client: SpectrumClient, status_code: int, httpx2_mock: respx.Router):
    route = httpx2_mock.delete(f"{BASE_URL}/api/spectrum/{SPECTRUM_ID}").respond(
        status_code=status_code,
    )

    result = client.delete_spectrum(SPECTRUM_ID)

    assert result is None
    assert route.call_count == 1


def test_delete_spectrum_not_found(client: SpectrumClient, httpx2_mock: respx.Router):
    httpx2_mock.delete(f"{BASE_URL}/api/spectrum/{SPECTRUM_ID}").respond(
        status_code=404, json=NOT_FOUND_RESPONSE
    )

    with pytest.raises(SpectrumNotFoundException, match="Spectrum not found") as exc_info:
        client.delete_spectrum(SPECTRUM_ID)

    assert exc_info.value.status_code == 404


def test_delete_spectrum_http_error(client: SpectrumClient, httpx2_mock: respx.Router):
    httpx2_mock.delete(f"{BASE_URL}/api/spectrum/{SPECTRUM_ID}").respond(
        status_code=500, text="Internal server error"
    )

    with pytest.raises(
        SpectrumClientException,
        match="returned 500: Internal server error",
    ):
        client.delete_spectrum(SPECTRUM_ID)


@pytest.mark.parametrize(
    "call",
    [
        lambda c: c.get_all_spectrums(),
        lambda c: c.get_spectrum(SPECTRUM_ID),
        lambda c: c.create_spectrum(
            CreateSpectrumRequest(name="x", wavelengths=[1.0], intensities=[1.0])
        ),
        lambda c: c.delete_spectrum(SPECTRUM_ID),
    ],
    ids=["get_all_spectrums", "get_spectrum", "create_spectrum", "delete_spectrum"],
)
def test_connection_error(client: SpectrumClient, call, httpx2_mock: respx.Router):
    httpx2_mock.route().mock(side_effect=httpx2.ConnectError("connection refused"))

    with pytest.raises(SpectrumClientConnectionException, match="connection refused") as exc_info:
        call(client)

    assert exc_info.value.status_code is None
    assert isinstance(exc_info.value.__cause__, httpx2.ConnectError)


def test_update_spectrum_connection_error(
    client: SpectrumClient, domain_spectrum: Spectrum, httpx2_mock: respx.Router
):
    httpx2_mock.route().mock(side_effect=httpx2.ConnectError("connection refused"))

    with pytest.raises(SpectrumClientConnectionException, match="connection refused"):
        client.update_spectrum(domain_spectrum)


def test_timeout_error(client: SpectrumClient, httpx2_mock: respx.Router):
    httpx2_mock.route().mock(side_effect=httpx2.ReadTimeout("too slow"))

    with pytest.raises(SpectrumClientTimeoutException, match="timed out"):
        client.get_all_spectrums()


def test_timeout_is_also_a_connection_error(client: SpectrumClient, httpx2_mock: respx.Router):
    httpx2_mock.route().mock(side_effect=httpx2.ConnectTimeout("too slow"))

    with pytest.raises(SpectrumClientConnectionException):
        client.get_all_spectrums()


def test_other_transport_error_is_wrapped(client: SpectrumClient, httpx2_mock: respx.Router):
    httpx2_mock.route().mock(side_effect=httpx2.RemoteProtocolError("protocol error"))

    with pytest.raises(SpectrumClientException):
        client.get_all_spectrums()


def test_invalid_url_is_wrapped():
    client = SpectrumClient("http://[invalid-host")

    with pytest.raises(SpectrumClientConnectionException):
        client.get_all_spectrums()


def test_base_url_trailing_slash_is_stripped():
    client = SpectrumClient(f"{BASE_URL}/")

    assert client.base_url == BASE_URL


def test_custom_timeout_is_stored():
    import math

    client = SpectrumClient(BASE_URL, timeout=2.5)

    assert math.isclose(client.timeout, 2.5, abs_tol=1e-9)
