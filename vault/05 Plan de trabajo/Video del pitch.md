---
tags: [entrega, pitch, video]
estado: listo
dueño: Líder
---

# Video del pitch

> [!tip] En simple
> El video de la entrega (máximo 3 minutos, lo pide la hackathon) está en la carpeta `video/` del repo. Es un tráiler
> estilo lanzamiento de Apple hecho con **HyperFrames** (HTML + animaciones GSAP que se renderizan a MP4). La voz está
> en **inglés**; la app se ve de verdad, en español y portugués, con burbujas que traducen al inglés lo que dice el chat.

## Qué cuenta (2:50)

1. **Why**: una notificación de un cobro que no reconoces; 40 % de las quejas son disputas de tarjeta, 15 días cada
   una, 1 de cada 5 fuera de plazo.
2. **Título**: "What if it took a minute? Meet NiceBank." y la URL `hackathon.evon.solutions`.
3. **What** (tomas reales de la app): disputa verificada; cobro revertido explicado sin abrir caso; intento rechazado,
   bloqueo con código 2FA en la ventana sobre el chat; portugués e intento de manipulación bloqueado; el especialista
   recibe el caso completo (consola en portugués, identidad revelada solo al tomar el caso, auditoría); el correo
   que recibe el cliente (buzón de prueba, ES y PT); panel del supervisor.
4. **How** (~10 %): "AI proposes. Code decides." y el stack con su porqué; una traza real en Jaeger con cada paso
   y la regla de la política.
5. **Resultados** (evaluación v2 del 4 oct): 86,7 % correcto vs 5,8 % del proceso actual, 0 resultados inseguros,
   26/26 manipulaciones bloqueadas, < 1 s por respuesta.
6. **Cierre**: logo, lema y URL.

## Cómo está hecho

- **Voz**: Kokoro (voz `af_sky`), generada **en la PC**, sin API ni nube. Una frase por archivo para sincronizar
  cada animación con lo que se dice.
- **Tomas**: un script de Playwright maneja la app local; los logins y el código 2FA los escribe una persona (el
  asistente de IA no maneja contraseñas). Se graban 6 escenas y se cortan con los tiempos que guarda el script.
- **Música**: compuesta con código (síntesis en Python), sin samples ni licencias, alineada con las escenas.
- **Montaje**: `node tools/build.mjs` arma la línea de tiempo; `npx hyperframes render` produce el MP4.
- Detalle y comandos: `video/README.md`.

## Entregables

- Video final: `NiceBank-video-pitch.mp4` (en Descargas del líder; los MP4 no van al repo).
- Miniatura y textos para YouTube: `video/thumbnail/nicebank-thumbnail.png` y `video/YOUTUBE.md` (título,
  descripción y capítulos).

## Lecciones

- Las animaciones deben declarar inicio y fin (`fromTo`): HyperFrames renderiza en paralelo y una animación relativa
  hace parpadear el zoom. Lo que aparece más tarde debe empezar oculto por CSS.
- Para grabar, el backend usa Mailpit **sin** `MAIL_REDIRECT_TO`; si no, los correos de prueba muestran la dirección
  real del líder.

## Pendiente

- Subirlo a YouTube y poner el link en el correo de entrega.
