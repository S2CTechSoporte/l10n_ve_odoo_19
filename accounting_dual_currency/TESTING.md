# Pruebas

Este documento define el contrato bloqueante de aceptación y el plan de pruebas
automatizadas de `accounting_dual_currency` en Odoo 19.0.

## Requisitos de aceptación

### Supuestos contables

- No se requiere una localización de país; `account_reports` aporta la dependencia de
  reportes.
- Fixture principal: compañía alemana con un plan de cuentas genérico, moneda de la
  compañía denominada CCY y USD como moneda de referencia. Las monedas del fixture son
  datos de prueba, no requisitos; CCY es un marcador de posición, no un código de moneda.
- CCY significa la moneda de la compañía; USD significa la moneda de referencia usada en
  el fixture principal.
- Ejemplo adicional: compañía con EUR como moneda de la compañía y USD como moneda de referencia.
- Fixture de referencia adicional: moneda de la compañía USD y moneda de referencia EUR.
- Fecha de factura, 2026-01-10: 1 USD = 50 CCY en el fixture principal.
- Segunda fecha de pago, 2026-01-20: 1 USD = 52 CCY.
- Tercera fecha de pago, 2026-01-30: 1 USD = 54 CCY.
- Las pruebas no usan impuestos, salvo que el comportamiento probado los requiera.

Las tasas son fixtures de prueba deterministas, no tasas de cambio históricas ni
proyectadas.

### Matriz obligatoria de facturas y pagos

1. Factura en USD con un pago completo en USD.
2. Factura en USD con un pago completo en CCY.
3. Factura en CCY con un pago completo en USD.
4. Factura en CCY con un pago completo en CCY.
5. Factura en USD con varios pagos parciales en USD.
6. Factura en USD con varios pagos parciales en CCY.
7. Factura en USD con pagos parciales mixtos en USD/CCY en fechas diferentes.
8. Factura en CCY con varios pagos parciales en USD.
9. Factura en CCY con varios pagos parciales en CCY.
10. Factura en CCY con pagos parciales mixtos en USD/CCY en fechas diferentes.

| # | Factura | Pagos | Resultado requerido |
|---|---|---|---|
| 1 | USD 100 a tasa 50 | USD 100 a tasa 50 | Ambos importes adeudados son cero; se muestra un pago en USD; la factura queda saldada. |
| 2 | USD 100 a tasa 50 | CCY 5.000 a tasa 50 | Los totales nativos y duales siguen siendo coherentes; ambos importes adeudados son cero. |
| 3 | CCY 5.000 a tasa 50 | USD 100 a tasa 50 | El widget de referencia muestra USD 100; ambos importes adeudados son cero. |
| 4 | CCY 5.000 a tasa 50 | CCY 5.000 a tasa 50 | La contabilidad nativa en moneda de la compañía no cambia; ambos importes adeudados son cero. |
| 5 | USD 100 a tasa 50 | USD 40 y luego USD 60 | El importe adeudado en USD pasa de 100 a 60 y luego a 0; se muestran dos pagos. |
| 6 | USD 100 a tasa 50 | CCY 2.000 y luego CCY 3.000 | El importe adeudado cambia de forma coherente en CCY y en USD, y termina en cero. |
| 7 | USD 100 a tasa 50 | USD 30 a tasa 50, CCY 2.080 a tasa 52, USD 30 a tasa 54 | Cada pago usa su propia fecha; no queda ninguna desviación final del importe adeudado. |
| 8 | CCY 5.000 a tasa 50 | USD 25 y luego USD 75 a tasa 50 | Los importes adeudados en CCY y en USD disminuyen tras cada pago y terminan en cero. |
| 9 | CCY 5.000 a tasa 50 | CCY 2.000 y luego CCY 3.000 | El importe adeudado en moneda de la compañía pasa de 5.000 a 3.000 y luego a 0. |
| 10 | CCY 5.000 a tasa 50 | USD 25 a tasa 50, CCY 1.050 a tasa 52, USD 50 a tasa 54 | La conciliación con fechas mixtas salda la factura y expone el impacto de la tasa sin corromper los campos auxiliares. |

### Aserciones por escenario de la matriz

Cada escenario debe comprobar:

1. La factura se registra en la moneda del documento solicitada.
2. `secondary_currency_id` es USD.
3. Los totales del documento, en moneda de la compañía y en moneda de referencia, son
   correctos en la fecha de la factura.
4. Los importes adeudados nativos y duales son correctos después de cada pago.
5. `account.partial.reconcile.amount_secondary_currency` usa la conciliación parcial en
   moneda de referencia cuando alguno de los lados conciliados está en USD; en caso
   contrario, convierte en la fecha de conciliación.
6. Los widgets de pagos en moneda de referencia y en moneda de la compañía contienen los
   pagos esperados, sin diferencias de cambio, en la moneda de visualización seleccionada.
7. Los campos de apunte contable `balance_secondary_currency`,
   `debit_secondary_currency`, `credit_secondary_currency` y
   `amount_residual_secondary_currency` se mantienen coherentes.
8. Los estados intermedios son `partial` cuando corresponde.
9. El importe adeudado final es cero, y el estado final de pago es el estado válido de factura
   saldada en Odoo (`paid` o `in_payment`, según las funciones contables instaladas).
10. Los asientos de diferencia de cambio generados por Odoo no crean pagos de negocio
    duplicados en las aserciones.

### Pruebas obligatorias de reportes

1. Cuenta por cobrar vencida (Aged Receivable) usa por defecto la moneda de la compañía y
   muestra esa moneda y la de referencia (CCY y USD en el fixture principal).
2. Cuenta por cobrar vencida en USD respeta la fecha de corte del reporte: un pago posterior
   a la fecha de corte no debe reducir un reporte anterior.
3. Los totales por contacto de Cuenta por cobrar vencida en USD son iguales al total general
   de un contacto aislado y a la suma de todos los tramos de antigüedad.
4. Cuenta por pagar vencida (Aged Payable) en USD usa el signo, el total por contacto y el
   tramo de antigüedad correctos.
5. Las columnas monetarias usan la moneda seleccionada en `dual_currency_id`.
6. Con una compañía en EUR y referencia en USD, el selector usa EUR por defecto y ofrece EUR
   y USD.
7. Con una compañía en USD y referencia en EUR, el selector usa USD por defecto y ofrece USD
   y EUR.
8. El Libro mayor de la empresa (Partner Ledger) y el Balance general (Balance Sheet) ofrecen
   la moneda de la compañía y la de referencia para compañías compatibles, y ocultan el
   selector en selecciones incompatibles.
9. Los totales por contacto y por apunte contable del Libro mayor de la empresa usan los
   importes registrados de débito y de saldo de referencia; los saldos iniciales, las
   conciliaciones indirectas y las líneas desplegadas conservan esos importes.
10. Los activos, cuentas por cobrar, pasivos, patrimonio y totales precalculados por grupo de
    columnas del Balance general usan los saldos de referencia registrados cuando se
    selecciona esa moneda, mientras que los totales en moneda de la compañía no cambian.
11. Las líneas de cuenta desplegadas del Balance general cuadran con los totales de su grupo
    padre en moneda de referencia.
12. El Libro mayor de la empresa y el Balance general usan la compañía del reporte
    seleccionada, no la compañía activa, para elegir los importes de referencia.
13. El Estado de cuenta del cliente (Customer Statement) usa por defecto la moneda de la
    compañía al abrirse directamente, ofrece ambas monedas y hereda la moneda seleccionada en
    Cuenta por cobrar vencida y Cuenta por pagar vencida. Los importes y saldos de clientes y
    proveedores usan los valores registrados de compañía y de referencia; las selecciones de
    compañías incompatibles ocultan el selector de moneda.

### Flujos adicionales obligatorios

1. Una nota de crédito en moneda de la compañía creada a partir de una factura en moneda de
   la compañía reutiliza la tasa original de la factura en los campos de referencia.
2. Una nota de crédito en USD usa su propia fecha contable para la conversión a moneda de la
   compañía.
3. Un asiento contable manual en USD conserva el débito y el crédito convertidos a moneda de
   la compañía después de guardarlo, y cuadra en los campos de referencia en USD.
4. Los campos auxiliares de pago calculan los importes de compañía y de referencia tanto para
   pagos en CCY como en USD.
5. Si la compañía no tiene moneda de referencia, los cálculos recurren de forma segura a la
   moneda de la compañía.
6. El módulo se instala sin una localización de país obligatoria y no activa monedas
   adicionales ni cambia la moneda de un país durante la instalación. Los fixtures de prueba
   pueden activar las monedas que usan.
7. El manifiesto no tiene dependencias de localización de país y no depende de
   `account_report_multi_currency`.
8. Una compañía que usa EUR y USD como referencia registra una factura en EUR, recibe un pago
   en USD y calcula correctamente ambos importes.
9. El valor por defecto de la moneda de referencia ofrece USD para las monedas de la compañía
   distintas de USD, incluido EUR, y no fuerza una moneda de referencia en las compañías que
   usan USD.
10. Una compañía en USD con EUR como referencia registra una factura en USD, recibe un pago en
    EUR y calcula correctamente ambos importes.

### Presentación obligatoria de la tasa guardada del documento

1. Los formularios principales de factura, asiento contable y pago derivan la tasa mostrada
   únicamente de su `conversion_rate` guardada. El cálculo de la visualización no debe llamar
   a funciones auxiliares de fecha, a conversiones de moneda ni a las API de búsqueda de tasas.
2. Con una compañía distinta de USD y referencia en USD, muestra la tasa guardada con el
   símbolo de la compañía. Con una compañía en USD y una referencia distinta de USD, muestra su
   inverso con el símbolo de la referencia. Usa la etiqueta **Tasa USD**.
3. Las facturas de cliente y de proveedor y los pagos en moneda de la compañía, en USD o en una
   tercera moneda muestran la misma orientación hacia USD para un mismo par compañía/referencia.
4. Cuando ninguna moneda es USD, o no hay referencia configurada, muestra la tasa guardada sin
   cambios en la moneda de la compañía bajo **Tasa de referencia**. Cuando ambas monedas son
   USD, se conserva una cotización unitaria en USD.
5. La visualización usa la precisión monetaria y la posición del símbolo de la contraparte, así
   como el idioma del usuario. No debe sobrescribir ni redondear la tasa de origen guardada.
6. La presentación sigue los cambios de la fuente guardada. Una fuente no positiva debe generar
   un error explícito si necesita invertirse.
7. Ambos formularios heredados usan campos monetarios de solo lectura y etiquetas USD/referencia
   mutuamente excluyentes. Las columnas de tasa de referencia de los apuntes contables no cambian.
8. Las notas de crédito en moneda de la compañía y los asientos contables manuales en USD
   conservan su comportamiento actual de tasa de referencia. La nueva visualización no introduce
   ninguna regla de fecha.
9. La tasa EUR/USD guardada de la compañía de demostración produce una visualización monetaria de
   la Tasa USD en EUR. Esta aserción debe ejecutarse con datos de demostración y omitirse de
   forma explícita sin ellos.

### Validación obligatoria de datos de demostración

Cuando los datos de demostración están habilitados:

1. `accounting_dual_currency.demo_company_eur` existe.
2. Esta compañía de ejemplo tiene como país Alemania, como moneda de la compañía EUR y como
   moneda de referencia USD.
3. `accounting_dual_currency.demo_rate_usd_20260110` pertenece a esa compañía y representa
   1 USD = 0,8 EUR.

La prueba de demostración debe omitirse de forma explícita cuando la base de datos se
inicializó sin datos de demostración. Debe ejecutarse, no omitirse, en la ejecución dedicada
con datos de demostración.

### Cotización obligatoria de la barra superior

1. La barra superior usa siempre USD como base y muestra el valor de un dólar.
2. Una compañía en USD con referencia en EUR muestra el importe en EUR; una compañía en EUR con
   referencia en USD también muestra el importe en EUR.
3. Si ninguna de las monedas configuradas es USD, la contraparte es la moneda de la compañía, no
   la moneda de referencia.
4. El formato monetario usa la precisión decimal y la posición configurada del símbolo de la
   moneda contraparte, así como el idioma del usuario. El formato español con EUR después del
   importe muestra **USD: 0,89 &#8364;**, sin un espacio adicional antes de los dos puntos. El
   formato no debe redondear el `amount` sin procesar de la respuesta.
5. Sin moneda de referencia, el indicador se oculta. Si USD es a la vez la moneda de la compañía
   y la de referencia, se conserva una cotización unitaria; si la compañía y la referencia son la
   misma moneda distinta de USD, sigue mostrándose la conversión de USD a esa moneda, no una
   cotización unitaria.
6. Abrir el desplegable, cambiar la compañía activa y completar una actualización manual
   actualizan la cotización. Las respuestas obsoletas no deben sobrescribir el importe ni el
   símbolo de la contraparte de la compañía recién seleccionada.
7. La cotización usa la fecha actual del contexto del usuario, no la fecha de un documento.
   Cuando existe una tasa vigente, una tasa futura no debe reemplazarla. Las sucursales usan las
   tasas de la compañía raíz.
8. Ver la cotización no requiere un proveedor. Actualizar requiere los permisos existentes y un
   proveedor configurado; los errores se propagan y un reintento exitoso debe actualizar el
   importe.
9. La presentación en USD de la barra superior no redefine las tasas de referencia de los
   documentos ni sus reglas de fecha.

### Regla de aceptación

La aceptación requiere que el módulo se instale y que todas las pruebas aplicables pasen en
ambas [ejecuciones con y sin datos de demostración](#ejecuciones-con-y-sin-datos-de-demostración).
Los archivos de prueba estáticos sin resultados ejecutados no cumplen este contrato. Migrar un
nombre de módulo ya instalado requiere una migración de base de datos aparte.

## Plan de pruebas

### Objetivo

Automatizar cada [requisito de aceptación](#requisitos-de-aceptación) para Odoo 19.0.

### Marco de pruebas

Las pruebas de contabilidad y reportes usan el comportamiento de `TransactionCase` de Odoo
19.0 mediante `AccountTestInvoicingCommon`; las pruebas de demostración y de la barra superior
heredan directamente de `TransactionCase`. Cada método de prueba ya se ejecuta en un savepoint;
la recomendación antigua de heredar de `SavepointCase` no aplica.

Usa `@tagged("post_install", "-at_install")` porque las pruebas registran documentos contables y
ejercitan los manejadores de reportes instalados.

### Estructura de las pruebas

- `tests/common.py`: compañía de prueba alemana con un plan de cuentas genérico, tasas de
  ejemplo CCY/USD, diarios, contactos, productos, funciones auxiliares y aserciones.
- `tests/test_dual_currency_invoice_payments.py`: la matriz obligatoria de diez escenarios y los
  campos auxiliares de pago.
- `tests/test_dual_currency_aged_reports.py`: opciones de los reportes de cuentas vencidas, fechas de
  corte, tramos de cuentas por cobrar y por pagar, y formato de moneda de las columnas; opciones,
  totales y líneas desplegadas del Libro mayor de la empresa y del Balance general.
- `tests/test_dual_currency_accounting_flows.py`: asientos contables manuales, notas de crédito,
  comportamiento de respaldo, flujos de factura y pago EUR/USD y USD/EUR, valores por defecto de
  referencia y comprobaciones de dependencias independientes de la localización.
- `tests/test_dual_currency_demo.py`: compañía de demostración en XML, validación de tasas y
  valores por defecto de referencia para varias monedas de la compañía.
- `tests/test_secondary_currency_menu.py`: contrato de datos de la cotización en USD, selección de
  contraparte, selección nativa de tasas, formato monetario, permisos de actualización manual,
  errores del proveedor y cotización de la demostración.
- `tests/test_stored_conversion_rate_display.py`: presentación de la tasa guardada en facturas,
  asientos contables y pagos; independencia de la moneda de transacción; etiquetas de respaldo;
  ausencia de búsquedas de fecha o tasa; preservación del origen; formato monetario; tasas inversas
  no válidas; vistas heredadas y validación de la demostración.
- `static/tests/secondary_currency_menu.test.js`: renderizado de la cotización y conservación del
  formato, flujos de actualización y reintento, condiciones de carrera al cambiar de compañía,
  visibilidad y posición en la barra superior.

### Fixtures compartidos

La clase común usa un fixture determinista de moneda de la compañía, denotada aquí por CCY, sin
exigir esa moneda a las compañías que usan el módulo. Debe configurar:

1. País `base.de` con la plantilla de plan de cuentas `generic_coa` de Odoo.
2. Una moneda de la compañía activa (CCY) y la moneda de referencia `base.USD`.
3. Moneda de la compañía CCY y `company.secondary_currency_id` USD.
4. Diarios estándar de Odoo: ventas, compras, banco y varios.
5. Un cliente y un proveedor alemanes.
6. Un producto de servicio sin impuestos.
7. Tasas específicas de la compañía de 50, 52 y 54 CCY por USD el 2026-01-10, el 2026-01-20 y el
   2026-01-30.

Un caso adicional cambia la moneda de la compañía de prueba a EUR, usa USD como referencia a 0,8
EUR por USD y verifica los totales de factura, la conversión de pagos y las opciones de moneda de
los reportes de cuentas vencidas. Otro caso usa una compañía en USD con referencia en EUR a 1,25 USD por
EUR para verificar una moneda de referencia alternativa. También se comprueba la selección por
defecto para EUR y para las compañías que ya usan USD.

### Funciones auxiliares requeridas

- `_set_rate(currency, company, rate_date, inverse_rate)`
- `_create_invoice(currency, amount, invoice_date, move_type="out_invoice")`
- `_create_payment(invoice, currency, amount, payment_date)`
- `_get_payment_term_line(move)`
- `_assert_invoice_dual_totals(invoice, document, local, reference)`
- `_assert_dual_residual_coherence(invoice)`
- `_assert_payment_widgets(invoice, payment_count)`
- `_assert_move_line_dual_fields(move)`
- `_run_invoice_payment_scenario(...)`
- `_get_report_options(report_xmlid, date_to, currency)`

Las funciones auxiliares deben usar las APIs estándar de conversión de moneda y de registro de
pagos de Odoo, en lugar de reproducir la lógica de conciliación de Odoo.

### Cobertura de escenarios

Los métodos de `tests/test_dual_currency_invoice_payments.py` cubren estos escenarios lógicos,
usando CCY para describir la moneda de la compañía de forma independiente de los nombres de
implementación específicos de cada moneda:

1. Factura en USD con pago completo en USD.
2. Factura en USD con pago completo en CCY.
3. Factura en CCY con pago completo en USD.
4. Factura en CCY con pago completo en CCY.
5. Factura en USD con pagos parciales en USD.
6. Factura en USD con pagos parciales en CCY.
7. Factura en USD con pagos parciales mixtos en fechas diferentes.
8. Factura en CCY con pagos parciales en USD.
9. Factura en CCY con pagos parciales en CCY.
10. Factura en CCY con pagos parciales mixtos en fechas diferentes.

`test_eur_company_invoice_payment_and_aged_currency_options` cubre el flujo contable EUR/USD;
`test_usd_company_eur_reference_invoice_and_payment` cubre una referencia distinta de USD.
`test_reference_currency_default_for_other_company_currency` y
`test_secondary_currency_default_depends_on_company_currency` cubren los valores por defecto.

### Estrategia de reportes

Obtén las opciones del reporte estándar de cuentas vencidas con `report.get_options()`. Selecciona la
moneda de referencia (USD en el fixture principal) pasando `dual_currency_id` en las opciones
anteriores. Invoca `_aged_partner_report_custom_engine_common()` para:

- Total general: sin groupby actual.
- Total por contacto: `current_groupby="partner_id"`.
- Apunte contable: `current_groupby="id"` al validar los valores de detalle.

Verifica que los pagos cuyo `max_date` es posterior a `options.date.date_to` queden excluidos del
importe adeudado del reporte.

Para el Libro mayor de la empresa y el Balance general, usa `report.get_options()` con
`dual_currency_id` para comparar los importes de compañía y de referencia. Verifica las líneas de
contacto, de saldo inicial, de apunte contable y desplegadas del Libro mayor de la empresa frente a
los importes secundarios registrados y a las conciliaciones. En el Balance general, usa
`get_report_information()` para verificar las líneas mostradas y los `column_groups_totals`
precalculados; después, verifica las líneas de cuenta desplegadas con `get_expanded_lines()`.
Comprueba que el selector se oculte en compañías incompatibles y que la compañía del reporte
seleccionada determine la moneda.

Para el Estado de cuenta del cliente, comprueba el valor por defecto de la moneda de la compañía en la
acción directa del contacto, las monedas de la compañía y de referencia seleccionables, y la moneda que
llega desde Cuenta por cobrar vencida y Cuenta por pagar vencida. Compara los importes y saldos de
clientes y proveedores mostrados con los valores registrados de los apuntes en ambas monedas.

### Ejecuciones con y sin datos de demostración

Las pruebas de la barra superior en `tests/test_secondary_currency_menu.py` cubren la conversión
desde USD en ambas configuraciones de compañía y referencia; la contraparte en moneda de la
compañía cuando ninguna moneda configurada es USD; el formato monetario español exacto, con
símbolos antes y después del importe; la precisión decimal de la contraparte sin redondear el
importe sin procesar; la selección por fecha actual con tasas pasadas y futuras; el aislamiento de
la compañía activa; la ausencia de monedas de referencia; las configuraciones con monedas iguales
en USD y con monedas iguales distintas de USD; la autorización de los responsables de Contabilidad;
los empleados sin permiso y las compañías no permitidas; las tasas de la compañía raíz para las
sucursales; la visualización sin proveedor; el actualizador manual estándar y los errores del
proveedor. Las respuestas del proveedor se simulan; las pruebas nunca descargan tasas en vivo. La
aserción de demostración verifica por separado la tasa USD/EUR declarada.

`static/tests/secondary_currency_menu.test.js` cubre la etiqueta USD, los símbolos localizados de
la contraparte antes y después del importe, la actualización del desplegable, la actualización
manual, el acceso de solo visualización, la propagación de errores y el reintento exitoso, los
clics duplicados, las condiciones de carrera al cambiar de compañía, los cambios de visibilidad y
la posición en la barra superior. Ejecútala en `/web/tests?filter=accounting_dual_currency`.

Ejecuta estos comandos desde la raíz del espacio de trabajo, con el intérprete, el entorno y el
servidor configurados en `.vscode/launch.json`:

```bash
export VIRTUAL_ENV="$PWD/.venv"
export PATH="$VIRTUAL_ENV/bin:$PATH"
export TMPDIR="$PWD/tmp"

./.venv/bin/python -X frozen_modules=off /opt/odoo/19.0/odoo/odoo-bin \
    -c odoo.conf \
    -d test_accounting_dual_currency_19 \
    -i accounting_dual_currency \
    --without-demo=True \
    --test-enable \
    --test-tags /accounting_dual_currency \
    --http-port=18019 \
    --stop-after-init
```

Ejecuta una segunda base de datos limpia con datos de demostración:

```bash
./.venv/bin/python -X frozen_modules=off /opt/odoo/19.0/odoo/odoo-bin \
    -c odoo.conf \
    -d test_accounting_dual_currency_demo_19 \
    -i accounting_dual_currency \
    --with-demo \
    --test-enable \
    --test-tags /accounting_dual_currency \
    --http-port=18021 \
    --stop-after-init
```

Ambas bases de datos deben inicializarse desde cero, para que los resultados no dependan de
registros contables existentes ni de módulos personalizados instalados.

Para una ejecución de regresión solo de la barra superior, usa
`--test-tags /accounting_dual_currency:TestSecondaryCurrencyMenu` en cada comando. Para volver a
ejecutar una base de datos de prueba dedicada ya inicializada, reemplaza
`-i accounting_dual_currency` por `-u accounting_dual_currency`.

### Comprobaciones estáticas

Antes de las ejecuciones de Odoo:

1. Compila todos los archivos Python.
2. Analiza sintácticamente todos los archivos XML.
3. Confirma que ninguna vista contiene `attrs`.
4. Confirma que ningún código en ejecución hace referencia a `l10n_cr`, Costa Rica, CRC ni a
   `account_report_multi_currency`; las aserciones negativas y la documentación sobre dependencias
   eliminadas son intencionales.
5. Confirma que las etiquetas y los valores por defecto de los campos de moneda de la compañía no
   fuerzan una moneda específica; la activación de monedas de prueba se limita a los fixtures, no a
   la instalación del módulo.
6. Confirma que el manifiesto y los archivos de datos no requieren una localización de país, no
   activan monedas adicionales ni modifican la moneda de un país.

### Criterios de finalización

El trabajo solo se considera completo cuando:

1. Pasan los diez escenarios de facturas y pagos.
2. Pasan las pruebas de los reportes de cuentas vencidas (Cuenta por cobrar vencida y Cuenta por pagar vencida) en
   moneda de la compañía y de referencia; también están cubiertos los selectores EUR/USD y USD/EUR.
3. Pasan las opciones y los totales del Libro mayor de la empresa y del Balance general en moneda
   de la compañía y de referencia, con las líneas desplegadas en moneda de referencia verificadas.
4. Pasan los asientos manuales, las notas de crédito (devoluciones), el comportamiento de respaldo,
   las facturas y pagos EUR/USD y USD/EUR, los valores por defecto de referencia y la instalación
   independiente de la localización.
5. Pasa la instalación sin datos de demostración.
6. La instalación con datos de demostración se ejecuta y pasa las aserciones de demostración.
7. Las pruebas de la cotización de la barra superior pasan en ambas ejecuciones, con la omisión
   esperada de la prueba de demostración solo en la base de datos sin datos de demostración, y
   pasan las pruebas HOOT correspondientes.
