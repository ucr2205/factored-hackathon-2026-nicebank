# Preguntas frecuentes — disputas de tarjeta

> Contenido de ejemplo creado por el equipo para el hackathon a partir de `policies/disputes.yaml` (v0.2.0). No es la política de un banco real.

## ¿Qué puedo hacer con el asistente?
<!-- covers: policy:rule:SCOPE-01 -->
Puedes reclamar un cargo de tu tarjeta que no reconoces, un cobro duplicado, un monto incorrecto, una compra que no recibiste o un retiro en cajero que no te entregó el efectivo. También puedes reportar una tarjeta perdida o robada. Para préstamos, inversiones o cambios de datos, usa la app o una sucursal.

## ¿Cuánto tiempo tengo para disputar un cargo?
<!-- covers: policy:dispute_type:unrecognized_charge policy:dispute_type:atm_cash_not_dispensed -->
Hasta 120 días desde la fecha del movimiento. Para un retiro en cajero que no entregó el dinero, hasta 60 días. Si el movimiento es más antiguo, el asistente pasa tu caso a un especialista.

## ¿El asistente abre la disputa solo?
<!-- covers: policy:globals -->
Busca el movimiento en tus registros, te muestra lo que encontró y te pide confirmación. Solo después de que confirmes abre el caso, y verifica que haya quedado registrado.

## ¿Hasta qué monto lo resuelve el asistente?
<!-- covers: policy:dispute_type:unrecognized_charge policy:dispute_type:wrong_amount policy:dispute_type:duplicate_charge policy:dispute_type:not_received policy:dispute_type:atm_cash_not_dispensed -->
Abre el caso automáticamente hasta 500 USD en cargos no reconocidos o con monto incorrecto, 1.000 USD en cargos duplicados y 300 USD en compras no recibidas o retiros en cajero. Por encima de esos montos, tu caso pasa a un especialista. Los montos se comparan en dólares con la tasa de cambio del día del movimiento.

## Me robaron o perdí la tarjeta, ¿qué hago?
<!-- covers: policy:dispute_type:card_lost_stolen -->
Escríbele al asistente. Te propondrá bloquear la tarjeta y pasará tu caso al equipo de fraude. Para bloquearla te pedirá el código de tu app autenticadora.

## Veo un cargo que ya fue revertido, ¿tengo que reclamar?
<!-- covers: policy:explain:EXPLAIN-REVERSED -->
No. Si el cargo ya fue revertido, el dinero volvió a tu cuenta y no hace falta abrir una disputa.

## La compra que no hice aparece como rechazada, ¿me cobraron?
<!-- covers: policy:explain:EXPLAIN-DECLINED-FRAUD policy:explain:EXPLAIN-DECLINED -->
No se te cobró nada. Pero si no fuiste tú, alguien pudo intentar usar tu tarjeta: el asistente te propondrá bloquearla y pasará el caso al equipo de fraude.

## El cobro todavía figura como pendiente, ¿puedo disputarlo?
<!-- covers: policy:explain:EXPLAIN-PENDING -->
Si reclamas un monto incorrecto, una compra no recibida o un cajero que no entregó el efectivo, espera a que el cargo se confirme: un cargo pendiente todavía puede cambiar o desaparecer. Si no reconoces el cargo, sí puedes reclamarlo aunque esté pendiente.

## ¿Qué pasa si ya abrí una disputa por ese mismo movimiento?
<!-- covers: policy:rule:DISP-DUPCASE-01 -->
El asistente te informa el número del caso existente y no abre otro.

## ¿Qué datos necesita el asistente para encontrar el movimiento?
<!-- covers: policy:rule:CLARIFY-NOTFOUND policy:rule:CLARIFY-MULTI policy:rule:ESC-CLARIFY-LIMIT -->
Ayuda mucho indicar el monto y la fecha, o el comercio. Si hay varios movimientos parecidos, te mostrará hasta 5 para que elijas. Si después de 2 intentos no logra identificarlo, pasa el caso a un especialista.

## ¿El asistente me puede devolver el dinero o hacer una transferencia?
<!-- covers: policy:globals -->
No. El asistente nunca reembolsa dinero, nunca transfiere fondos y nunca muestra datos de otro cliente. Abre tu disputa o te deriva con un especialista, que es quien la resuelve.

## ¿Qué pasa si el sistema falla?
<!-- covers: policy:rule:ESC-TECH-01 -->
Si algo técnico no responde, el asistente pasa tu caso a un especialista para que no te quedes sin respuesta.

## ¿Dónde veo el estado de mis disputas?
En la sección «Mis disputas» de la app ves cada disputa abierta y cada caso con un especialista, con su estado. Cuando un especialista cierra tu caso, ahí ves el resultado y su explicación.

## ¿Cuánto dura la conversación?
<!-- covers: policy:globals -->
La conversación se cierra después de 15 minutos sin actividad. Puedes empezar una nueva cuando quieras.
