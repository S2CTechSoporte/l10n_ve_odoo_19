# Changelog

## 19.0.1.1.1 — 2026-10-19

- **Tasa de la factura en las retenciones de IVA e ISLR:** las bases, importes retenidos
  y totales del comprobante ISLR se convierten con la `invoice_currency_rate` estándar
  de la factura de origen, en lugar de volver a buscar una tasa por la fecha de la
  retención.
- **Asientos de retención:** los apuntes de IVA e ISLR se expresan en la moneda de la
  factura y llevan su importe en moneda calculado con esa misma tasa. Al conciliarlos con
  la factura, no se genera una diferencia de cambio por usar una tasa distinta.
- **Reporte ISLR:** el total del documento usa el mismo cálculo por tasa de factura, en
  vez de depender del campo `currency_bs_rate`, que no está definido por este módulo.
- **Motivo:** la retención nace de la factura y debe heredar su tasa efectiva —manual o
  estándar— para que sus importes y la conciliación coincidan. La implementación usa
  campos estándar de Odoo y no añade una dependencia de `accounting_dual_currency`, por
  lo que ambos módulos siguen siendo instalables por separado.
