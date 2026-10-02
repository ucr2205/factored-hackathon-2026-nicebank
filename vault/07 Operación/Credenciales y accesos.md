---
tags: [operacion, credenciales]
---

# Credenciales y accesos

> [!warning] Solo entorno local
> Todos estos usuarios existen **solo** en el Keycloak de desarrollo de cada máquina. No son credenciales reales.
> El documento completo (con las claves TOTP de cada cliente) lo tiene el líder en PDF: *"NiceBank - Credenciales
> de prueba.pdf"* (en su carpeta de Descargas); pídeselo por el canal privado. Las claves de AWS, DeepSeek y del
> correo **nunca** van aquí: se comparten por el canal privado y viven solo en tu `.env`.

## Patrón de contraseñas

Todas siguen el patrón `Test-Only-<usuario>` (por ejemplo, `Test-Only-cliente01`).

| Usuarios | Rol | Para qué |
|---|---|---|
| `cliente01` … `cliente20` | cliente (con TOTP) | Demo y pruebas manuales; el bloqueo de tarjeta pide código |
| `agente01`, `agente02` | agente | Consola de casos escalados |
| `supervisor01` | supervisor | Consola + supervisión |
| `carga01` … `carga20` | cliente (**sin** TOTP) | Solo JMeter; no pueden hacer acciones de nivel 2 |

## Qué usuario usar en cada caso del demo

| Caso | Usuario | Qué hacer |
|---|---|---|
| Normal (ES) | `cliente01` | "No reconozco un cobro de hoy" o tocar **Streaming Music** |
| Duplicado (PT) | `cliente02` | "Me cobraram duas vezes no mercado" |
| Escalamiento + código | `cliente03` | Tocar **Electro Mundo Online** (1.450 USD, EE. UU.) → Confirmar → código |
| No soportado (PT) | cualquiera | "Quero um empréstimo" |
| Recuperar contraseña | `cliente20` | "¿Olvidaste tu contraseña?" → correo (en Mailpit, o en tu `MAIL_REDIRECT_TO` con servidor real) → código → nueva contraseña |
| Consola | `agente01` | Tomar el caso escalado, "Mostrar identidad", ver su auditoría y (con "Ver detalle técnico") la traza en Jaeger |
| Correos al cliente | cualquiera | Abrir una disputa y mirar el correo en Mailpit (http://localhost:8090/mail/) |

## Generar un código TOTP sin celular

```bash
poetry run python -c "import sys; sys.path.insert(0,'scripts'); from smoke_chat import totp; print(totp('nicebank-demo-otp-cliente03'))"
```

Si alguien cambió una contraseña con la recuperación: `docker compose up -d --force-recreate keycloak` restaura todo.
