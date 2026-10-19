# Changelog

## 19.0.1.0.1 — 2026-10-19

- **Base de la retención municipal:** la conversión a moneda de la compañía usa la tasa
  estándar de la factura de origen, en vez de consultar `rate_date` y redondear una tasa
  buscada por fecha.
- **Asiento de retención:** los apuntes llevan la moneda y el importe en moneda de la
  factura, calculado con su tasa, para conservar la valoración de origen al publicar el
  comprobante.
- **Pruebas:** se valida la tasa de factura frente a una tasa de tabla distinta, tanto
  para facturas en moneda extranjera como en moneda de compañía; se corrige el RIF de un
  fixture existente para ajustarlo al formato que valida `l10n_ve_full`.
- **Motivo:** asegurar que la retención municipal herede la tasa de la factura y evitar
  errores de conversión en Odoo 19. La reutilización de la función estándar añadida en
  `l10n_ve_full` no introduce dependencias nuevas: este módulo ya depende de él.
