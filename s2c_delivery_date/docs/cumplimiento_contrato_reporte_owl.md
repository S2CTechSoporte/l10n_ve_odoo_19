# Cumplimiento del contrato de reportes OWL en Odoo 19

## Objetivo

Este documento describe el estado de la personalización que agrega información de
entrega al reporte estándar **Cuenta por cobrar vencida** y las acciones necesarias
para que cumpla el contrato definido en
[`docs/personalizacion_reportes_owl_odoo_19.md`](../../../../../docs/personalizacion_reportes_owl_odoo_19.md).

El análisis abarca estas columnas:

- `delivery_date`: fecha de entrega de la factura.
- `delivery_time`: días transcurridos entre la fecha de factura y la fecha de entrega.
- `invoice_date_due`: fecha de vencimiento calculada a partir de la entrega y el
  término de pago.
- `remaining_days`: estado relativo del vencimiento, por ejemplo `Hoy`, `Mañana`,
  `Hace 5 días` o `En 20 días`.

## Decisiones funcionales confirmadas

### Extensión directa del reporte estándar

El módulo modifica directamente `account_reports.aged_receivable_report`. Esta
estrategia es válida porque el objetivo es que la acción estándar muestre las
columnas para todos los usuarios. No se requiere una variante con `root_report_id`
mientras se mantenga ese alcance.

Esta decisión implica acoplamiento con `account_reports`. Después de cada
actualización de Odoo se deben ejecutar las pruebas del reporte para detectar
cambios en el handler, las expresiones o el mecanismo de expansión.

### Regla de días relativos a la entrega

La columna `remaining_days` es deliberadamente dinámica y **no debe usar la fecha
de corte del reporte** como fecha de referencia.

La regla de negocio confirmada es:

1. Los términos de pago toman `delivery_date` como fecha inicial.
2. Ese cálculo produce `invoice_date_due` y `date_maturity`.
3. `remaining_days` compara ese vencimiento, originado en la entrega, con el día
   actual.

Por tanto, abrir hoy un reporte con una fecha de corte histórica puede mostrar un
estado relativo distinto del bucket histórico del reporte. No es un defecto: el
bucket responde a la fecha de corte y `remaining_days` responde al estado vigente
del vencimiento calculado desde la entrega.

Esta semántica debe conservarse en pantalla, PDF y XLSX. También debe quedar cubierta
por pruebas para evitar que una futura modificación sustituya el día actual por
`options['date']['date_to']`.

> Nota semántica: la implementación no cuenta directamente los días desde
> `delivery_date`. Cuenta los días respecto de `invoice_date_due`, cuya base de
> cálculo es `delivery_date`. Esto corresponde a la regla descrita arriba.

## Estado actual

### Aspectos que cumplen

- El manifest depende de `account_reports`.
- Cada columna tiene una expresión en `account_reports.aged_receivable_line`.
- Para las cuatro columnas coinciden `expression_label`, `label`, `subformula` y
  la clave Python.
- El cálculo monetario, los períodos, las conciliaciones parciales, la moneda,
  `offset` y `limit` siguen a cargo del engine estándar.
- No se reemplaza `custom_display_config`, por lo que se conservan los filtros y la
  plantilla de línea del reporte estándar.
- Los diccionarios de columnas existentes se modifican sin reconstruirlos; por ello
  se conserva `column_group_key`.
- Las columnas son descriptivas por apunte. Es correcto que sus valores sean `None`
  en el total general y en el subtotal por cliente.
- Las expresiones custom no son auditables actualmente. Esto es coherente porque no
  existe una acción que explique esas celdas.
- `_prepare_partner_values()` incluye las cuatro claves adicionales. Esto permite
  que la optimización batch de `unfold_all` conozca las expresiones y no obliga a
  desactivarla.

### Aspectos pendientes

#### 1. Valor crudo incorrecto en `delivery_time`

En
[`models/account_aged_partner_balance.py`](../models/account_aged_partner_balance.py),
la celda `delivery_time` recibe `delivery_date` en `no_format`.

El contrato exige que `no_format` contenga el valor crudo de la propia columna. En
este caso debe ser el entero de `account.move.delivery_time`. El valor actual puede
producir exportaciones incorrectas y deja la celda con una semántica distinta de su
`expression_label`.

Además, el uso de una condición de verdad para construir `name` oculta el valor
válido `0`. Una entrega en la misma fecha de la factura debe poder mostrar cero días.

#### 2. Los valores de detalle no nacen del engine

`_aged_partner_report_custom_engine_common()` agrega las claves, pero las devuelve
como `None` en todos los niveles. Después, `_custom_line_postprocessor()` rellena el
detalle mediante consultas a `account.move.line`.

El postprocesador se ejecuta en el servidor y también participa en las exportaciones,
por lo que su uso no equivale a calcular en OWL. Sin embargo, en este caso deja una
inconsistencia: `_build_column_dict()` construye primero la celda a partir de `None`
y calcula metadatos como `is_zero`; luego el postprocesador cambia `name` y
`no_format`, pero no reconstruye esos metadatos.

También obliga a resolver cada línea después de que el engine ya conocía el
`account.move.line` correspondiente. El valor de detalle debe incorporarse al
resultado del engine para que la celda se construya correctamente desde el inicio.

#### 3. Las fechas se formatean manualmente

`delivery_date` e `invoice_date_due` asignan manualmente un `name` con el patrón
`%d-%m-%Y`. Al existir `name`, el formateador genérico no vuelve a procesar la
celda.

Esto evita el formato regional de Odoo y puede convertir una fecha en texto al
exportar a XLSX. Las columnas con `figure_type="date"` deben entregar objetos
`date` en `no_format` y permitir que Odoo genere `name`.

#### 4. Tipo declarativo de `delivery_time`

`delivery_time` representa un conteo, pero está declarado como `string`. Para
preservar orden, exportación y semántica debe declararse como `integer` y entregar
un entero en `no_format`.

Si se necesita mostrar la unidad, la opción más simple y compatible es nombrar la
columna `Tiempo de entrega (días)` y dejar que Odoo formatee el número. Si se exige
el texto `10 días` dentro de cada celda, la presentación debe separarse del valor
crudo y probarse especialmente en XLSX para no convertir el dato numérico en texto.

#### 5. Orden no determinista de las columnas

Los registros de
[`data/account_aged_receivable_report.xml`](../data/account_aged_receivable_report.xml)
no declaran `sequence`, y el documento XML tampoco usa `auto_sequence`. Las nuevas
columnas reciben la secuencia predeterminada y los empates se resuelven por el `id`
de base de datos.

Se deben declarar secuencias explícitas para todas las columnas involucradas en el
nuevo orden. Si es necesario intercalarlas con columnas estándar, también se deben
actualizar de forma explícita las secuencias de esas columnas estándar. El orden no
debe depender del orden de instalación ni de identificadores internos.

#### 6. Alcance demasiado amplio del handler

La clase hereda `account.aged.partner.balance.report.handler`, compartido por cuentas
por cobrar y cuentas por pagar. Aunque el método del engine comprueba el
`report_id`, `_custom_line_postprocessor()` y `_prepare_partner_values()` también se
ejecutan en el flujo de cuentas por pagar.

La personalización debe heredar el handler específico
`account.aged.receivable.report.handler`. Así el reporte de cuentas por pagar queda
fuera del cambio por construcción y no depende de guardas parciales.

#### 7. Cobertura de pruebas insuficiente

El test del reporte sólo comprueba que existen líneas y que las etiquetas aparecen
en `options['columns']`. No comprueba los valores ni los caminos que reconstruyen el
reporte.

Sin estas aserciones, la suite actual no detecta el `no_format` incorrecto de
`delivery_time`, una fecha exportada como texto, una regresión de `unfold_all` ni un
cambio accidental en la regla de días basada en la entrega.

## Instrucciones de implementación

### Paso 1. Fijar el contrato de cada columna

Antes de modificar el handler, mantener esta matriz como contrato de salida:

| Columna | `figure_type` | Detalle `id` | Cliente | Total general |
|---|---|---|---|---|
| `delivery_date` | `date` | `date` o `None` | `None` | `None` |
| `delivery_time` | `integer` | entero, incluido `0` | `None` | `None` |
| `invoice_date_due` | `date` | `date` o `None` | `None` | `None` |
| `remaining_days` | `string` | texto relativo o `None` | `None` | `None` |

Los valores de cliente y total general son vacíos de forma deliberada: no existe
una única fecha ni un único tiempo de entrega representativo cuando se agrupan
varias facturas.

### Paso 2. Limitar la herencia a cuentas por cobrar

Cambiar la herencia Python al modelo
`account.aged.receivable.report.handler`. Los overrides del engine y de
`_prepare_partner_values()` seguirán disponibles por la herencia del handler
estándar, pero no afectarán el Aged Payable.

Después del cambio, conservar una prueba que abra ambos reportes:

- Aged Receivable debe contener las cuatro columnas.
- Aged Payable no debe contenerlas y debe conservar cualquier columna aportada por
  otros módulos.

### Paso 3. Producir el detalle desde el engine

Mantener la llamada a `super()` para reutilizar por completo el SQL estándar. No es
necesario copiar la consulta de antigüedad.

Después de obtener el resultado:

1. Para `current_groupby is None`, agregar las cuatro claves con `None`.
2. Para `current_groupby == 'partner_id'`, agregar las cuatro claves con `None` a
   cada cliente.
3. Para `current_groupby == 'id'`, reunir todos los identificadores de
   `account.move.line` devueltos por `super()`.
4. Leer sus facturas en lote, sin `sudo()` y sin una búsqueda que ignore el dominio
   del reporte.
5. Agregar a cada diccionario los valores crudos de `move_id`.

La forma esperada del detalle es equivalente a:

```python
{
    "delivery_date": move.delivery_date or None,
    "delivery_time": move.delivery_time,
    "invoice_date_due": move.invoice_date_due or None,
    "remaining_days": relative_due_text,
}
```

Es importante comprobar `current_groupby == 'id'` antes de interpretar la clave del
resultado como un apunte. En el nivel anterior esa clave es un `res.partner`.

El cálculo en lote evita consultas repetidas y hace que el mismo resultado alimente
la carga inicial, el despliegue manual, `load_more`, `unfold_all`, PDF y XLSX.

### Paso 4. Conservar la regla deliberada de `remaining_days`

El helper debe seguir comparando `invoice_date_due` con el día actual, no con la
fecha de corte del reporte. Para integrarse mejor con Odoo puede obtenerse el día
actual mediante `fields.Date.context_today(self)`, calculado una sola vez por
ejecución, pero la semántica no debe cambiar.

Casos mínimos:

| Diferencia | Resultado |
|---:|---|
| `0` | `Hoy` |
| `1` | `Mañana` |
| `-1` | `Ayer` |
| menor que `-1` | `Hace N días` |
| entre `2` y `120` | `En N días` |
| mayor que `120` | `En más de 120 días` |
| sin vencimiento | vacío |

Las pruebas deben controlar el día actual o construir fechas relativas a él. Deben
incluir un reporte cuya fecha de corte sea distinta del día actual y demostrar que
`remaining_days` conserva la regla basada en el estado vigente del vencimiento
originado en la entrega.

### Paso 5. Delegar el formato a Odoo

Eliminar del postprocesador la asignación manual de `name` para fechas y enteros.
Cuando el engine entregue los valores crudos, `_format_column_values()` producirá el
texto de pantalla según el idioma del usuario y mantendrá tipos adecuados en la
exportación.

`remaining_days` puede seguir siendo un string ya calculado porque su valor es una
etiqueta relativa, no un número destinado a agregación.

Si el postprocesador deja de tener otra responsabilidad, eliminar el override
completo. Si se conserva por una necesidad visual futura, no debe corregir cálculos
ni reemplazar valores crudos del engine.

### Paso 6. Completar la definición XML

En cada `account.report.column`:

- Declarar una `sequence` explícita.
- Mantener `date` para `delivery_date` e `invoice_date_due`.
- Cambiar `delivery_time` a `integer`.
- Mantener `remaining_days` como `string`.
- Decidir explícitamente si la columna es `sortable`.

En cada `account.report.expression`:

- Mantener iguales `label`, `subformula` y la clave del engine.
- Declarar `auditable=False` de forma explícita mientras no exista una acción de
  auditoría que represente exactamente el valor.

Un orden sugerido debe colocar juntos los datos documentales:

1. Fecha de factura.
2. Fecha de entrega.
3. Tiempo de entrega en días.
4. Fecha de vencimiento.
5. Estado relativo del vencimiento.
6. Columnas monetarias y períodos estándar.

Las secuencias exactas deben asignarse también a las columnas estándar que haya que
mover para obtener este orden sin empates.

### Paso 7. Verificar `unfold_all` y paginación

Al mantener las cuatro claves en `_prepare_partner_values()` y producirlas en el
resultado de detalle, `_common_custom_unfold_all_batch_data_generator()` puede
transportarlas sin copiar el SQL estándar.

Se debe verificar que:

- `unfold_all=True` muestra los valores de todos los apuntes.
- El despliegue manual devuelve los mismos valores.
- `load_more` conserva los valores al solicitar páginas posteriores.
- Los subtotales generados debajo de secciones mantienen vacías estas columnas
  descriptivas.

Si una futura columna necesita agregación real, ya no bastará con
`_prepare_partner_values()`: habrá que definir cómo se acumula en el batch o
desactivar esa optimización devolviendo `{}`.

## Plan mínimo de pruebas

Agregar casos enfocados en
[`tests/test_delivery_date.py`](../tests/test_delivery_date.py):

1. Verificar orden, nombre, `figure_type`, `sortable` y `column_group_key` en
   `get_options()`.
2. Crear una factura con entrega posterior y comprobar en la línea de apunte:
   `delivery_date`, `delivery_time`, `invoice_date_due` y `remaining_days`.
3. Comprobar que `delivery_time.no_format` es un entero y no una fecha.
4. Comprobar que una entrega el mismo día produce `delivery_time == 0` y que el cero
   no desaparece.
5. Comprobar que fechas y enteros dejan que Odoo produzca `name`, sin imponer el
   patrón `%d-%m-%Y` desde el handler.
6. Comprobar explícitamente `None` para las cuatro columnas en total general y
   subtotal por cliente.
7. Activar `totals_below_sections` y comprobar que `Total <cliente>` conserva esa
   semántica.
8. Comparar despliegue manual y `unfold_all`.
9. Forzar más apuntes que el límite de carga y comprobar la página obtenida por
   `load_more`.
10. Usar una fecha de corte histórica y comprobar que `remaining_days` sigue
    calculándose contra el día actual a partir del vencimiento originado en la
    entrega.
11. Verificar una conciliación parcial y confirmar que las columnas monetarias
    estándar no cambian.
12. Verificar multicompañía y, cuando esté disponible, moneda extranjera.
13. Generar XLSX y comprobar que las fechas son celdas de fecha y
    `delivery_time` es numérico.
14. Generar PDF y comprobar al menos que finaliza y contiene los encabezados y
    valores esperados.
15. Confirmar que Aged Payable continúa sin las columnas del módulo.

Las pruebas deben inspeccionar `no_format` antes de limitarse al texto presentado.
Para estas columnas no aditivas no se exige que el total sea la suma del detalle;
se exige que el agregado sea deliberadamente `None`.

## Criterios de aceptación

La adaptación se considera conforme cuando se cumplen todos estos puntos:

- [ ] La extensión afecta únicamente al handler de cuentas por cobrar.
- [ ] Cada columna mantiene alineados `expression_label`, `label`, `subformula` y
      clave Python.
- [ ] El engine devuelve los valores reales en `current_groupby == 'id'`.
- [ ] Total general y cliente devuelven `None` deliberadamente para las cuatro
      columnas.
- [ ] `delivery_time.no_format` es entero y admite el valor `0`.
- [ ] Las fechas conservan objetos `date` como valor crudo.
- [ ] Odoo, y no el handler, aplica el formato regional de las fechas.
- [ ] `remaining_days` usa el día actual y conserva el vencimiento originado en la
      entrega como regla funcional.
- [ ] El orden de columnas se controla mediante secuencias explícitas.
- [ ] Las expresiones descriptivas declaran `auditable=False`.
- [ ] `unfold_all`, despliegue manual y `load_more` producen el mismo detalle.
- [ ] XLSX conserva fechas e enteros como tipos nativos y PDF muestra los valores.
- [ ] Aged Payable permanece sin cambios.
- [ ] La suite compara valores crudos y cubre la excepción funcional de la fecha de
      corte.

## Ejecución de la validación

La suite debe ejecutarse en una base de pruebas, nunca sobre producción:

```bash
.venv/bin/python /opt/odoo/19.0/odoo/odoo-bin \
    -c odoo.conf \
    -d <base_de_pruebas> \
    -u s2c_delivery_date \
    --test-enable \
    --test-tags /s2c_delivery_date \
    --stop-after-init
```

Además del resultado de la suite, se debe realizar una comprobación manual del
reporte estándar con un cliente que tenga varias facturas, despliegue completo y
exportación XLSX/PDF.