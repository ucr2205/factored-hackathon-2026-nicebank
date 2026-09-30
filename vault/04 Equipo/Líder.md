---
tags: [equipo, lider]
rol: Backend, frontend, seguridad, infraestructura y coordinación
---

# Líder

> [!tip] Tu rol en una frase
> Garantizas que el sistema **funcione, sea seguro y se levante con un comando**, y que las piezas de los demás
> **encajen**: cuidas los contratos, revisas todo lo que entra al repo y conduces los gates.

## Lo que ya está hecho (27 sep)

Backend completo (orquestador, políticas, herramientas verificadas, handoff, auditoría, trazas, métricas),
frontend (chat, cuentas, consola, supervisión, identidad NiceBank), Keycloak (PKCE, TOTP, recuperación
verificada, tema propio), Docker Compose con 9 servicios, Poetry, `AGENTS.md` y este vault. Además, el mismo día:

- **LLM real**: DeepSeek Flash + Pro de respaldo, comparados con `go run ./cmd/llmcheck` (Flash elegido), prompt
  v2 con caché y extracción en paralelo con la clasificación ([[LLM]], [[Orquestador]]).
- **Identidad seudonimizada** (ADR 0003) y **correos al cliente** (ADR 0005) con diseño NiceBank, servidor real
  con redirección y el correo de recuperación de Keycloak por la misma cuenta ([[Notificaciones por correo]]).
- **Endurecimiento de seguridad** (commit `2468283`) y marca NiceBank en app, login y correos.
- **Chat**: fechas sin año bien interpretadas y respuestas "no encontré" que dicen qué se buscó.
- **Consola** en español claro; **supervisión** y **barra de navegación** rediseñadas (estas dos, pendientes de
  commit) ([[Frontend]]).
- **Pruebas**: 35 funciones de test en Go, `make smoke` con 10 escenarios (25 comprobaciones) en verde, JMeter de
  humo con DeepSeek sin errores ([[Pruebas de carga con JMeter]]).
- Repo privado en GitHub: `ucr2205/repo-hackhaton` (rama `main`).

## Qué te toca

| Fecha | Tarea | Hecho |
|---|---|---|
| **lun 28 sep 18:00** | Conducir el **Gate 1**: flujo confirmado por la EDA; congelar contratos C1–C6 | ☐ |
| lun 28 sep | Commit de supervisión + barra de navegación; terminar la columna de prioridad con tiempo de espera | ☐ |
| lun 28 sep | Copiar este vault al repo en `vault/` | ☐ |
| lun 28 – mar 29 sep | Esqueleto de `eval/` a partir de `smoke_chat.py` para que P4 solo agregue casos y métricas | ☐ |
| lun 28 – mar 29 sep | Tests de integración en Go: sesión expirada, caída de ml-service → escala, RLS | ☐ |
| mar 29 – mié 30 sep | Integrar el proveedor LLM real (con P3), con enmascarado y costo | ☑ (27 sep) |
| mar 29 – mié 30 sep | Agente: **cerrar/resolver** un caso tomado; cliente: vista **"Mis disputas"** | ☐ |
| mar 29 – mié 30 sep | Probar el correo de recuperación con el servidor real; decidir logos de Visa/Mastercard (theSVG o Flaticon/kit de Mastercard) | ☐ |
| **mié 30 sep** | **Gate 2**: caso normal con los componentes reales que ya existan | ☐ |
| mié 30 sep | `/embed` real + carga de `kb_chunks` para destrabar la RAG | ☐ |
| jue 1 oct | Integrar el loader de P2 y el ml-service real de P3 | ☐ |
| **vie 2 oct** | **Gate 3**: todo implementado + primera evaluación | ☐ |
| vie 2 – sáb 3 oct | Carga con JMeter (perfiles de carga y estrés; el de humo ya pasó) y ajuste | ☐ |
| sáb 3 oct | Preparar despliegue: URL pública para los enlaces de los correos, URLs de Keycloak, HTTPS, secretos en un gestor, quitar `eval-harness` | ☐ |
| **dom 4 oct 20:00** | **Code freeze**; evaluación final; ensayo del video | ☐ |

Los listados completos están en [[Infraestructura]], [[Código]] y [[Pruebas]].

## Cómo revisar un aporte (checklist)

- [ ] ¿Respeta los contratos? ([[Contratos entre módulos]])
- [ ] ¿Tiene test o script reproducible? ¿`make smoke` sigue en verde?
- [ ] ¿Código y docs en inglés? ¿Python con Poetry (`pyproject.toml` + `poetry.lock`)?
- [ ] ¿No sube `data/`, `.env`, credenciales ni `team/`?
- [ ] ¿No debilita ningún invariante de [[Seguridad]]?

## Qué actualizar en cada gate

1. `AGENTS.md` del repo (estado y workstreams) — es lo que leen los asistentes de IA del equipo.
2. Este vault: [[00 Inicio#Estado hoy (27 sep, día 2 de 10)]] y las casillas de cada persona.
3. El documento de seguimiento compartido.

## Prompts útiles

> [!example] Revisión
> *"Revisa los cambios sin commit contra AGENTS.md: contratos, invariantes de seguridad, idioma y Poetry. Lista
> problemas por severidad con archivo y línea. No modifiques nada."*

> [!example] Commit (con opencode)
> *"Crea commits atómicos Conventional Commits en inglés para los cambios actuales, agrupados por capa. No hagas
> push. No incluyas data/, .env, team/ ni archivos de resultados. Sin líneas Co-Authored-By ni atribución a IA."*
> Si lo lanza otro asistente, usa el `OPENCODE_CONFIG` de solo git: [[Cómo trabajar con opencode o Claude Code]].
