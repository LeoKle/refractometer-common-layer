import json

import httpx2
import pytest
import respx

from refractometer_common.image.image import Image
from refractometer_common.image.image_client import ImageClient
from refractometer_common.image.image_client_interface import (
    CreateImageRequest,
    ImageClientConnectionException,
    ImageClientException,
    ImageClientInvalidResponseException,
    ImageClientTimeoutException,
    ImageNotFoundException,
)

BASE_URL = "http://image-service"

IMAGE_ID = "image-123"
NEW_IMAGE_ID = "6f1c2f8e-2b5c-4d0e-9a57-0d6f3a1d9c11"

IMAGE_RESPONSE = {
    "values": [[1.0, 2.0], [3.0, 4.0]],
    "shape": [2, 2],
}

NOT_FOUND_RESPONSE = {"detail": "Image not found"}


@pytest.fixture
def client() -> ImageClient:
    return ImageClient(BASE_URL)


@pytest.fixture
def create_request() -> CreateImageRequest:
    return CreateImageRequest(values=[[1.0, 2.0], [3.0, 4.0]], shape=(2, 2))


def test_get_image(client: ImageClient, httpx2_mock: respx.Router):
    httpx2_mock.get(f"{BASE_URL}/api/result/{IMAGE_ID}").respond(
        status_code=200,
        json=IMAGE_RESPONSE,
    )

    image = client.get_image(IMAGE_ID)

    assert isinstance(image, Image)
    assert image.values == IMAGE_RESPONSE["values"]
    assert image.shape == (2, 2)


def test_get_image_empty_matrix(client: ImageClient, httpx2_mock: respx.Router):
    httpx2_mock.get(f"{BASE_URL}/api/result/{IMAGE_ID}").respond(
        status_code=200,
        json={"values": [], "shape": [0, 0]},
    )

    image = client.get_image(IMAGE_ID)

    assert image.values == []
    assert image.shape == (0, 0)


def test_get_image_with_trailing_slash_base_url(httpx2_mock: respx.Router):
    client = ImageClient(f"{BASE_URL}/")
    httpx2_mock.get(f"{BASE_URL}/api/result/{IMAGE_ID}").respond(
        status_code=200,
        json=IMAGE_RESPONSE,
    )

    assert client.get_image(IMAGE_ID).shape == (2, 2)


def test_get_image_not_found(client: ImageClient, httpx2_mock: respx.Router):
    httpx2_mock.get(f"{BASE_URL}/api/result/{IMAGE_ID}").respond(
        status_code=404,
        json=NOT_FOUND_RESPONSE,
    )

    with pytest.raises(
        ImageNotFoundException,
        match=f"Image '{IMAGE_ID}' not found",
    ) as exc_info:
        client.get_image(IMAGE_ID)

    assert exc_info.value.status_code == 404


def test_get_image_not_found_is_client_exception(client: ImageClient, httpx2_mock: respx.Router):
    httpx2_mock.get(f"{BASE_URL}/api/result/{IMAGE_ID}").respond(
        status_code=404,
        json=NOT_FOUND_RESPONSE,
    )

    with pytest.raises(ImageClientException):
        client.get_image(IMAGE_ID)


@pytest.mark.parametrize("status_code", [400, 401, 403, 500, 502, 503])
def test_get_image_http_error(client: ImageClient, status_code: int, httpx2_mock: respx.Router):
    httpx2_mock.get(f"{BASE_URL}/api/result/{IMAGE_ID}").respond(
        status_code=status_code,
        text="Something went wrong",
    )

    with pytest.raises(
        ImageClientException,
        match=f"returned {status_code}: Something went wrong",
    ) as exc_info:
        client.get_image(IMAGE_ID)

    assert not isinstance(exc_info.value, ImageNotFoundException)
    assert exc_info.value.status_code == status_code


def test_get_image_http_error_uses_detail_field(client: ImageClient, httpx2_mock: respx.Router):
    httpx2_mock.get(f"{BASE_URL}/api/result/{IMAGE_ID}").respond(
        status_code=500,
        json={"detail": "database exploded"},
    )

    with pytest.raises(ImageClientException, match="returned 500: database exploded"):
        client.get_image(IMAGE_ID)


def test_get_image_http_error_json_without_detail_falls_back_to_text(
    client: ImageClient, httpx2_mock: respx.Router
):
    httpx2_mock.get(f"{BASE_URL}/api/result/{IMAGE_ID}").respond(
        status_code=500,
        json={"error": "boom"},
    )

    with pytest.raises(ImageClientException, match="boom"):
        client.get_image(IMAGE_ID)


def test_get_image_invalid_json(client: ImageClient, httpx2_mock: respx.Router):
    httpx2_mock.get(f"{BASE_URL}/api/result/{IMAGE_ID}").respond(
        status_code=200,
        text="<html>nope</html>",
    )

    with pytest.raises(ImageClientInvalidResponseException, match="not valid JSON") as exc_info:
        client.get_image(IMAGE_ID)

    assert exc_info.value.status_code == 200


@pytest.mark.parametrize(
    "body",
    [
        {"not": "an image"},
        {"values": [[1.0]]},  # missing shape
        {"shape": [1, 1]},  # missing values
        {"values": "nope", "shape": [1, 1]},  # wrong type for values
        {"values": [["a", "b"]], "shape": [1, 2]},  # non-numeric cells
        {"values": [[1.0]], "shape": [1]},  # wrong shape arity
        {"values": [[1.0]], "shape": "1x1"},  # wrong type for shape
        [IMAGE_RESPONSE],  # list instead of object
        None,
    ],
    ids=[
        "unrelated_object",
        "missing_shape",
        "missing_values",
        "values_wrong_type",
        "values_non_numeric",
        "shape_wrong_arity",
        "shape_wrong_type",
        "list_instead_of_object",
        "null",
    ],
)
def test_get_image_unprocessable(client: ImageClient, body, httpx2_mock: respx.Router):
    httpx2_mock.get(f"{BASE_URL}/api/result/{IMAGE_ID}").respond(
        status_code=200,
        json=body,
    )

    with pytest.raises(ImageClientInvalidResponseException) as exc_info:
        client.get_image(IMAGE_ID)

    assert exc_info.value.status_code == 200


@pytest.mark.parametrize("status_code", [200, 201])
def test_post_image(
    client: ImageClient,
    create_request: CreateImageRequest,
    status_code: int,
    httpx2_mock: respx.Router,
):
    httpx2_mock.post(f"{BASE_URL}/api/result").respond(
        status_code=status_code,
        json={"id": NEW_IMAGE_ID},
    )

    assert client.post_image(create_request) == NEW_IMAGE_ID


def test_post_image_sends_expected_payload(
    client: ImageClient,
    create_request: CreateImageRequest,
    httpx2_mock: respx.Router,
):
    route = httpx2_mock.post(f"{BASE_URL}/api/result").respond(
        status_code=200,
        json={"id": NEW_IMAGE_ID},
    )

    client.post_image(create_request)

    assert route.call_count == 1
    sent = route.calls.last.request
    assert json.loads(sent.content) == {
        "values": [[1.0, 2.0], [3.0, 4.0]],
        "shape": [2, 2],
    }


def test_post_image_with_trailing_slash_base_url(
    create_request: CreateImageRequest, httpx2_mock: respx.Router
):
    client = ImageClient(f"{BASE_URL}/")
    httpx2_mock.post(f"{BASE_URL}/api/result").respond(
        status_code=200,
        json={"id": NEW_IMAGE_ID},
    )

    assert client.post_image(create_request) == NEW_IMAGE_ID


@pytest.mark.parametrize("status_code", [400, 401, 403, 500, 502, 503])
def test_post_image_http_error(
    client: ImageClient,
    create_request: CreateImageRequest,
    status_code: int,
    httpx2_mock: respx.Router,
):
    httpx2_mock.post(f"{BASE_URL}/api/result").respond(
        status_code=status_code,
        text="Something went wrong",
    )

    with pytest.raises(
        ImageClientException,
    ) as exc_info:
        client.post_image(create_request)

    assert exc_info.value.status_code == status_code


def test_post_image_validation_error_from_service(
    client: ImageClient, create_request: CreateImageRequest, httpx2_mock: respx.Router
):
    httpx2_mock.post(f"{BASE_URL}/api/result").respond(
        status_code=422,
        json={"detail": [{"msg": "field required"}]},
    )

    with pytest.raises(ImageClientException, match="field required") as exc_info:
        client.post_image(create_request)

    assert exc_info.value.status_code == 422


def test_post_image_not_found(
    client: ImageClient, create_request: CreateImageRequest, httpx2_mock: respx.Router
):
    httpx2_mock.post(f"{BASE_URL}/api/result").respond(
        status_code=404,
        json=NOT_FOUND_RESPONSE,
    )

    with pytest.raises(ImageNotFoundException) as exc_info:
        client.post_image(create_request)

    assert exc_info.value.status_code == 404


def test_post_image_invalid_json(
    client: ImageClient, create_request: CreateImageRequest, httpx2_mock: respx.Router
):
    httpx2_mock.post(f"{BASE_URL}/api/result").respond(
        status_code=200,
        text="<html>nope</html>",
    )

    with pytest.raises(ImageClientInvalidResponseException, match="not valid JSON"):
        client.post_image(create_request)


@pytest.mark.parametrize(
    "body",
    [
        {"not": "valid"},
        {"id": None},
        {"id": ["a", "list"]},
        [],
        None,
    ],
    ids=["missing_id", "null_id", "id_wrong_type", "empty_list", "null"],
)
def test_post_image_unprocessable_response(
    client: ImageClient,
    create_request: CreateImageRequest,
    body,
    httpx2_mock: respx.Router,
):
    httpx2_mock.post(f"{BASE_URL}/api/result").respond(
        status_code=200,
        json=body,
    )

    with pytest.raises(ImageClientInvalidResponseException) as exc_info:
        client.post_image(create_request)

    assert exc_info.value.status_code == 200


@pytest.mark.filterwarnings("ignore")  # model_construct + model_dump emits serializer warnings
def test_post_image_invalid_request_is_wrapped(client: ImageClient):
    # model_construct skips validation, so we can build a request that is invalid
    # when it gets re-validated into the API DTO. No HTTP call must be made.
    bad_request = CreateImageRequest.model_construct(values="not-a-matrix", shape=(1, 1))

    with pytest.raises(ImageClientException, match="Invalid image create request") as exc_info:
        client.post_image(bad_request)

    assert exc_info.value.status_code is None
    assert not isinstance(exc_info.value, ImageClientInvalidResponseException)


CALLS = [
    lambda c: c.get_image(IMAGE_ID),
    lambda c: c.post_image(CreateImageRequest(values=[[1.0]], shape=(1, 1))),
]
CALL_IDS = ["get_image", "post_image"]


@pytest.mark.parametrize("call", CALLS, ids=CALL_IDS)
def test_connection_error(client: ImageClient, call, httpx2_mock: respx.Router):
    httpx2_mock.route().mock(side_effect=httpx2.ConnectError("connection refused"))

    with pytest.raises(ImageClientConnectionException, match="connection refused") as exc_info:
        call(client)

    assert exc_info.value.status_code is None
    assert isinstance(exc_info.value.__cause__, httpx2.ConnectError)


@pytest.mark.parametrize("call", CALLS, ids=CALL_IDS)
def test_timeout_error(client: ImageClient, call, httpx2_mock: respx.Router):
    httpx2_mock.route().mock(side_effect=httpx2.ReadTimeout("too slow"))

    with pytest.raises(ImageClientTimeoutException, match="timed out") as exc_info:
        call(client)

    assert exc_info.value.status_code is None
    assert isinstance(exc_info.value.__cause__, httpx2.ReadTimeout)


def test_timeout_message_contains_configured_timeout(httpx2_mock: respx.Router):
    client = ImageClient(BASE_URL, timeout=2.5)
    httpx2_mock.route().mock(side_effect=httpx2.ReadTimeout("too slow"))

    with pytest.raises(ImageClientTimeoutException, match=r"2\.5s"):
        client.get_image(IMAGE_ID)


@pytest.mark.parametrize(
    "error",
    [httpx2.ConnectTimeout("too slow"), httpx2.ReadTimeout("too slow"), httpx2.PoolTimeout("busy")],
    ids=["connect_timeout", "read_timeout", "pool_timeout"],
)
def test_timeout_is_also_a_connection_error(
    client: ImageClient, error: Exception, httpx2_mock: respx.Router
):
    httpx2_mock.route().mock(side_effect=error)

    with pytest.raises(ImageClientConnectionException):
        client.get_image(IMAGE_ID)


@pytest.mark.parametrize(
    "error",
    [
        httpx2.RemoteProtocolError("protocol broke"),
        httpx2.ReadError("read failed"),
        httpx2.WriteError("write failed"),
        httpx2.UnsupportedProtocol("bad scheme"),
    ],
    ids=["remote_protocol", "read_error", "write_error", "unsupported_protocol"],
)
@pytest.mark.parametrize("call", CALLS, ids=CALL_IDS)
def test_other_transport_error_is_wrapped(
    client: ImageClient, call, error: Exception, httpx2_mock: respx.Router
):
    httpx2_mock.route().mock(side_effect=error)

    with pytest.raises(ImageClientException) as exc_info:
        call(client)

    assert exc_info.value.__cause__ is error


@pytest.mark.parametrize("call", CALLS, ids=CALL_IDS)
def test_invalid_url_is_wrapped(call):
    client = ImageClient("http://[invalid-host")

    with pytest.raises(ImageClientConnectionException):
        call(client)


def test_base_url_trailing_slash_is_stripped():
    client = ImageClient(f"{BASE_URL}/")

    assert client.base_url == BASE_URL


@pytest.mark.parametrize(
    "exception_type",
    [
        ImageClientConnectionException,
        ImageClientTimeoutException,
        ImageNotFoundException,
        ImageClientInvalidResponseException,
    ],
)
def test_all_exceptions_derive_from_base_exception(exception_type: type[Exception]):
    assert issubclass(exception_type, ImageClientException)


def test_timeout_exception_derives_from_connection_exception():
    assert issubclass(ImageClientTimeoutException, ImageClientConnectionException)


def test_exception_status_code_defaults_to_none():
    assert ImageClientException("boom").status_code is None


def test_exception_keeps_status_code_and_message():
    ex = ImageClientException("boom", 418)

    assert str(ex) == "boom"
    assert ex.status_code == 418
