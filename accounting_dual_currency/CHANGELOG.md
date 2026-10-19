# Changelog

## 19.0.1.3.0 — 2026-10-19

- **Tasa manual en documentos de cliente y asientos:** las facturas, notas de crédito,
  recibos y pagos de clientes, además de los asientos contables manuales, pueden usar una
  tasa manual. Se permite capturarla a los administradores de Contabilidad y de Ajustes;
  el servidor aplica los mismos permisos que los formularios.
- **Consistencia de asientos y conciliación:** al cambiar la tasa de un asiento en
  borrador se recalculan sus apuntes en moneda de referencia; se rechazan terceras monedas
  y cambios que dejan el asiento descuadrado. Las reversas conservan la tasa. En las
  conciliaciones, la tasa del pago tiene prioridad sobre la de la factura y la del asiento.
- **Importes de referencia:** los apuntes de un asiento expresados en la moneda de
  referencia conservan como tal el importe en moneda que indica el propio apunte. Esto
  permite que asientos originados en otros módulos, como las retenciones, mantengan su
  tasa contable sin que este módulo dependa de ellos.
- **Motivo:** extender la captura de tasas manuales a clientes y asientos sin perder la
  coherencia de débitos, créditos, reversas, conciliaciones y reportes, y proteger la
  edición de la tasa también fuera de la interfaz.
