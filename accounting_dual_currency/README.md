# Contabilidad en doble moneda

`accounting_dual_currency` añade una capa de moneda de referencia a la aplicación de
Contabilidad de Odoo 19.0. No depende de una localización de país: la moneda de la
compañía puede ser cualquier moneda configurada en Odoo, y la moneda de referencia se
selecciona de forma independiente para cada compañía. La demo usa EUR/USD; la matriz
principal de pruebas contables usa las monedas de la compañía y de referencia (CCY/USD).

## Alcance

- Añade una moneda de referencia a nivel de compañía. Se sugiere USD cuando la moneda de
  la compañía no es USD; las compañías que usan USD seleccionan su propia moneda de
  referencia.
- Muestra los totales, impuestos e importes adeudados de las facturas en la moneda de
  referencia cuando el documento usa la moneda de la compañía, o en la moneda de la
  compañía cuando el documento está en moneda extranjera. Los apuntes contables exponen
  importes de referencia, y los formularios de pago muestran los importes en ambas
  monedas.
- Calcula los importes de referencia conciliados en cada fecha de conciliación.
- Añade un selector de compañía/moneda de referencia a los reportes Cuenta por cobrar
  vencida (Aged Receivable) y Cuenta por pagar vencida (Aged Payable).
- Añade la misma elección de moneda a Libro mayor de la empresa (Partner Ledger), Balance
  general (Balance Sheet) y Estado de cuenta del cliente (Customer Statement). Usa los
  importes almacenados en moneda de referencia de los apuntes contables para los totales
  y las líneas de detalle.
- Abre el Estado de cuenta del cliente en la moneda seleccionada en Cuenta por cobrar
  vencida o Cuenta por pagar vencida. Si se abre directamente desde la lista de clientes,
  usa por defecto la moneda de la compañía.
- Conserva la tasa original de la factura en las notas de crédito en moneda de la
  compañía creadas a partir de una factura.
- Muestra un USD expresado en la moneda contraparte en la barra superior, justo antes del
  selector de compañía.

## Configuración

1. Abre los ajustes de Contabilidad.
2. Confirma la moneda de la compañía antes de registrar asientos contables.
3. Selecciona la moneda de referencia en **Dualidad de moneda**.
4. Configura tasas de cambio deterministas (definidas manualmente) o en vivo mediante
   las tasas de cambio estándar de Odoo. Mantén disponibles las tasas de USD aunque ni
   la compañía ni la moneda de referencia sean USD, porque la barra superior siempre
   cotiza USD.

El manifiesto depende de `account_reports` para sus extensiones de reportes y de
`currency_rate_live` para el actualizador de tasas estándar de Odoo basado en
proveedores. Odoo instala ambas dependencias junto con este módulo. Configura un
proveedor en los ajustes de Contabilidad para usar la acción **Actualizar ahora** de la
barra superior. Esta acción actualiza todas las monedas activas que admite ese
proveedor, no solo la moneda de referencia. No activa actualizaciones programadas ni
cambia el intervalo configurado.

El módulo no cambia la moneda de una compañía existente, porque Odoo debe proteger los
datos contables registrados. En las compañías que ya usan USD, elige explícitamente una
moneda de referencia distinta. Instalar el módulo no activa monedas adicionales ni
altera la moneda por defecto de ningún país.

## Uso

Los formularios de factura, de asiento contable y de pago muestran una **Tasa USD** de
solo lectura cuando USD es la moneda de la compañía o la de referencia. Esta
presentación se deriva únicamente de la `conversion_rate` guardada en el documento: nunca
selecciona una fecha ni consulta una tasa de cambio. Con USD como moneda de referencia, el
valor guardado ya expresa el costo de un dólar en la moneda de la compañía. Con una
compañía en USD y una moneda de referencia distinta, su inverso expresa el costo de un
dólar en esa moneda de referencia. La moneda de transacción de la factura o del pago no
afecta a esta presentación.

Si ninguna de las monedas configuradas es USD, o no hay moneda de referencia configurada,
los formularios conservan el valor guardado bajo **Tasa de referencia**, con formato de la
moneda de la compañía. Una cotización en USD no puede reconstruirse solo a partir de esa
tasa guardada. La `conversion_rate` original y los campos de tasa de referencia de los
apuntes contables conservan su significado de unidades de la compañía por unidad de la
moneda de referencia.

La cotización de la barra superior es independiente de esas tasas del documento: siempre
empieza con **USD** y expresa el valor de un dólar. La contraparte es la moneda de la
compañía, salvo que la compañía use USD; en ese caso, es la moneda de referencia. Si
ninguna de las monedas configuradas es USD, se usa la moneda de la compañía. El importe
sigue el idioma del usuario, y la precisión decimal y la posición del símbolo de la
moneda contraparte.

| Moneda de la compañía | Moneda de referencia | Contraparte en la barra superior |
|---|---|---|
| USD | EUR | EUR |
| EUR | USD, GBP o EUR | EUR |
| USD | USD | USD, con cotización unitaria |
| Cualquiera | Sin configurar | El elemento de la barra superior se oculta |

La cotización lee las tasas almacenadas para la fecha actual cuando se carga el
componente, cuando se abre su desplegable o cuando cambia la compañía activa. Leer la
cotización no consulta a ningún proveedor de tasas. **Actualizar ahora** actualiza los
registros compartidos de tasas de cambio de Odoo y después recarga la cotización; no
redefine las tasas de referencia de los documentos ni sus reglas de fecha.

En los reportes Cuenta por cobrar vencida, Cuenta por pagar vencida, Libro mayor de la
empresa, Balance general o Estado de cuenta del cliente, selecciona la moneda de la
compañía o la de referencia en el selector de moneda. Los importes, saldos, saldos
iniciales y apuntes conciliados del Libro mayor de la empresa y del Estado de cuenta del
cliente, así como los totales de cuentas y de grupos del Balance general, usan la moneda
seleccionada. La columna Importe en moneda del documento original sigue en su moneda de
transacción. Desde una fila de contacto de un reporte de cuentas vencidas, el Estado de cuenta
del cliente hereda la moneda seleccionada para clientes y proveedores; después, el
selector puede cambiarla. Cuando las compañías seleccionadas no comparten la misma moneda
de la compañía y la misma moneda de referencia, el selector se oculta en el Libro mayor
de la empresa, el Balance general y el Estado de cuenta del cliente.

## Diseño técnico

- `res.company.secondary_currency_id` almacena la moneda de referencia.
- [`res.company`](models/res_company.py) expone los datos de la barra superior de la
  compañía activa convirtiendo una unidad de `base.USD` a la moneda contraparte con
  `_convert` nativo y un formato monetario sensible al idioma. La cotización usa la fecha
  actual del contexto del usuario. Se conservan la selección nativa de tasas de la
  compañía y de la compañía raíz, así como los respaldos nativos cuando falta una tasa.
  Sin moneda de referencia no hay elemento en la barra superior.
- El [componente de la barra superior](static/src/components/secondary_currency_menu/secondary_currency_menu.js)
  se actualiza al abrir su desplegable, después de una actualización y al cambiar la
  compañía activa. Una extensión de la barra superior lo ancla antes del selector de
  compañía, porque Studio y ese selector usan la misma secuencia del systray. Los iconos
  de billete y de actualización manual usan la variable nativa de Odoo `--link-color` para
  seguir el tema claro u oscuro sin colores fijos.
- `update_secondary_currency_rates()` autoriza solo a los administradores de Ajustes y a
  los responsables de Contabilidad, verifica el acceso a la compañía activa y después
  eleva los permisos únicamente para la llamada transitoria de ajustes a
  `res.config.settings.update_currency_rates_manually()`. Las tasas pertenecen a la
  compañía raíz en el caso de las sucursales. Los demás usuarios pueden ver la tasa, pero
  no actualizarla. Los errores del proveedor se propagan mediante el diálogo de error
  normal de Odoo.
- `account.move` almacena la tasa de referencia y expone los totales de la moneda de la
  compañía y de referencia, así como los widgets de pagos convertidos. Su formulario usa
  campos monetarios de presentación independientes para orientar esa tasa guardada hacia
  USD sin modificarla.
- `account.payment` usa la misma presentación de tasa guardada en su formulario.
- `account.move.line` almacena los campos auxiliares convertidos de débito, crédito, saldo,
  precio y residual.
- `account.partial.reconcile.amount_secondary_currency` usa el importe conciliado del lado
  de la moneda de referencia cuando existe; en caso contrario, convierte el importe en
  moneda de la compañía en la fecha `max_date`.
- `account.aged.partner.balance.report.handler` reconstruye los tramos de antigüedad a
  partir del saldo de referencia almacenado y de las conciliaciones hasta la fecha de corte
  del reporte. Su acción `open_customer_statement` pasa la moneda seleccionada a las
  opciones del Estado de cuenta del cliente.
- [`account.report`](models/account_report.py) selecciona los importes almacenados de
  débito, crédito, saldo y conciliados de la moneda de referencia en las consultas del
  Libro mayor de la empresa y del Estado de cuenta del cliente, y en el motor de dominio
  (domain) del Balance general, solo cuando se selecciona la moneda de referencia. Por eso,
  los totales del reporte conservan la tasa de referencia de cada asiento en lugar de
  convertir el total de la compañía a la fecha del reporte. También da formato a las
  columnas monetarias en la moneda seleccionada. `get_report_information()` establece este
  contexto antes de calcular los totales de expresiones, de modo que los totales de grupo
  del Balance general y las líneas desplegadas usan la misma moneda.
- Los [filtros de los reportes](static/src/components/aged_partner_balance/filters.xml)
  comparten un único selector de moneda en los cinco reportes.

El módulo no ejecuta SQL independiente contra las tablas de conciliación; reutiliza las
consultas del Libro mayor de la empresa de Odoo y los importes de conciliación parcial
almacenados.

### Presentación de la tasa guardada del documento

[`res.company._get_conversion_rate_display()`](models/res_company.py) comparte la regla de
orientación de facturas, asientos contables y pagos. Devuelve el valor, la moneda de
visualización y el indicador que distingue la etiqueta USD de la etiqueta de referencia.
Las tasas guardadas no positivas generan un `UserError` cuando se necesita su inverso.

Ambos modelos exponen los campos no almacenados `conversion_rate_display`,
`conversion_rate_display_currency_id` y `conversion_rate_display_is_usd`. El widget
monetario nativo usa la precisión y la posición del símbolo de la moneda de visualización,
con el formato numérico del usuario. Estos campos siguen los cambios de la tasa guardada;
no introducen una instantánea histórica separada ni cambian las dependencias del cálculo
original de la tasa ni el comportamiento de las notas de crédito.

La visualización del documento es distinta de la barra superior: esta última lee las tasas
nativas de la fecha actual. Por eso, un documento histórico y la barra superior pueden
mostrar cotizaciones de USD diferentes. Las columnas de tasa de los apuntes contables
mantienen **Tasa de referencia** y su semántica actual; este cambio se limita a los
indicadores de tasa de los formularios principales de documentos y de pagos.

### Contrato de datos de la barra superior

`get_secondary_currency_systray()` devuelve `False` cuando la compañía activa no tiene
moneda de referencia. En caso contrario, su respuesta contiene:

| Clave | Significado |
|---|---|
| `currency_name` | El código de la moneda base de `base.USD`, no el de la contraparte. |
| `amount` | El resultado sin redondear de convertir un USD a la moneda contraparte. |
| `formatted_amount` | Ese importe formateado con `formatLang`, usando la precisión y la posición del símbolo de la contraparte y el idioma del usuario. |
| `can_update` | Indica si el usuario pertenece a los administradores de Ajustes o a los responsables de Contabilidad. |

El formato redondea solo el importe mostrado; no redondea el `amount` devuelto. Cuando
faltan tasas, se mantienen los respaldos nativos de conversión de Odoo; por eso, mostrar
una cotización no garantiza que se haya obtenido una tasa reciente del proveedor.

## Instalaciones existentes

La [pre-migración 19.0.1.1.0](migrations/19.0.1.1.0/pre-migrate.py) renombra las columnas
`fcurrency` persistidas y el índice de la fecha de vencimiento a sus nombres
`secondary_currency` al actualizar este mismo módulo técnico. No transfiere metadatos de
instalación ni de IDs externos desde un predecesor con otro nombre técnico.

Cambiar el nombre técnico de un módulo no equivale a una actualización *in situ*. Antes de
reemplazar un predecesor instalado, migra los metadatos del módulo instalado y de los IDs
externos, y revisa sus vistas y datos existentes en una copia de la base de datos. Las
pruebas siguientes cubren instalaciones limpias, no la migración de bases de datos ya
instaladas.

## Validación

[Pruebas](TESTING.md) define el contrato funcional de aceptación, la cobertura automatizada
de Odoo 19.0 y los comandos para bases de datos con y sin datos de demostración. Los
fixtures de prueba CCY/USD se ejecutan con un plan de cuentas genérico, mientras que la demo
EUR/USD y la prueba de factura y pago verifican un ejemplo concreto de moneda de la
compañía. Una prueba de factura y pago USD/EUR verifica una moneda de referencia distinta
de USD. Las [pruebas de reportes](tests/test_dual_currency_aged_reports.py) cubren los
totales del Libro mayor de la empresa, los saldos iniciales, las conciliaciones indirectas
y la expansión, así como los activos, pasivos y patrimonio del Balance general y los saldos
del Estado de cuenta del cliente en ambas monedas, incluidos su acción directa y la
navegación desde los reportes de cuentas vencidas.
