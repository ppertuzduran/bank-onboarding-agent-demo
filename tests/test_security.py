from app.security import EncryptionService


def test_encrypt_decrypt_roundtrip() -> None:
    service = EncryptionService.from_settings()
    message = "contenido sensible del banco"
    token = service.encrypt_text(message)
    assert token != message.encode()
    assert service.decrypt_text(token) == message


def test_schemas_reject_invalid_product() -> None:
    import pytest
    from app.schemas import OnboardingRequest

    with pytest.raises(ValueError):
        OnboardingRequest(prospect_name="Juan Perez", document_id="1234567890", product="credito_hipotecario")


def test_schemas_reject_non_digit_document() -> None:
    import pytest
    from app.schemas import OnboardingRequest

    with pytest.raises(ValueError):
        OnboardingRequest(prospect_name="Juan Perez", document_id="12345abc", product="cuenta_ahorros")


def test_schemas_reject_name_with_digits() -> None:
    import pytest
    from app.schemas import OnboardingRequest

    with pytest.raises(ValueError):
        OnboardingRequest(prospect_name="Juan 2 Perez", document_id="1234567890", product="cuenta_ahorros")
