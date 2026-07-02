_TRANSCRIBE_PROMPT = (
    "Transcribe el siguiente mensaje de voz sobre finanzas personales "
    "al español. Devuelve SOLO el texto transcrito, sin explicaciones."
)

_RECEIPT_PROMPT = "Extrae los datos de este recibo de compra."

_STATEMENT_PROMPT = (
    "Extrae todas las transacciones de este extracto bancario. "
    "Los gastos son cantidades negativas, los ingresos son positivas.\n\n"
    "Clasifica cada transacción en una categoría (como 'Alimentación', "
    "'Transporte', 'Salario', 'Hipoteca', 'Subscripciones', "
    "'Salud', 'Educación', 'Restaurante', 'Supermercado', "
    "'Seguros', 'Ahorros', etc.) basándote en la descripción "
    "o el nombre del beneficiario.\n\n"
    "Devuelve SOLO las transacciones, sin resúmenes ni explicaciones adicionales."
)
