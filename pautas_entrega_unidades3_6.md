# Buenas prácticas de trabajo en GCP
**Pautas de entrega - Unidades 3, 4, 5 y 6**  
**Curso:** Computación en la Nube para IA  
**Profesora:** Diana Jaimes  

---

## 1) Propósito
Este documento define reglas comunes para trabajar en GCP de forma ordenada, colaborativa y con control de costos durante las Unidades 3, 4, 5 y 6 del curso. Aplica a todos los estudiantes con acceso a los proyectos del curso, y en particular al uso de:

* **Unidad 3:** Agent Platform (antes Vertex AI)
  * Workbench (notebooks de exploración y análisis de sesgo/SHAP).
* **Unidad 4:** Agent Platform (antes Vertex AI) - Training Job, Endpoints y Cloud Functions.
* **Unidad 5:** FastAPI + Docker + Cloud Run.
* **Unidad 6:** Apache Airflow (orquestación), sobre Agent Platform y BigQuery.

---

## 2) Organización por equipos (ternas)
* Los entregables se realizan por grupos de 3 personas, desde la Unidad 3 hasta la Unidad 6 (el mismo grupo se mantiene, salvo ajuste explícito de la profesora).
* Aunque varias personas tengan acceso al mismo proyecto de GCP, la responsabilidad de los recursos y de los entregables es del grupo, no individual.

### Asignación de grupos (según Excel)
* Cada estudiante debe registrar su valor en la columna **Grupo** durante la primera sesión (Unidad 3). No se aceptan registros tardíos salvo casos de fuerza mayor coordinados con la profesora.
* Los números de grupo deben ser únicos y consecutivos: si ya existen 1 y 2, el siguiente grupo nuevo debe ser 3, y así sucesivamente.
* Si el estudiante ya tiene una terna definida, debe indicar `Grupo 1`, `Grupo 2`, `Grupo 3`...
* Si el estudiante no tiene grupo, debe colocar `0`. La profesora agrupará a los estudiantes con $Grupo = 0$ por orden de disponibilidad, también en la primera sesión.

---

## 3) Entrega de los laboratorios (plataforma INTU)
* Todo entregable de las Unidades 3-6, sin excepción, se sube a la plataforma INTU. No se aceptan entregas por correo, WhatsApp, Drive suelto, etc.
* Solo una persona del grupo sube la tarea en INTU (para evitar entregas duplicadas o inconsistentes entre integrantes).
* El entregable debe nombrar explícitamente a los tres integrantes del grupo (nombre completo) dentro del propio archivo o entrega.
* **Recomendación:** definan desde la primera sesión quién sube en INTU durante todo el curso (puede rotar por unidad, pero debe quedar claro antes del deadline de cada entrega).

---

## 4) Regla crítica de costos
En GCP, varios de los recursos que usaremos en el curso generan costo mientras existen o están activos, no solo mientras se usan. Por eso, la regla general para todo el curso (U3-U6) es:

> **Ningún recurso que genere costo continuo debe quedar activo al terminar la sesión de trabajo o el laboratorio.**

### Unidad 3: Workbench
* **Regla 1 (1 grupo = 1 instancia):** cada terna trabaja con una sola instancia de Workbench, no una por integrante.
* **Regla 2 (apagado vs. eliminado no son lo mismo):**
  * **Detener (Stop)** la instancia apaga el cómputo, pero el disco persistente sigue existiendo y sigue generando costo ($\approx \$0.04\text{/GB-mes}$ en disco estándar, $\approx \$0.17\text{/GB-mes}$ en SSD; por ejemplo, un disco de 100 GB serían $\approx \$4\text{--}17\text{/mes}$ si nunca se elimina).
  * **Eliminar (Delete)** la instancia borra también el disco, y ahí el costo llega a cero.
  * Al terminar cada sesión de trabajo, el grupo debe detener la instancia como mínimo. Al terminar el laboratorio (cuando ya no se va a volver a usar esa instancia), el grupo debe eliminarla, no solo detenerla.
* **Regla 2b (revisión):** se revisará cada mañana; instancias corriendo (no detenidas) bajan la calificación del laboratorio.
* **Regla 3 (responsabilidad):** el grupo es responsable de crear, usar, detener y eliminar su instancia. Un disco olvidado no es un costo alto por sí solo, pero es el tipo de descuido que en un entorno profesional real, multiplicado por muchos recursos, si se vuelve dinero significativo; es el hábito lo que están practicando.

### Unidad 4: Training Job, Endpoint, Cloud Function
El Endpoint es el recurso más costoso de esta unidad: queda desplegado y facturando de forma continua (con réplicas activas) hasta que se elimina explícitamente. A diferencia de un notebook, no es visible "corriendo" en pantalla, así que es fácil olvidarlo.

* **Regla 1:** al terminar la sesión o el laboratorio, el grupo debe eliminar el Endpoint (*undeploy* + *delete*) y la Cloud Function asociada.
* **Regla 2:** el Training Job no genera costo una vez termina de ejecutarse, pero el grupo debe verificar que no queden Jobs corriendo indefinidamente por error de configuración.
* **Regla 3 (responsabilidad):** igual que en U3, un solo grupo = un solo Endpoint activo a la vez.

### Unidad 5: Cloud Run / Docker
Cloud Run escala a cero cuando no recibe tráfico, así que el riesgo de costo continuo es bajo, pero no es cero: las imágenes construidas quedan almacenadas en Artifact Registry y consumen espacio (costo de almacenamiento) mientras existan.

* Al cerrar el laboratorio, el grupo debe eliminar el servicio de Cloud Run si ya no lo va a usar, y limpiar imágenes de prueba en Artifact Registry (no dejar builds acumulados con nombres genéricos).

### Unidad 6: Airflow
* Airflow corre de forma local (no en un servicio administrado de GCP), por lo que no aplica una regla de apagado/borrado en la nube para esta unidad.

---

## 5) Buenas prácticas de colaboración
* **Trabajo por terna:** cualquier integrante del grupo puede ejecutar acciones críticas (crear/detener/borrar recursos), siempre que se coordine por chat con el resto del grupo antes de hacerlo. Esto evita depender de una sola persona (si esa persona falta a una sesión, el grupo no debe quedar bloqueado).
* **Cambios con aviso:** antes de borrar o modificar un recurso del grupo, avisar y acordar con los compañeros.
* **Evidencia, capturar antes de eliminar:** como los recursos deben eliminarse al terminar el laboratorio, la evidencia del trabajo (salidas, gráficos, resultados de SHAP, respuesta del Endpoint, etc.) debe capturarse mientras el recurso todavía existe, no se puede volver a generar después de borrarlo. Cada grupo debe tomar sus capturas/evidencia antes de eliminar cualquier recurso, siguiendo lo que pida el enunciado específico de cada laboratorio.

---

## 6) Nomenclatura (obligatoria)
El objetivo es que cualquier recurso se pueda identificar rápidamente por unidad, grupo y fecha.

### Formato base (guion medio como estándar)
$$\text{u}N\text{-g}NN\text{-}\langle\text{tipo}\rangle\text{-YYYYMMDD}$$

* $uN =$ unidad (`u3`, `u4`, `u5`, `u6`)
* $gNN =$ número de grupo (`g01`, `g02`, `g03`...)
* $\langle\text{tipo}\rangle =$ tipo de recurso (ver tabla)
* `YYYYMMDD` = fecha

#### ¿Por qué guion medio y no guion bajo?
La mayoría de los recursos de GCP (nombres de instancias de Compute Engine/Workbench, buckets de Cloud Storage, servicios de Cloud Run, nombres de Endpoints, Cloud Functions) no aceptan guion bajo, solo letras minúsculas, números y guion medio. Usar guion bajo ahí directamente falla o es rechazado por la consola.

#### Excepción BigQuery
Los datasets y tablas de BigQuery son al revés: no aceptan guion medio, solo letras, números y guion bajo. Por eso, únicamente para objetos de BigQuery (datasets/tablas), el formato debe ser:
$$\text{u}N\text{\_g}NN\text{\_}\langle\text{tipo}\rangle\text{\_YYYYMMDD}$$

### Tipos de recurso por unidad

| Unidad | Recurso | Tipo | Ejemplo |
| :--- | :--- | :--- | :--- |
| **U3** | Instancia de Workbench | `wb` | `u3-g03-wb-20260224` |
| **U3** | Notebook | `nb` | `u3-g03-nb-20260224.ipynb` |
| **U3/U4** | Dataset/Tabla BigQuery (guion bajo) | `data` | `u3_g03_data_20260224` |
| **U4** | Training Job | `job` | `u4-g03-job-20260224` |
| **U4** | Endpoint | `ep` | `u4-g03-ep-20260224` |
| **U4** | Cloud Function | `fn` | `u4-g03-fn-20260224` |
| **U4/U5** | Modelo (guion bajo) | `mdl` | `u4_g03_mdl_20260224` |
| **U5** | Servicio Cloud Run | `cr` | `u5-g03-cr-20260224` |
| **U5** | Imagen (Artifact Registry) | `img` | `u5-g03-img-20260224` |
| **Todas** | Carpeta/paquete de scripts | `scripts` | `u4-g03-scripts-20260224` |
| **Todas** | Archivo SQL | `sql` | `u3-g03-sql-20260224.sql` |

### Reglas adicionales
* No usar nombres genéricos: `test`, `prueba`, `nuevo`, `final_final`.
* Si hay versiones, agregar `v1`, `v2` antes de la fecha (ej.: `u4-g03-ep-v2-20260224`).

---

## 7) Checklist obligatorio al finalizar (por grupo)
Antes de retirarse, el grupo debe verificar:

| Unidad | Verificación obligatoria |
| :--- | :--- |
| **U3** | Instancia de Workbench detenida (fin de sesión) o eliminada (fin de laboratorio). |
| **U4** | Endpoint eliminado (*undeploy* + *delete*) y Cloud Function eliminada. |
| **U5** | Servicio de Cloud Run eliminado (si ya no se usará) y sin imágenes de prueba en Artifact Registry. |
| **U6** | No aplica (Airflow corre localmente). |
| **Todas** | Sin recursos "de prueba" con nombres fuera del estándar; evidencia capturada antes de eliminar recursos; entregable final subido a INTU con nombre estándar y los tres integrantes identificados. |

---

## 8) Monitoreo de costos (para control del curso)
El control de costos se realizará desde **Cloud Billing $\rightarrow$ Reports**, filtrando por proyecto y agrupando por **Service** y **SKU** para identificar consumos anómalos.