"""Genera documentos sintéticos de política bancaria en markdown.

Siguiendo la guía del prompt: párrafos cortos, instrucciones claras, no ambiguos,
con títulos y subtítulos que permiten chunking por sección.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.config import get_settings


@dataclass(frozen=True)
class SyntheticDoc:
    filename: str
    product: str
    content: str


_DOCS: list[SyntheticDoc] = [
    SyntheticDoc(
        filename="politica_cuenta_ahorros.md",
        product="cuenta_ahorros",
        content="""# Política de Apertura — Cuenta de Ahorros

## Elegibilidad del cliente
El cliente debe ser mayor de 18 años y residente en el país. Se admite ciudadano nacional o extranjero con permiso de residencia vigente.

## Documentación mínima
Se requieren: cédula de ciudadanía por ambas caras y comprobante de domicilio con antigüedad no mayor a tres meses.

## Depósito inicial
El depósito inicial mínimo es de COP 50.000. No existe depósito máximo para la apertura.

## Declaración de origen de fondos
Si el depósito inicial supera COP 10.000.000, el cliente debe firmar declaración de origen de fondos antes de la activación.

## Tiempos de activación
La activación de la cuenta ocurre en un máximo de 24 horas hábiles tras recibir toda la documentación válida.

## Causales de rechazo
Se rechaza la apertura si el cliente aparece en lista de alto riesgo, si la identidad no se puede verificar, o si la documentación está incompleta tras dos intentos.
""",
    ),
    SyntheticDoc(
        filename="politica_cuenta_corriente.md",
        product="cuenta_corriente",
        content="""# Política de Apertura — Cuenta Corriente

## Elegibilidad del cliente
Requiere mayoría de edad y comprobación de ingresos recurrentes mensuales iguales o superiores a dos salarios mínimos.

## Documentación mínima
Cédula de ciudadanía, comprobante de domicilio con antigüedad no mayor a tres meses, certificado de ingresos de los últimos dos meses y declaración de origen de fondos.

## Validación de referencias
Se valida al menos una referencia bancaria o comercial activa. Si el cliente es nuevo en el sistema financiero, se exige referencia personal verificable.

## Sobregiro
El cupo de sobregiro se otorga únicamente tras tres meses de historial activo con movimientos recurrentes.

## Comisiones
La cuenta corriente aplica cuota de manejo mensual. El valor vigente se informa al cliente antes de la firma del contrato.

## Causales de rechazo
Ingresos insuficientes, referencias no verificables, coincidencia en listas de alto riesgo o documentación falsa generan rechazo automático.
""",
    ),
    SyntheticDoc(
        filename="politica_tarjeta_credito.md",
        product="tarjeta_credito",
        content="""# Política de Apertura — Tarjeta de Crédito

## Elegibilidad del cliente
Cliente mayor de 18 años con ingresos demostrables y score de crédito dentro de los umbrales internos del banco.

## Documentación mínima
Cédula de ciudadanía, certificado laboral con antigüedad no mayor a 30 días y comprobantes de pago de los últimos tres meses.

## Score mínimo
El score crediticio mínimo exigido es 580 en el buró de crédito consultado. Clientes por debajo requieren revisión manual.

## Cupo inicial
El cupo inicial se calcula como el 30% de los ingresos mensuales demostrables. Puede incrementarse tras seis meses de uso responsable.

## Declaración de renta
Para cupos solicitados superiores a COP 20.000.000 se exige la última declaración de renta.

## Causales de rechazo
Score por debajo del mínimo, mora activa en el sistema financiero o coincidencia en listas de alto riesgo generan rechazo.
""",
    ),
    SyntheticDoc(
        filename="politica_credito_consumo.md",
        product="credito_consumo",
        content="""# Política de Apertura — Crédito de Consumo

## Elegibilidad del cliente
Mayor de 18 años con antigüedad laboral de al menos seis meses y capacidad de pago demostrable.

## Documentación mínima
Cédula de ciudadanía, certificado laboral reciente, comprobantes de pago, declaración de renta del último año y dos referencias comerciales.

## Monto y plazo
Monto mínimo COP 1.000.000, máximo COP 100.000.000. Plazos entre 12 y 60 meses según perfil.

## Garantías
Para montos superiores a COP 50.000.000 se requiere codeudor con capacidad de pago verificable.

## Tasa de interés
La tasa es fija y se comunica al cliente antes de la firma del pagaré. No se aplican cargos ocultos.

## Causales de rechazo
Capacidad de pago insuficiente, mora activa, referencias no verificables o coincidencia en listas de alto riesgo generan rechazo.
""",
    ),
    SyntheticDoc(
        filename="politica_kyc_general.md",
        product="general",
        content="""# Política General KYC — Conocimiento del Cliente

## Alcance
Esta política aplica a todos los productos del banco: cuentas de depósito, tarjetas y productos de crédito.

## Verificación de identidad
Se verifica la identidad del cliente mediante proveedor externo con comparación biométrica (selfie vs documento). Confianza mínima aceptable: 0.80.

## Consulta de listas de riesgo
Se consultan OFAC, listas de personas políticamente expuestas (PEP) y lista interna del banco antes de activar cualquier producto.

## Niveles de riesgo
Riesgo bajo: continuar flujo. Riesgo medio: continuar flujo con alerta registrada. Riesgo alto: escalar a cumplimiento y suspender activación.

## Retención documental
Toda la documentación del onboarding se almacena cifrada por un periodo mínimo de diez años.

## Escalamiento
Si cualquier verificación es ambigua o falla, el caso se escala a un oficial de cumplimiento con una propuesta de resolución clara.
""",
    ),
]


def main() -> int:
    settings = get_settings()
    out_dir: Path = settings.docs_plain_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    for doc in _DOCS:
        (out_dir / doc.filename).write_text(doc.content, encoding="utf-8")
    print(f"Generados {len(_DOCS)} documentos en {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
