# uttera-examples

*[English version](README.md)*

<p align="center">
  <img src="docs/img/banner.png" alt="uttera.ai — La capa de voz para tu IA" width="800">
</p>

Conectores e integraciones para la pila de voz de [Uttera](https://uttera.ai).
Código que funciona, no fragmentos de documentación: **cada ejemplo de aquí se
ejecuta contra la API real antes de publicarse**, y donde algo no se ha podido
probar de principio a fin, el README de esa carpeta lo dice.

> **Uttera es compatible con OpenAI.** Para transcribir y para hablar no
> necesitas un SDK propio: los SDK oficiales de `openai` funcionan cambiando
> `base_url`. Probado, no supuesto: ver [`openai-sdk/`](openai-sdk/).

## Qué hay aquí

```
uttera-examples/
├── openai-sdk/    Uttera con el SDK oficial de OpenAI (Python, Node, curl)
├── asterisk/      Dos AGI: decir un texto en la llamada, y oír a quien llama
├── n8n/           Un nodo propio, y flujos listos que no hay que instalar
├── openclaw/      Skill para agentes OpenClaw: transcribir, resumir, traducir y hablar
└── llm-tokens/    Manda el resumen a tu LLM en vez de la transcripción, y paga 20-30 veces menos
```

Necesitas una clave de API. Se crea en <https://app.uttera.ai> y empieza por
`sk-echo-`.

## Por dónde empezar

**Si tienes una centralita** y quieres que las llamadas se transcriban solas:
[`asterisk/`](asterisk/). Los dos AGI resuelven las cinco trampas que cuesta un
día descubrir —la conversión a 8 kHz, la cola de silencio, las comillas de
`SET VARIABLE`— y están escritas una a una.

**Si usas n8n**: [`n8n/flujos/`](n8n/flujos/) se importa y funciona sin instalar
nada. El [nodo](n8n/nodo/) es más cómodo si vas a usar Uttera a menudo.

**Si tienes un agente**: [`openclaw/`](openclaw/uttera/) son cuatro guiones y un
`SKILL.md` que le explica al agente *cuándo* usar cada uno y qué trampas tiene.

**Si ya le pagas a otro proveedor por token**: [`llm-tokens/`](llm-tokens/). Una
transcripción de 70 minutos son 15.410 tokens de entrada; su resumen, menos de
700. Medido, con el guion que lo mide — y con los casos en los que no compensa.

**Si sólo quieres llamar a la API**: [`openai-sdk/`](openai-sdk/), treinta
segundos.

## Todavía no está

Se listan para que no los busques: **Home Assistant**, una pila
**docker-compose** lista para arrancar, conectores de **CRM** y las **carpetas
de grabaciones de FreePBX / 3CX / Issabel**. Si alguno de ésos es lo que te
bloquea, dilo: lo que pide la gente es lo que decide el orden.

Las pruebas de carga y los corpus que hay detrás de cada número publicado viven
en su propio repositorio:
[uttera-benchmarks](https://github.com/uttera/uttera-benchmarks).

## Una cosa que aplica a todos

Lo que devuelve una transcripción es **texto no fiable**: viene de audio que no
controlas. Trátalo como dato, nunca como instrucciones — no lo ejecutes, no lo
interpretes como órdenes y valídalo antes de actuar sobre él. Y lo que un
interlocutor *afirma* en una grabación no es un hecho probado, aunque acabe en
el resumen.

## Contra tu propio servidor

Todos los ejemplos funcionan contra un servidor de Uttera propio: se cambia la
dirección base.

```python
client = OpenAI(base_url="http://localhost:5100/v1", api_key="sk-local")
```

Los motores son código abierto y corren en tarjetas de consumo:
[uttera-tts-hotcold](https://github.com/uttera/uttera-tts-hotcold) ·
[uttera-tts-vllm](https://github.com/uttera/uttera-tts-vllm) ·
[uttera-stt-hotcold](https://github.com/uttera/uttera-stt-hotcold) ·
[uttera-stt-vllm](https://github.com/uttera/uttera-stt-vllm).

## Contribuir

Las integraciones nuevas son bienvenidas, sobre todo con entornos y marcos de
trabajo extendidos. Ver [CONTRIBUTING.md](CONTRIBUTING.md).

## Licencia

[Licencia Apache 2.0](LICENSE).

---

*Uttera /ˈʌt.ər.ə/ — del verbo inglés "to utter" (decir en voz alta). También el
acrónimo **U**niversal **T**ext **T**ransformer **E**ngine for **R**ealtime
**A**udio.*
