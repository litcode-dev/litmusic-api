import pytest
import uuid
from pydantic import ValidationError
from app.schemas.purchase import CheckoutRequest


def test_checkout_requires_exactly_one_product():
    with pytest.raises(ValidationError):
        CheckoutRequest()  # neither provided


def test_checkout_rejects_both_products():
    with pytest.raises(ValidationError):
        CheckoutRequest(loop_id=uuid.uuid4(), stem_pack_id=uuid.uuid4())


def test_checkout_accepts_loop_only():
    req = CheckoutRequest(loop_id=uuid.uuid4())
    assert req.stem_pack_id is None


def test_checkout_accepts_stem_pack_only():
    req = CheckoutRequest(stem_pack_id=uuid.uuid4())
    assert req.loop_id is None


# append at end of file
from app.exceptions import NotFoundError, UnauthorizedError, EntitlementError


def test_not_found_error_status():
    err = NotFoundError("loop not found")
    assert err.status_code == 404
    assert err.message == "loop not found"


def test_entitlement_error_default_message():
    err = EntitlementError()
    assert err.status_code == 403
    assert "Purchase required" in err.message
