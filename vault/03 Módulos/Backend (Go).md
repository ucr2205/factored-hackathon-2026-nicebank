---
tags: [modulo, backend]
estado: funcionando
dueño: Líder
---

# Backend (Go)

> [!tip] En simple
> Es el **servidor** que recibe los mensajes del chat y de la consola, comprueba quién eres, decide qué hacer y
> guarda todo. Está escrito en **Go** porque es rápido, simple de desplegar (un solo binario) y fácil de testear.

## Qué contiene (`backend/internal/`)

| Paquete | Para qué | Nota |
|---|---|---|
| `auth` | Verifica el token de Keycloak y saca `customer_ref` (opaco), roles y nivel (`acr`) | [[Identidad y login (Keycloak)]] |
| `pii` | Descifra nombres (AES-256-GCM) solo en memoria | [[Seguridad]] |
| `notify` | Correos al cliente: bandeja de salida, plantilla HTML, SMTP | [[Notificaciones por correo]] |
| `store` | Conexión a Postgres; `WithCustomer` activa el filtro por cliente | [[Base de datos y RLS]] |
| `orchestrator` | El ciclo Entender → Decidir → Actuar → Verificar → Escalar | [[Orquestador]] |
| `policy` | Lee y aplica `disputes.yaml` | [[Motor de políticas]] |
| `tools` | Buscar transacciones, abrir caso, bloquear tarjeta, sugerir agentes | [[Herramientas del banco]] |
| `llm` | Interfaz del modelo de lenguaje: DeepSeek real + versión simulada | [[LLM]] |
| `mlclient` | Llama a ml-service con timeout y reintentos | [[ml-service (clasificador)]] |
| `guard` | Enmascara datos personales y detecta prompt injection | [[Seguridad]] |
| `audit` | Escribe cada paso en `audit_events` | [[Observabilidad]] |
| `telemetry` | Trazas (OpenTelemetry) y métricas (Prometheus) | [[Observabilidad]] |
| `httpapi` | Rutas HTTP, roles, CORS, errores | abajo |
| `contract` | Formas JSON de la API | [[Contratos entre módulos]] |

## Rutas de la API

| Ruta | Quién | Qué hace |
|---|---|---|
| `POST /api/chat` | cliente | Un turno de conversación (`?mode=baseline` para el baseline) |
| `POST /api/chat/confirm` | cliente | Confirma o cancela una acción propuesta |
| `GET /api/sessions/{id}` | cliente | Recupera la conversación (tras el step-up) |
| `GET /api/me/overview` | cliente | Tarjetas y movimientos recientes |
| `GET /api/handoffs`, `/{id}`, `POST /{id}/claim` | agente | Cola de casos, detalle, tomar caso |
| `POST /api/handoffs/{id}/identity` | agente que tomó el caso | Revela nombre y referencia del cliente (queda auditado) |
| `GET /api/sessions/{id}/audit` | agente/supervisor | Línea de tiempo de auditoría |
| `GET /api/admin/config`, `/summary` | supervisor | Configuración activa y resumen de turnos |
| `GET /api/health`, `/api/ready`, `/metrics` | infra | Salud, dependencias, métricas |

## Confiabilidad

Timeout de 2 s y máximo 2 reintentos al llamar a ml-service (y su respuesta se lee con un tope de 64 KB); si
falla, **escala a humano** con motivo "falla técnica" en vez de inventar. DeepSeek tiene timeout de 8 s, respaldo
en Pro y luego en el simulado. Sesión expira tras 15 min sin actividad.

## Cómo probarlo

```bash
cd backend && go test ./...     # 24 funciones de test (políticas, guardas, LLM, extracción en paralelo, cifrado, correos)
go run ./cmd/llmcheck           # comparación de LLM (16 mensajes; DeepSeek solo si hay DEEPSEEK_API_KEY)
make smoke                      # 9 escenarios (22 comprobaciones) de punta a punta contra la API
```

## Pendientes

- [x] Proveedor LLM real detrás de `llm.Provider` (DeepSeek, ADR 0004)
- [ ] Tests de integración: sesión expirada, caída de ml-service, RLS en Go
- [ ] Cerrar/resolver un caso desde la consola; vista "Mis disputas" para el cliente
- [ ] Límite de tasa por usuario (producción)
