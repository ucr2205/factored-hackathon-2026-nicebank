---
tags: [equipo, herramientas, ia]
---

# Cómo trabajar con opencode o Claude Code

> [!tip] La idea
> No hace falta explicarle el proyecto a tu asistente de IA cada vez. El repo trae **`AGENTS.md`** (en inglés) con
> todo el contexto: qué construimos, reglas, contratos, estado y qué le toca a cada persona.
> - **opencode** lo lee solo.
> - **Claude Code** lo lee a través de `CLAUDE.md`, que lo importa.

## Dónde está todo

| Qué | Dónde |
|---|---|
| Repo | GitHub **privado** `https://github.com/ucr2205/repo-hackhaton`, rama `main` (pide acceso al líder) |
| Contexto para la IA | `AGENTS.md` en la raíz del repo (y `CLAUDE.md`, que lo importa) |
| Este vault | Hoy en la carpeta `NiceBank-Vault` del líder; se va a copiar al repo en **`vault/`** y desde ahí se abre en Obsidian |
| Decisiones técnicas | `docs/adr/0001`…`0005` (resumen en [[Decisiones (ADR)]]) |

## Primer uso (10 minutos)

1. Clona el repo y prepara tu máquina ([[Levantar el proyecto]]).
2. Abre una terminal **en la raíz del repo** y arranca tu herramienta: `opencode` o `claude`.
3. Primer mensaje recomendado:
   > *"Lee AGENTS.md y resume en 5 puntos: qué construimos, las reglas duras, mi workstream (soy P2/P3/P4) y qué
   > archivos debería tocar y cuáles no."*
4. Compara su resumen con tu nota personal ([[Persona 2 - Datos]], [[Persona 3 - IA y ML]],
   [[Persona 4 - Evaluación y pitch]]). Si algo no coincide, avísale al líder.

## Buenas prácticas

| Haz | Evita |
|---|---|
| Pedir primero **un plan**, revisarlo y luego pedir que lo ejecute | Pedir "haz todo el módulo" en un solo mensaje |
| Pedir que corra `make smoke` / `make test` antes de terminar | Aceptar cambios sin probarlos |
| Decir qué carpetas **no** debe tocar | Dejar que cambie contratos por su cuenta |
| Recordarle: inglés en el repo, Poetry, sin datos en git | Instalar con `pip install` |
| Pedir commits con opencode al final de cada bloque | Commits gigantes al final del día |

## Plantilla de pedido

```text
Contexto: soy P<n>. Lee AGENTS.md y <archivos relevantes>.
Objetivo: <qué quiero lograr, en una frase>.
Restricciones: no toques <carpetas>; respeta el contrato <Cx>; Poetry; inglés en el repo.
Entregable: <archivos> + cómo probarlo.
Primero muéstrame el plan; no escribas código hasta que lo apruebe.
```

## Commits

Los commits se hacen **siempre con opencode** (no con `git commit` a mano ni desde Claude Code):
*"crea commits atómicos Conventional Commits en inglés para mis cambios; no hagas push; no incluyas data/, .env,
team/ ni resultados; no agregues líneas Co-Authored-By ni ninguna atribución a IA"*.
Formato: `feat(etl): add pandera contract for complaints`. Luego avisa al líder para revisión.

> [!warning] Sin atribución a IA
> Los mensajes de commit **no** llevan líneas tipo `Co-Authored-By: <asistente>` ni "Generated with…". Si tu
> herramienta las agrega sola, pídele que no lo haga (los commits más recientes del repo ya van sin ellas).

### opencode sin interacción (cuando otra IA le pide el commit)

La configuración global de opencode **pide aprobación** para cada comando, así que un `opencode run` lanzado por
otro asistente se queda esperando para siempre. La solución es darle, **solo para esa corrida**, un archivo de
configuración que permita únicamente comandos de git de lectura y commit:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "permission": {
    "edit": "deny",
    "webfetch": "deny",
    "bash": {
      "*": "deny",
      "git status*": "allow",
      "git diff*": "allow",
      "git log*": "allow",
      "git add *": "allow",
      "git commit *": "allow",
      "git push": "deny",
      "git push *": "deny"
    }
  }
}
```

Guárdalo **fuera del repo** (por ejemplo `opencode-git-only.json` en una carpeta temporal) y úsalo así:

```powershell
$env:OPENCODE_CONFIG = "C:\ruta\a\opencode-git-only.json"
opencode run "Crea estos commits... (subject, paths y body de cada uno). Sin push. Sin atribución a IA."
```

Así opencode no puede editar archivos, navegar ni hacer push: solo mirar el estado, preparar y commitear. El
`push` se hace aparte, después de revisar los commits.

> [!warning] Datos sensibles
> Nunca pegues en el chat de la IA claves de AWS, contraseñas reales ni datos de clientes sin enmascarar.
