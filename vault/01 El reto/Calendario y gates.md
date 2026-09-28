---
tags: [reto, calendario]
---

# Calendario y gates

Un **gate** es un punto de control: nos juntamos 20 minutos, revisamos si se cumplió el criterio y decidimos
recortes si hace falta.

| Día | Fecha | Hito | Criterio para pasar |
|---|---|---|---|
| D1 | sáb 26 sep | Arranque | Máquinas listas, datos descargados ✅ |
| D2 | dom 27 sep | Contratos en borrador | [[Contratos entre módulos]] publicados |
| D3 | **lun 28 sep 18:00** | **Gate 1** | Flujo confirmado con datos (EDA de P2); contratos congelados |
| D5 | **mié 30 sep** | **Gate 2** | Caso normal de punta a punta con los componentes reales que ya existan |
| D7 | **vie 2 oct** | **Gate 3** | Todo implementado; primera evaluación completa |
| D8 | sáb 3 oct | Ajustes | Segunda evaluación; pruebas de carga |
| D9 | **dom 4 oct 20:00** | **Code freeze** | Evaluación final; ensayo del video |
| D10 | **lun 5 oct** | **Entrega** | Repo, link, slides, video → hackathon.admin@factored.ai |


## Reunión diaria (15 min, 9:00)

Cada uno responde tres cosas: ¿qué terminé?, ¿qué hago hoy?, ¿qué me bloquea? Plantilla: [[Reunión diaria]].

## Plan de recorte (si el D6 el caso normal no cierra)

1. Se quita el dashboard de Grafana.
2. La consola del agente queda solo con la cola de casos.
3. La RAG se limita a las políticas (sin FAQ).
