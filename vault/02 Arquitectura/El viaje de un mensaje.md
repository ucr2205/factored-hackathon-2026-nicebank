---
tags: [arquitectura, flujo]
---

# El viaje de un mensaje

Qué pasa desde que el cliente escribe hasta que recibe respuesta, con cada decisión que toma el sistema.
Los rombos son decisiones; los recuadros inclinados son respuestas al cliente; el código entre corchetes es el
**id de la regla** que queda en la auditoría.

```mermaid
flowchart TD
    A(["El cliente escribe en el chat"]) --> B["La web envía el mensaje con el token<br/>(el token solo trae una referencia opaca)"]
    B --> C["Postgres traduce la referencia al cliente<br/>y aísla sus datos (RLS)"]
    C --> D["Se tapan datos personales:<br/>nombres, números largos, correos"]
    D --> E{"¿Intenta manipular<br/>al asistente?"}
    E -- Sí --> E1[/"Se niega con amabilidad<br/>[SEC-INJ-01]"/]
    E -- No --> F["ml-service clasifica el tipo de caso"]
    F -- "falla técnica" --> H1
    F --> G{"¿Es una disputa<br/>de tarjeta?"}
    G -- No --> G1[/"Explica qué sí puede hacer<br/>[SCOPE-01]"/]
    G -- "No está seguro" --> G2[/"Pregunta qué pasó<br/>[CLARIFY-TYPE]"/]
    G -- Sí --> X["El LLM extrae monto, fecha y comercio<br/>(solo propone, nada se da por cierto)"]
    X --> I["Busca en las tarjetas del cliente"]
    I --> J{"¿Cuántos movimientos<br/>coinciden?"}
    J -- Ninguno --> J1[/"Pide fecha, monto o comercio"/]
    J -- Varios --> J2[/"Muestra la lista y el cliente elige"/]
    J -- Uno --> K{"Motor de políticas<br/>(monto en USD, plazo, estado)"}
    J2 --> K
    K -- "Ya tiene disputa abierta" --> K1[/"Avisa el caso existente<br/>[DISP-DUPCASE-01]"/]
    K -- "Caso normal" --> L[/"¿Abro la disputa?"/]
    K -- "Monto alto o tarjeta robada" --> M[/"¿Bloqueo la tarjeta?<br/>[DISP-ESC-01 / 02]"/]
    K -- "Fuera de plazo u otro" --> H1
    L --> O{"¿Confirma?"}
    O -- No --> O1[/"No hace ningún cambio"/]
    O -- Sí --> Q["Abre el caso y lo RELEE"]
    M --> P{"¿Confirma y pasa<br/>el código TOTP?"}
    P -- Sí --> S["Bloquea y RELEE"]
    P -- No --> H1
    S --> H1
    Q --> T{"¿Se verificó?"}
    T -- Sí --> U(["Responde con el número de caso"])
    T -- No --> H1
    H1["Crea el handoff: hechos verificados,<br/>acciones, evidencia y preguntas abiertas"] --> V(["Un agente toma el caso y ve la identidad<br/>solo si la pide (queda auditado)"])

    G2 -.->|"el cliente responde"| A
    J1 -.->|"el cliente responde"| A
    G2 -.->|"tras 2 aclaraciones [ESC-CLARIFY-LIMIT]"| H1

    classDef answer fill:#fdf2f5,stroke:#7A1F3D,color:#3b0d1d
    classDef human fill:#fff4e0,stroke:#D98A00,color:#4a2f00
    classDef done fill:#e8f5e9,stroke:#2E7D32,color:#1b3d1e
    class E1,G1,G2,J1,J2,K1,L,M,O1 answer
    class H1,V human
    class U done
```

## Paso a paso, en simple

1. **Identificar** — El token del cliente no trae su número de cliente del banco, solo una **referencia opaca**
   (`cr_…`). Postgres la traduce por dentro y desde ahí cada consulta solo ve los datos de ese cliente
   ([[Base de datos y RLS]]). Ver [[Seguridad]] → *Identidad seudonimizada*.
2. **Entender** — Se tapan datos personales antes de que salgan del sistema. Si el texto intenta "hackear" al
   asistente (*"ignora tus instrucciones…"*), se bloquea (`SEC-INJ-01`).
3. **Clasificar** — [[ml-service (clasificador)]] dice qué tipo de disputa es. Si no está seguro, el sistema
   **pregunta** en vez de adivinar. Si se agotan las aclaraciones, pasa a un humano.
4. **Extraer** — El [[LLM]] (DeepSeek) saca monto, fecha y comercio. *Solo propone*: nada se da por cierto
   hasta encontrarlo en la base de datos. Para ganar tiempo, este paso arranca **al mismo tiempo** que el paso 3 y
   se cancela si el mensaje no resulta ser una disputa ([[Orquestador]]).
5. **Buscar** — Las [[Herramientas del banco]] buscan en las tarjetas **de ese cliente**. Una fecha sin año
   ("23/12") es la última vez que pasó. Si hay varias candidatas, el cliente elige; si no hay ninguna, se le dice
   **qué se buscó** y se le pide más detalle.
6. **Decidir** — El [[Motor de políticas]] aplica las reglas y devuelve una decisión con **el id de la regla**.
7. **Actuar** — Nada se ejecuta sin que el cliente **confirme**. Bloquear tarjeta además exige **código TOTP**.
8. **Verificar** — Después de escribir, se **relee** de la base de datos. Si no se puede confirmar, no se dice
   "listo": se escala.
9. **Escalar** — El agente recibe un **resumen estructurado**, nunca el chat crudo. El nombre del cliente está
   cifrado y solo lo ve el agente que **tomó** el caso, cuando lo pide; esa consulta queda en la auditoría.

Cuando se abre una disputa, se bloquea la tarjeta o el caso pasa a un especialista, el cliente además recibe un
**correo** con los mismos datos verificados ([[Notificaciones por correo]]).

Cada paso deja una fila en la **auditoría** y un tramo en la **traza** ([[Observabilidad]]).

> [!example]- Vista técnica: el caso de escalamiento como secuencia
> Ejemplo real del demo: `cliente03` escribe **"No reconozco una compra de 1.450 dólares del lunes"**.
>
> ```mermaid
> sequenceDiagram
>     actor Cli as Cliente
>     participant Web as Web app
>     participant API as Backend
>     participant ML as ml-service
>     participant LLM as LLM (DeepSeek)
>     participant DB as Postgres
>     participant KC as Keycloak
>     Cli->>Web: escribe el mensaje
>     Web->>API: POST /api/chat (token con customer_ref)
>     API->>DB: resolve_customer(ref) y fija el cliente (RLS)
>     API->>ML: ¿qué tipo de disputa es?
>     ML-->>API: unrecognized_charge
>     API->>LLM: extrae monto y fecha (texto enmascarado)
>     LLM-->>API: 1450, lunes 15/06
>     API->>DB: busca transacciones de sus tarjetas
>     DB-->>API: Electro Mundo Online, USA
>     API-->>Web: ¿Confirmas el bloqueo? (requiere código)
>     Web->>API: confirma
>     API-->>Web: 403 step_up_required
>     Web->>KC: acr_values=2
>     KC-->>Web: token con acr=2 (TOTP)
>     Web->>API: confirma otra vez
>     API->>DB: bloquea, relee, crea el handoff y lo relee
>     API-->>Web: Bloqueé tu tarjeta (BLK-…)
> ```
