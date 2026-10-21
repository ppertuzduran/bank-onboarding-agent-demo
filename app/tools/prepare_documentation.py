"""Mock de preparación documental: dado el producto, devuelve requisitos documentales."""

from __future__ import annotations

from app.schemas import DocumentPreparationResult, Product, RequiredDocument


class DocumentationPreparer:
    """Devuelve requisitos documentales por producto.

    En producción esto consulta un servicio de catálogo documental.
    """

    _REQUIREMENTS: dict[Product, list[RequiredDocument]] = {
        Product.CUENTA_AHORROS: [
            RequiredDocument(name="Cédula de ciudadanía (frente y reverso)"),
            RequiredDocument(name="Comprobante de domicilio (no mayor a 3 meses)"),
            RequiredDocument(name="Declaración de origen de fondos", mandatory=False,
                             reason="Requerido solo si el depósito inicial supera COP 10M"),
        ],
        Product.CUENTA_CORRIENTE: [
            RequiredDocument(name="Cédula de ciudadanía (frente y reverso)"),
            RequiredDocument(name="Comprobante de domicilio (no mayor a 3 meses)"),
            RequiredDocument(name="Certificado de ingresos (últimos 2 meses)"),
            RequiredDocument(name="Declaración de origen de fondos"),
        ],
        Product.TARJETA_CREDITO: [
            RequiredDocument(name="Cédula de ciudadanía (frente y reverso)"),
            RequiredDocument(name="Certificado laboral (no mayor a 30 días)"),
            RequiredDocument(name="Comprobantes de pago (últimos 3 meses)"),
            RequiredDocument(name="Declaración de renta (último año)", mandatory=False,
                             reason="Requerida para cupos superiores a COP 20M"),
        ],
        Product.CREDITO_CONSUMO: [
            RequiredDocument(name="Cédula de ciudadanía (frente y reverso)"),
            RequiredDocument(name="Certificado laboral (no mayor a 30 días)"),
            RequiredDocument(name="Comprobantes de pago (últimos 3 meses)"),
            RequiredDocument(name="Declaración de renta (último año)"),
            RequiredDocument(name="Referencias comerciales (2)"),
        ],
    }

    def execute(self, product: Product, client_data: dict[str, str] | None = None) -> DocumentPreparationResult:
        docs = list(self._REQUIREMENTS.get(product, []))
        return DocumentPreparationResult(product=product, required_documents=docs)
