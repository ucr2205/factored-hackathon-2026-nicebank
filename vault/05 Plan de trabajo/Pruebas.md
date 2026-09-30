---
tags: [plan, pruebas, qa]
---

# Plan de trabajo — Pruebas

La estrategia completa está en [[Estrategia de pruebas]]; aquí el listado accionable.

## Unitarias (rápidas, sin servicios)

- [x] Motor de políticas: automático, escala, fuera de plazo, estado inválido, tarjeta robada (`policy_test.go`)
- [x] Extracción del LLM simulado: montos, fechas relativas, elección de candidata (`fake_test.go`)
- [x] Enmascarado (incluye documentos, CPF y teléfonos con etiqueta) y detección de prompt injection (`guard_test.go`)
- [x] Fechas sin año = última vez que ocurrieron ("23/12" → 23/12/2025), en el simulado y en DeepSeek (`fake_test.go`, `deepseek_test.go`)
- [x] Proveedor DeepSeek con servidor falso: extracción, respaldo Flash → Pro → simulado, fechas imposibles, redacción que conserva los datos (`deepseek_test.go`)
- [x] Extracción en paralelo: corre mientras clasifica, se cancela al descartarla, cuenta el costo si ya terminó (`speculative_test.go`)
- [x] Cifrado de identidad: ida y vuelta, valor atado a su fila y columna, llave inválida (`pii_test.go`)
- [x] Correos: escapa HTML, un solo idioma, respaldo a español, logo incrustado, SMTP con redirección (`notify_test.go`)
- [x] Comparación de LLM con 16 mensajes etiquetados (`go run ./cmd/llmcheck`)
- [ ] Formateo de montos y fechas ES/PT en el frontend (hoy solo se evitó que valores malos rompan la pantalla) — Líder
- [ ] Contratos Pandera (filas válidas e inválidas) — P2
- [ ] Clasificador: formato de respuesta y umbral — P3

## Integración (con Postgres y servicios)

- [ ] **RLS en Go**: `cliente01` no lee filas de `cliente02` en ninguna tabla — Líder
- [ ] **Sesión expirada** → `401 session_expired` (con `SESSION_IDLE_MINUTES=0`) — Líder
- [ ] **Caída de ml-service** → escala con `ESC-TECH-01`, sin inventar — Líder
- [ ] **Verificación fallida** de una escritura → no dice "listo", escala — Líder
- [ ] ETL idempotente + llegada tardía (`make test-etl`) — P2
- [ ] ml-service real: contrato C2 y p95 < 100 ms — P3

## De punta a punta (API)

- [x] `make smoke` — 10 escenarios (25 comprobaciones): normal, ambiguo, duplicado PT, no soportado PT, prompt injection, bloqueo sin TOTP, RLS entre clientes, baseline, identidad seudonimizada, correos, explicar antes de disputar
- [x] Correos por la bandeja de salida llegan a Mailpit desde `NiceBank <nicebank@evon.solutions>` (smoke 9)
- [x] Consola: tomar caso, revelar identidad solo el agente que lo tomó, auditoría del reveal (smoke 8)
- [ ] Recuperación de contraseña automatizada (Mailpit API + TOTP) — Líder
- [ ] Correo de recuperación de contraseña probado con el **servidor real** — Líder
- [ ] Consola: roles (agente no entra a supervisión) y cerrar/resolver caso cuando exista — Líder

## Seguridad

- [x] Roles aplicados en el backend (403 cruzados)
- [ ] Prompt injection: 10 variantes ES/PT/EN en el set adversarial — P4
- [ ] Token vencido, token de otro realm, token sin `customer_ref` o con una referencia inventada — Líder
- [x] Identidad: el token no trae `customer_id`; solo el agente que tomó el caso ve el nombre, con auditoría — Líder (smoke 8)
- [x] Endurecimiento: enmascarado ampliado, límite de respuestas de ml-service, limpieza de trazas por patrón, comillas SQL en `00_app_role.sh`, CSP y cabeceras en nginx (commit `2468283`) — Líder
- [ ] Revisión con `/security-review` o similar antes del freeze — Líder

## Evaluación (calidad del sistema)

- [ ] ~200 casos held-out, sistema vs baseline, 3 corridas — P4
- [ ] Desglose por idioma y segmento; análisis de disparidades — P4 + P3

## Rendimiento — [[Pruebas de carga con JMeter]]

- [x] Plan `qa/jmeter/nicebank-load.jmx` + usuarios de carga (corregido: ruta del CSV y login con formulario)
- [x] Perfil de humo (5 usuarios, 60 s) — Líder: **0 errores**
- [x] Humo con el LLM real (DeepSeek Flash) vs simulado: chat p50 970 ms / p95 1.299 ms vs ~15–65 ms — Líder
- [ ] Perfil de carga (25 usuarios, 10 min) — P4 + Líder
- [ ] Perfil de estrés (100 usuarios) y de resistencia (1 h) — P4 + Líder
- [ ] Costo por caso con el LLM real sobre los casos held-out — P4 + P3

## Manual / exploratorio (antes del video)

- [ ] Los 3 casos de demo en ES y PT, en escritorio y celular
- [ ] Recuperación de contraseña completa
- [ ] Lectura de la traza en Jaeger y de la auditoría en la consola
