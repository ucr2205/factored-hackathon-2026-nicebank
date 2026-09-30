---
tags: [inicio, mapa]
actualizado: 2026-09-27
---

# NiceBank — Documentación del equipo

> [!tip] En una frase
> Estamos construyendo un **asistente bancario que atiende disputas de tarjeta** (cargos que el cliente no
> reconoce) en **español y portugués**. La IA entiende y redacta; las **reglas escritas** deciden; el sistema
> **verifica** cada acción y, cuando hace falta, **pasa el caso a una persona** con todo el contexto.

Este vault es la memoria del equipo: qué construimos, cómo funciona cada pieza, qué le toca a cada quien y
cómo probarlo. Está escrito para entenderse sin ser experto; lo técnico está explicado paso a paso.

> [!important] ¿Cómo vamos? ¿Qué construimos y qué no?
> La foto de hoy (qué funciona, qué falta, riesgos y decisiones pendientes) está en [[Estado del proyecto]].
> El foco del producto (el problema, para quién, qué lo hace distinto y qué quedó fuera) está en
> [[Visión de producto]]: léelo antes de proponer una funcionalidad nueva.

## ¿Por dónde empiezo?

| Si eres… | Lee primero |
|---|---|
| Nuevo en el proyecto | [[El reto en simple]] → [[Visión general]] → [[El viaje de un mensaje]] |
| Líder | [[Líder]] |
| Persona 2 — Datos | [[Persona 2 - Datos]] |
| Persona 3 — IA y ML | [[Persona 3 - IA y ML]] |
| Persona 4 — Evaluación y pitch | [[Persona 4 - Evaluación y pitch]] |
| Vas a usar opencode o Claude Code | [[Cómo trabajar con opencode o Claude Code]] |

## Mapa del vault

- **El reto** — [[El reto en simple]] · [[Visión de producto]] · [[Cómo nos evalúan]] · [[Calendario y gates]]
- **Arquitectura** — [[Visión general]] · [[El viaje de un mensaje]] · [[Seguridad]] · [[Datos del proyecto]] ·
  [[Contratos entre módulos]] · [[Decisiones (ADR)]]
- **Módulos** — [[Backend (Go)]] · [[Orquestador]] · [[Motor de políticas]] · [[Herramientas del banco]] ·
  [[Identidad y login (Keycloak)]] · [[Base de datos y RLS]] · [[ml-service (clasificador)]] · [[LLM]] ·
  [[ETL y calidad de datos]] · [[Frontend]] · [[Observabilidad]] · [[Notificaciones por correo]] · [[Evaluación]]
- **Equipo** — [[Líder]] · [[Persona 2 - Datos]] · [[Persona 3 - IA y ML]] · [[Persona 4 - Evaluación y pitch]]
- **Plan de trabajo** — [[Infraestructura]] · [[Código]] · [[Pruebas]]
- **QA y rendimiento** — [[Estrategia de pruebas]] · [[Pruebas de carga con JMeter]]
- **Operación** — [[Levantar el proyecto]] · [[Problemas comunes]] · [[Credenciales y accesos]]
- **Seguimiento** — [[Estado del proyecto]]
- [[08 Glosario|Glosario]] · Plantillas: [[Reunión diaria]] · [[Decisión]] · [[Reporte de bug]]

## Estado hoy (27 sep, día 2 de 10)

- ✅ El producto funciona **de punta a punta**: chat del cliente, consola del agente, supervisión, políticas,
  acciones verificadas, código de verificación (TOTP), recuperación de contraseña y auditoría.
- ✅ **IA real conectada**: DeepSeek Flash extrae monto, fecha y comercio (Pro de respaldo). En la prueba de 16
  mensajes acertó el 100% de montos y comercios; responde en ~1 s y cuesta fracciones de centavo. En el repo el
  valor por defecto sigue siendo el simulado (`fake`). Ver [[LLM]].
- ✅ **Identidad seudonimizada**: el token no dice quién es el cliente y los nombres están cifrados; el agente
  ve la identidad solo al tomar el caso, y queda auditado. Ver [[Seguridad]].
- ✅ **Correos al cliente** (disputa abierta, tarjeta bloqueada, caso con especialista) con diseño NiceBank, en
  el idioma de la conversación. Ver [[Notificaciones por correo]].
- ✅ Consola del agente y supervisión **en español claro** (lo técnico queda detrás de "Ver detalle técnico").
- ✅ `make smoke` en verde con los escenarios 1–9 y prueba de carga con JMeter **sin errores**. Ver
  [[Estrategia de pruebas]] y [[Pruebas de carga con JMeter]].
- 🟡 Siguen **provisionales**: clasificador por palabras clave, política v0, 20 clientes de demo. Ver
  [[Visión general#Qué es real y qué es provisional]].
- 🔴 **Lo más urgente**: el arnés de evaluación con ~200 casos held-out ([[Persona 4 - Evaluación y pitch]]) y el
  clasificador real ([[Persona 3 - IA y ML]]).
- 📅 Próximo hito: **Gate 1 — lunes 28 sep, 18:00**. Ver [[Calendario y gates]].

> [!info] Dónde vive este vault
> Hoy está en la carpeta `NiceBank-Vault` que comparte el líder. Se va a copiar **dentro del repo**, en la carpeta
> `vault/` (repo privado en GitHub, rama `main`). Desde ahí se abre en Obsidian con *Open folder as vault*.

> [!info] Reglas de oro (resumen)
> Todo lo que va **dentro del repo** está en **inglés**; entre nosotros, español. Python **solo con Poetry**.
> Nunca subir `data/`, `.env` ni credenciales. Los commits los hacemos con **opencode** (Conventional Commits en
> inglés, sin líneas de "coautor IA"). Detalle en [[Cómo trabajar con opencode o Claude Code]].
