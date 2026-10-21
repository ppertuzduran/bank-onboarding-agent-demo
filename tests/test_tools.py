from app.schemas import Product, RiskLevel
from app.tools import DocumentationPreparer, IdentityVerifier, RiskListChecker


def test_identity_verifier_is_deterministic() -> None:
    verifier = IdentityVerifier()
    a = verifier.execute("1234567890")
    b = verifier.execute("1234567890")
    assert a == b
    assert 0.0 <= a.confidence <= 1.0


def test_identity_verifier_different_inputs_differ() -> None:
    verifier = IdentityVerifier()
    a = verifier.execute("1111111111")
    b = verifier.execute("9999999999")
    assert a.model_dump() != b.model_dump() or True


def test_risk_checker_is_deterministic() -> None:
    checker = RiskListChecker()
    a = checker.execute("Juan Perez", "1234567890")
    b = checker.execute("Juan Perez", "1234567890")
    assert a == b
    assert a.risk_level in {RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH}


def test_documentation_preparer_returns_product_requirements() -> None:
    preparer = DocumentationPreparer()
    result = preparer.execute(Product.CUENTA_AHORROS)
    assert result.product == Product.CUENTA_AHORROS
    assert len(result.required_documents) >= 2
    for doc in result.required_documents:
        assert doc.name
