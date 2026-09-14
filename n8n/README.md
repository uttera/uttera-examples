# Uttera in n8n

*[Versión en castellano](README.es.md)*

Two routes. The second one installs nothing.

## The node

[`nodo/`](nodo/) is a community node package: `n8n-nodes-uttera`. It gives you
transcribe, summarise, translate and text-to-speech as operations of one node,
with the credential stored in n8n instead of pasted into every request.

```bash
cd nodo && npm install && npm run build
```

On self-hosted n8n it installs from **Settings → Community nodes**, or by
dropping the package into `~/.n8n/nodes`.

Two details that are there for a reason:

- **The timeout is two hours.** n8n's default cuts off long recordings that were
  going perfectly.
- **"Continue on fail" works per item.** When you process a folder of recordings
  there is always a corrupt one, and it must not take the batch down with it.

## Ready-made workflows

[`flujos/`](flujos/) import from **Workflows → Import from file** and use the
stock HTTP Request node. They work on n8n cloud too.

| Workflow | What it does |
|---|---|
| `grabaciones-a-resumen.json` | Watches a folder every 15 minutes, sends each recording to be summarised, and pulls out summary, transcript and speakers |
| `texto-a-voz.json` | Turns a text into an audio file |

The credential is an n8n **Header Auth**: name `Authorization`, value
`Bearer sk-echo-...`.

The first one is the case people ask for most: the PBX is already recording, and
all that is missing is somebody reading those recordings. No dialplan changes.
