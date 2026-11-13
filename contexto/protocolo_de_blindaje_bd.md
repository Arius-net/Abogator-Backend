# Protocolo de Blindaje y Reglas de Base de Datos
**Proyecto:** AboGator v3 (Modelo Híbrido - 20 Tablas)
**Objetivo:** Prevenir inconsistencias, colisiones offline, hacks de economía y rupturas de referencias legales al usar campos JSONB.

---

## 1. Regla de Inmutabilidad del Contenido (El Efecto Mariposa)
Al agrupar veredictos, evidencias y preguntas en un campo `JSONB` dentro de la tabla `tarjetas`, una edición descuidada corromperá los Juicios de Apelación pendientes.

*   **PROHIBIDO:** Hacer `UPDATE tarjetas SET jsonb_data = ... WHERE id = X`.
*   **MANDATORIO (Insert-Only):** Cuando el Back-office edite una tarjeta:
    1. El backend hace un `UPDATE` en la tarjeta vieja para poner `activa = false`.
    2. Hace un `INSERT` de la nueva tarjeta con un nuevo UUID, incrementando el campo `version` (ej. de 1 a 2), y la marca como `activa = true`.
*   **Resultado:** Los usuarios que fallaron la versión 1, leerán la versión 1 en su apelación. Los nuevos Sprints descargarán la versión 2.

## 2. Transaccionalidad Estricta (Bloqueo Pesimista)
Con 5,000 usuarios concurrentes, si un usuario toca el botón de "Comprar Comodín" 10 veces en un segundo por un lag de su red, podría gastar monedas que no tiene o duplicar compras (Condición de Carrera).

*   **PROHIBIDO:** Leer las monedas, restarlas en la memoria de Python (FastAPI) y luego hacer un `UPDATE`.
*   **MANDATORIO:** Usar `SELECT ... FOR UPDATE` en SQLAlchemy. Esto bloquea la fila del usuario a nivel de base de datos durante la transacción.
*   **Ejemplo de Flujo Seguro (Regla RN04):**
    ```sql
    BEGIN;
    SELECT monedas FROM usuarios WHERE id = X FOR UPDATE;
    -- FastAPI valida si le alcanza. Si sí:
    UPDATE usuarios SET monedas = monedas - 60, inventario = ... WHERE id = X;
    INSERT INTO movimientos_economia (usuario_id, cantidad, saldo, motivo) ...;
    COMMIT;
    -- Si falla, FastAPI ejecuta ROLLBACK;
    ```

## 3. Integridad Estricta de Campos JSONB (Schema Drift)
PostgreSQL no valida la estructura interna de un campo JSONB. Si el frontend espera `{"vidas_delta": -1}` y el backend guarda `{"vida_restada": 1}`, la app móvil va a crashear en producción.

*   **MANDATORIO:** NUNCA inyectar diccionarios crudos a la base de datos.
*   **MANDATORIO:** Todo campo JSONB (`tarjetas.contenido_json`, `usuarios.inventario`, `usuarios.reto_diario`) DEBE tener un modelo estricto en **Pydantic** dentro de FastAPI.
*   **Proceso:** El dato entra a FastAPI -> Pydantic lo valida y rechaza llaves faltantes/sobrantes -> Se convierte a JSON -> Se inserta en PostgreSQL.

## 4. Idempotencia y Sincronización Offline-First (Regla RN15)
El jugador resuelve un Sprint sin internet (en el metro). Al reconectarse, la app envía sus respuestas. Si la red parpadea y la app manda el mismo paquete dos veces, el jugador podría perder 2 vidas por un solo error.

*   **PROHIBIDO:** Usar llaves primarias autoincrementables (`SERIAL`) para entidades que nacen en el celular (como `respuestas`, `intentos`, `usos_comodin`).
*   **MANDATORIO:** El cliente móvil (Flutter) DEBE generar un `UUIDv4` para cada respuesta.
*   **MANDATORIO:** El backend debe usar `ON CONFLICT DO NOTHING` al insertar. Si el mismo UUID llega dos veces, PostgreSQL ignora silenciosamente el segundo intento, protegiendo los indicadores y la economía.

## 5. Veracidad del Tiempo (Anti-Hacks de Reloj)
Los usuarios suelen cambiar la hora de su teléfono para engañar a los juegos, saltarse los tiempos de espera y recargar vidas instantáneamente.

*   **PROHIBIDO:** Confiar en los campos de fecha (`timestamp`) que vengan en el JSON del cliente móvil.
*   **MANDATORIO (Regla RN01):** Toda recarga de vidas, asignación de fecha de vencimiento de apelaciones (`proxima_revision`) y cálculo de rachas DEBE generarse usando el reloj del servidor de la base de datos (`now()` en Postgres o `datetime.utcnow()` en FastAPI).

## 6. Cumplimiento Legal INAI / ARCO (Soft-Deletes)
Si un usuario solicita eliminar su cuenta, borrarlo inmediatamente con un `DELETE` rompe las métricas del juego e infringe políticas de retención temporal.

*   **PROHIBIDO:** Ejecutar `DELETE FROM usuarios WHERE id = X;`.
*   **MANDATORIO:** Cambiar `estado_cuenta = 'pendiente_borrado'` y registrar el `eliminado_en = now()`.
*   **Proceso de Purga:** Un script automático (Cron job) en el servidor barrerá cada noche la tabla de usuarios. Si un usuario lleva más de 30 días en `pendiente_borrado`, el script procederá a anonimizar sus datos (cambiar nombre a "Usuario Eliminado", borrar email) en lugar de borrar la fila, manteniendo vivas las estadísticas de los Sprints jugados.