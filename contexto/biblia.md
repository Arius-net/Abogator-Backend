# Documento Maestro del Proyecto: AboGator v3

**Institución:** Universidad Politécnica de Chiapas (Suchiapa, Chiapas, México)
**Equipo de Desarrollo:** José Juan Ramos Cabrera, Sayd Alexandro Quevedo Flores, Alexander Jesús Jiménez León.
**Fecha de Actualización:** Noviembre 2026
**Versión:** 3.0 (Release Candidate v1.1.0) - Arquitectura Híbrida Optimizada

---

## 1. Visión General del Proyecto
**AboGator** (motor técnico *LawSwipe*) es una plataforma cliente-servidor gamificada diseñada para enseñar marcos normativos legales (licencias Open Source, privacidad de datos, delitos informáticos, contratos) a desarrolladores de software y estudiantes.
El juego emula un simulador de Startup donde el jugador actúa como el CTO. A través de una mecánica de "Swipe" de tarjetas (estilo Tinder), el usuario toma decisiones legales que impactan directamente los indicadores financieros y de riesgo de su empresa.

---

## 2. Stack Tecnológico e Infraestructura
*   **Backend:** Python con **FastAPI**. Uso intensivo de **Pydantic** para validación estricta de esquemas (especialmente payloads JSONB).
*   **Base de Datos:** **PostgreSQL 16** alojada en **AWS RDS**.
*   **ORM:** **SQLAlchemy** (Core & ORM) para manejar modelos híbridos (Relacional 3NF + JSONB).
*   **Frontend (Móvil/Tablet):** **Flutter** (Android/iOS). Soporte responsivo para tablets (riel de navegación, hojas laterales).
*   **Arquitectura de Red:** **Offline-First**. El móvil usa SQLite (sqflite/drift) como caché local y una cola de sincronización en segundo plano (*Background Sync Worker*) para enviar respuestas al backend al recuperar la red.
*   **Autenticación:** **JWT** (RFC 7519) con rotación de Refresh Tokens. Encriptación de contraseñas con **bcrypt**.
*   **Servicios Externos:** **Resend** (correos transaccionales) y **PostHog** (Analítica de eventos).
*   **Notificaciones:** Firebase Cloud Messaging (FCM) y APNs.

---

## 3. Mecánicas de Juego y Gamificación

### 3.1 Swipe en 4 Direcciones
El usuario procesa "casos" deslizando tarjetas:
*   ➡️ **Derecha (Legal):** Acción permitida.
*   ⬅️ **Izquierda (Ilegal):** Infrige la ley o licencia.
*   ⬆️ **Arriba (Condicional):** Legal solo si se modifica un contrato o se da atribución.
*   ⬇️ **Abajo (Escalar):** Se debe mandar al departamento jurídico.
*   *Respuesta Parcial:* Tomar una decisión segura pero innecesaria (ej. escalar algo que era claramente ilegal). Otorga puntos mínimos (3 XP) y no quita vida.

### 3.2 HUD (Indicadores de la Startup)
El juego monitorea 4 barras vivas (0 a 100): **Presupuesto, Reputación, Velocidad y Riesgo Legal**.
*   Cada veredicto aplica "Deltas" (ej. Riesgo +25, Velocidad -10).
*   **Condición de Quiebra (Game Over):** Si el *Riesgo Legal* llega a 100 o el *Presupuesto* llega a 0, la Startup quiebra. El sprint se reinicia perdiendo el progreso.

### 3.3 Micro-interacciones (Evidencias y Dilemas)
*   **Evidencias:** Algunas tarjetas ocultan un código fuente (`.dart`, `.json`). El usuario debe tocar la tarjeta para girarla y **subrayar con el dedo la línea infractora** antes de poder deslizar. Acierto = +5 XP.
*   **Micro-pregunta (¿Por qué?):** Tras un acierto, un modal rápido exige justificar el motivo para evitar adivinanzas al azar. Acierto = +5 XP.

### 3.4 El Jefe (Examen Final)
El último sprint de cada módulo es un nivel de crisis temporal contra un Jefe (ej. Inspectora Vega, 100 HP).
*   El usuario tiene tiempo límite (15s por decisión).
*   **Contraargumentos:** Al deslizar bien, el Jefe replica. El usuario debe elegir el fundamento legal en 8s para asestar un golpe (-20 HP). Fallar quita una vida.
*   No se permiten comodines.

### 3.5 Retención: Buzón de Apelaciones
*   Cada error en el juego resta 1 vida y archiva la tarjeta.
*   **Repetición Espaciada:** El caso vuelve como un juicio a los **3, 7 y 14 días**.
*   Si el usuario gana el juicio, avanza de etapa y **recupera 1 vida gratis**.

### 3.6 Economía y Comodines (Tienda)
El usuario puede gastar monedas en 4 ventajas:
1.  **Lupa de Auditor:** Resalta en amarillo palabras trampa en la tarjeta.
2.  **Abogado Senior:** Traduce el caso a la ley exacta (ej. LFPDPPP).
3.  **Amparo / Fianza:** Escudo que absorbe el siguiente error (salva la vida, pero los indicadores de la Startup sí sufren daño).
4.  **Congelar Racha:** Mantiene la racha intacta 1 día sin jugar.

---

## 4. Reglas de Negocio (El Core del Backend)

*   **RN01 (Integridad Temporal):** Regeneración de vidas (1 cada 2h), rachas y vencimientos de apelación se calculan EXCLUSIVAMENTE con el reloj del servidor Postgres/FastAPI (Evita Time-Drifting del móvil).
*   **RN02 (Progresión N-1):** Validado en backend. El sprint N no entrega datos si el N-1 no está "completado".
*   **RN03 (Jefe sin ayudas):** Bloqueo por código de endpoints de uso de comodines durante el examen.
*   **RN04 (Transaccionalidad ACID):** Mutaciones de vidas, monedas o tienda usan `SELECT ... FOR UPDATE` para bloquear la fila del jugador. Todo cambio ocurre en una sola transacción o se hace `ROLLBACK`.
*   **RN05 (Quiebra instantánea):** Si al aplicar un delta los indicadores tocan sus límites, el intento se marca como "quebrado" y detiene la recompensa.
*   **RN10 (Repetición Espaciada):** Ganar apelaciones reprograma a la siguiente etapa (+7, +14). Perderlas reinicia el castigo a la etapa 1 (+3 días).
*   **RN14 (Consentimiento INAI):** Se exige aceptar el aviso explícitamente y se registra versión, IP y timestamp exacto.
*   **RN15 (Idempotencia Offline):** Los `_id` de los swipes los genera el cliente (Flutter) como UUIDv4. Si la red falla y envía el mismo paquete dos veces, Postgres usa `ON CONFLICT DO NOTHING` para evitar duplicar el cobro de vidas.

---

## 5. Arquitectura de Base de Datos (Modelo Híbrido - 20 Tablas)

Se optó por una **Desnormalización Estratégica**. Se mantiene un modelo relacional 3NF estricto para economía, usuarios y reglas legales, pero se utiliza el motor **JSONB** de PostgreSQL para empaquetar el contenido narrativo, garantizando lecturas masivas y velocidad extrema para el modo Offline-First.

### Dominios de la BD:
1.  **Contenido:** `modulos`, `sprints` (embebe el escenario del jefe en JSONB), `tarjetas` (embebe veredictos, impactos, evidencias y preguntas en JSONB).
2.  **Usuarios y Seguridad:** `usuarios` (embebe preferencias, inventario y progreso del reto diario en JSONB), `consentimientos`, `sesiones_refresh`, `restablecimientos_contrasena`, `dispositivos_push`.
3.  **Juego:** `progreso_sprints`, `intentos` (embebe los UUIDs de tarjetas asignadas en JSONB), `respuestas`.
4.  **Economía:** `comodines`, `movimientos_economia` (libro mayor inmutable de auditoría, embebe detalles de compra).
5.  **Apelaciones:** `apelaciones`, `juicios_apelacion`, `notificaciones`.
6.  **Logros:** `insignias`, `usuario_insignias`, `certificados`, `auditoria_admin`.

---

## 6. Protocolo de Blindaje y Seguridad (Reglas de Oro)

Para evitar que el uso de JSONB rompa el sistema en producción, el backend debe acatar estas leyes inviolables:

1.  **Inmutabilidad del Contenido (El Efecto Mariposa):**
    *   *Prohibido:* Hacer `UPDATE` sobre el JSONB de una tarjeta.
    *   *Mandatorio:* Si el Back-office edita una tarjeta, se debe insertar una fila nueva con `version + 1` y marcar la vieja como `activa = false`. Así los juicios de apelación históricos del usuario nunca pierden sentido ni se corrompen.
2.  **Bloqueo Pesimista (Anti-Hack de Economía):**
    *   *Mandatorio:* Toda mutación económica en SQLAlchemy DEBE usar `.with_for_update()`. Evita condiciones de carrera si el usuario spamea el botón de comprar.
3.  **Integridad JSONB mediante Pydantic:**
    *   *Mandatorio:* Postgres no valida qué hay dentro del JSONB. FastAPI debe usar modelos estrictos de Pydantic para validar cada diccionario entrante/saliente antes de tocar la base de datos (Schema Drift Prevention).
4.  **Soft-Deletes (Cumplimiento INAI/ARCO):**
    *   *Prohibido:* Hacer `DELETE FROM usuarios`. Destruye la integridad referencial y las métricas.
    *   *Mandatorio:* Cambiar `estado_cuenta = 'pendiente_borrado'`. Un cron job a los 30 días se encarga de anonimizar los datos (cambiar correo y nombre), reteniendo los logs estadísticos de las partidas jugadas.
```eof
