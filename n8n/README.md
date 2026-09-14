# Uttera en n8n

Dos caminos. El segundo no necesita instalar nada.

## Nodo propio

[`nodo/`](nodo/) es un paquete de nodo comunitario: `n8n-nodes-uttera`. Da
transcribir, resumir, traducir y texto a voz como operaciones de un nodo, con la
credencial guardada en n8n en vez de suelta en cada petición.

```bash
cd nodo && npm install && npm run build
```

En n8n autoalojado se instala desde **Ajustes → Nodos de la comunidad**, o
copiando el paquete en `~/.n8n/nodes`.

Dos detalles que están ahí por una razón:

- **El tiempo de espera son dos horas.** El valor por defecto de n8n corta
  grabaciones largas que iban perfectamente.
- **«Continuar en caso de error» funciona por elemento.** Al procesar una
  carpeta de grabaciones siempre hay alguna corrupta, y no debe tumbar el lote.

## Flujos listos

[`flujos/`](flujos/) se importan desde **Flujos → Importar desde archivo** y
usan el nodo HTTP Request de serie. Funcionan también en n8n en la nube.

| Flujo | Qué hace |
|---|---|
| `grabaciones-a-resumen.json` | Mira una carpeta cada 15 minutos, manda cada grabación a resumir y saca resumen, transcripción e interlocutores |
| `texto-a-voz.json` | Convierte un texto en un fichero de audio |

La credencial es un **Header Auth** de n8n: nombre `Authorization`, valor
`Bearer sk-echo-...`.

El primero es el caso que más se pide: la centralita ya está grabando, y lo único
que falta es que alguien lea esas grabaciones. No hay que tocar el dialplan.
