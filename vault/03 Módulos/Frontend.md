---
tags: [modulo, frontend]
estado: funcionando
dueño: Líder
---

# Frontend

> [!tip] En simple
> La **aplicación web** que ven el cliente, el agente y el supervisor. Hecha con **React 19 + Vite + TypeScript**,
> componentes **MUI**, íconos **Lucide** e identidad **NiceBank** (burgundy y blanco). Textos en ES y PT.

## Pantallas

| Pantalla | Quién | Qué muestra |
|---|---|---|
| Login | todos | Tema NiceBank en Keycloak (logo, panel con auras animadas, selector de idioma, recuperar contraseña) |
| Inicio del cliente | cliente | Tarjeta burgundy con "Hola, {nombre}", sus tarjetas y estado; movimientos recientes (tocar uno inicia la disputa) |
| Chat | cliente | Conversación, candidatas para elegir, confirmación, aviso de código, chips "✅ Verificado" y "especialista". El **código 2FA se pide en una ventana sobre el chat** (ver abajo) |
| Casos (cola) | agente | Handoffs por prioridad, motivo, idioma y cola con nombre legible ("Fraudes · español") |
| Detalle del caso | agente | Pedido del cliente (enmascarado), hechos verificados, acciones, preguntas abiertas, reglas, agentes sugeridos, botón "Mostrar identidad" (solo tras tomar el caso) y auditoría en español |
| Supervisión → **Resumen** | supervisor | 8 KPIs y 7 gráficas por periodo (24 h, 7 días, 30 días, todo): resueltas sin una persona, escalamientos, tiempos, cola, asistente vs baseline, reglas, embudo y tiempo por paso. Detalle en [[Observabilidad#Resumen del supervisor (la forma más fácil)]] |
| Supervisión → **Configuración y reglas** | supervisor | Configuración activa y la política explicada en español |

## Barra de navegación

- **Barra burdeos oscuro** con el mismo degradado del login (desde el 1 oct; antes era blanca). Logo con "Nice"
  en blanco y "Bank" en el rosa del logo, y un subtítulo según el rol ("Centro de atención" para el personal).
- **Pestañas con ícono**: *Chat* (cliente), **Casos** (antes decía "Consola"; agentes y supervisor) y *Supervisión*.
  En el celular solo se ven los íconos.
- **Menú de la cuenta**: avatar con la inicial, nombre de usuario y rol (Cliente, Agente, Supervisor) y **Cerrar
  sesión** dentro del menú.

## Código de verificación (2FA) sin salir de la página

Bloquear una tarjeta pide el código de la app autenticadora. Desde el 1 oct se pide en una **ventana sobre el
chat** (fondo desenfocado) en vez de llevar al cliente a otra página:

1. El cliente confirma el bloqueo; el backend responde `step_up_required`.
2. Se abre la ventana *Verificación de seguridad* con la página de código de Keycloak adentro (solo la tarjeta, sin
   el panel de marca). El navegador de login (`oidc-client-ts`) hace el mismo flujo seguro de siempre (PKCE).
3. Al escribir el código, Keycloak vuelve a `/stepup-callback.html`, que le pasa la respuesta a la app, y el
   bloqueo se confirma solo con el nuevo token. La conversación nunca se recarga.
4. **Cancelar** cierra la ventana y deja la acción pendiente. Si la ventana no carga en 8 s aparece *"Ábrelo en
   pantalla completa"*, que usa el flujo anterior (ir a Keycloak y volver al chat).

Archivos: `src/auth/modalNavigator.ts`, `src/auth/StepUpDialog.tsx`, `public/stepup-callback.{html,js}`. Por qué es
seguro: [[Seguridad#Capas de protección]].

## Menos blanco (1 oct)

Fondo de página rosado muy suave, bordes rosados, encabezados de tabla en rubor, secciones con **barra de acento
burdeos** e ícono en círculo, KPIs con borde superior burdeos (el principal con el degradado) y la cabecera del
chat en burdeos. Los componentes compartidos están en `src/components/Panels.tsx` (`Section`, `Stat`,
`IconBadge`). Las gráficas usan `@mui/x-charts` y solo se descargan al abrir el Resumen; sus colores están
validados para daltonismo.

## Consola del agente en español claro

La auditoría ya no muestra frases técnicas en inglés: cada paso se traduce a una frase simple. Por ejemplo:

| Antes (técnico) | Ahora (lo que ve el agente) |
|---|---|
| `handoff 397c1442-… to queue disputes_es (reason …)` | *Caso 397C1442 enviado a la cola Disputas · español · motivo: …* |
| `label=unrecognized_charge confidence=0.90 …` | *Clasificó el mensaje como «Cargo no reconocido» con 90% de confianza* |
| `executed open_dispute_case -> DSP-000123` | *Se ejecutó: abrir la disputa (DSP-000123)* |
| `DISP-ESC-01` | *Monto alto: posible fraude* (el código queda en la ayuda emergente) |

- Las **fuentes** de cada hecho verificado y los **nombres de acciones** también están en español ("movimientos de
  la tarjeta", "Tarjeta bloqueada").
- El interruptor **"Ver detalle técnico"** muestra lo de siempre para auditores y el equipo: ids completos, el texto
  original, los códigos de regla y el enlace a la traza en Jaeger.
- Archivos: `features/console/auditText.ts` (traducción de la auditoría) y `features/console/labels.ts` (nombres).

> [!note] En curso: prioridad con tiempo de espera
> El backend ya ordena la cola por **prioridad** y, dentro de cada prioridad, por **quién lleva más tiempo
> esperando** (y devuelve cuándo se tomó cada caso). La columna de la pantalla se está rediseñando.

## Supervisión explicada

La pantalla de supervisión se rediseñó para que la entienda alguien que no leyó el YAML:

- **"Qué resuelve solo y qué pasa a una persona"**: por cada tipo de caso, qué acción hace el asistente, hasta qué
  monto y plazo, y a qué equipo pasa si no puede.
- **Garantías globales** como frases: *"Nunca puede hacer reembolsos, mover o transferir dinero ni mostrar datos de
  otro cliente"*, *"Ninguna acción se ejecuta sin que el cliente la confirme"*, etc.
- **Nombres amigables**: el modelo ("DeepSeek Flash" o "Simulado"), el clasificador ("Palabras clave
  (provisional)") y la fecha del demo (los datos sintéticos terminan ese día).
- Tiempos con su explicación: "Tiempo de respuesta típico (p50)" y "Respuestas más lentas (p95)".
- Lo técnico (ids de reglas, versiones exactas) queda detrás de **"Ver detalle técnico"**.
- Archivo nuevo: `features/supervisor/policyText.ts` (lee la política y la explica en español).

> [!info] Estado del código
> El rediseño de la barra de navegación y de supervisión está en la copia de trabajo del líder y todavía **no tiene
> commit** (27 sep); la consola en español ya está en `main`.

## Marca

El logo sale de una sola imagen, `docs/brand/nicebank-logo-source.jpg`. Los tamaños que usa cada pieza se generan
con `poetry run python scripts/build_brand_assets.py`: favicon y marca de la app (`frontend/public/brand/`), el
logo del login de Keycloak y el del encabezado de los correos. No se editan a mano: se cambia la imagen fuente y se
vuelve a correr el script.

## Cómo está organizado (`frontend/src/`)

| Carpeta | Contenido |
|---|---|
| `app/` | Rutas, tema NiceBank, textos ES/PT (`i18n.tsx`) |
| `auth/` | Login PKCE, step-up, retomar el chat después del código |
| `api/` | Tipos del contrato y cliente HTTP |
| `features/chat/` | Chat, panel de cuentas, lógica en `useChat.ts` |
| `features/console/` · `features/supervisor/` | Pantallas del personal (se cargan solo si eres agente/supervisor) |
| `components/` | Marco de la app, auras animadas |

> [!note] Seguridad en el navegador
> Los tokens viven **en memoria** (no en localStorage). Esconder botones por rol es solo comodidad: **los
> permisos reales los aplica el backend**.

## Cómo probarlo

```bash
cd frontend && npm run dev      # http://localhost:5173
npm run build                   # chequeo de tipos + build de producción
```
El contenedor `frontend` sirve el build en http://localhost:8088.
