# Uttera + Asterisk

*[Versión en castellano](README.es.md)*

Two ways in, and the second one needs no change to your dialplan at all.

```
agi/           speak in a live call, and hear the caller
recordings/    transcribe the calls your PBX is already recording
```

## `recordings/` — start here

Your PBX is already writing `.wav` files somewhere. Point the script at that
folder and last week's calls are transcribed, without touching Asterisk. This is
the code we run in production. See [recordings/](recordings/).

## `agi/` — talking inside the call

Two AGI scripts: one speaks a text in the call, the other listens to the caller
and leaves what they said in a dialplan variable.

```
exten => 101,1,Answer()
 same => n,AGI(uttera-decir.agi,"How can I help you?")
 same => n,AGI(uttera-oir.agi,8,en)
 same => n,NoOp(The caller said: ${UTTERA_TEXTO})
```

### Installation

```bash
cp agi/uttera_agi.py /var/lib/asterisk/agi-bin/
chmod +x /var/lib/asterisk/agi-bin/uttera_agi.py
ln -s uttera_agi.py /var/lib/asterisk/agi-bin/uttera-decir.agi
ln -s uttera_agi.py /var/lib/asterisk/agi-bin/uttera-oir.agi
apt install sox
```

The key goes in the service environment, **never in the dialplan** — a key
written there ends up in your configuration backup, in version control and in
the output of `dialplan show`:

```
systemctl edit asterisk
[Service]
Environment=UTTERA_API_KEY=sk-echo-...
```

### What costs a day to find out

All of it is handled in the code. It is written down because it takes a day to
discover and five minutes to read.

**The audio conversion is not optional.** Uttera generates at 24 kHz and a phone
channel runs at 8 kHz. Hand Asterisk the WAV as it comes and it plays it at its
own rate: the voice comes out fast and high-pitched. `sox` converts to `.sln`,
raw PCM at 8 kHz, which is exactly what the channel wants.

**Add silence at the end.** Without a few tenths of tail (`pad 0 0.4`), Asterisk
clips the last syllable when it closes the file.

**`STREAM FILE` takes no extension.** Give it the base name and it picks the
format it finds.

**Whisper does not stay quiet when given silence.** It does not return an empty
string — it invents a sentence, usually something like "Thanks for watching",
because that is what its training data is full of. The AGI drops recordings under
2 KB before sending them: it saves you paying for a hallucination and, worse,
acting on it.

**The quoting in `SET VARIABLE` and `VERBOSE`.** The AGI parser splits on
spaces: unquoted text arrives truncated and the variable keeps only the first
word. A quote *inside* the text derails the rest of the line, so they are
replaced before sending.

**Telephony timeouts are not API timeouts.** Uttera holds the connection for up
to two hours for long jobs, but here there is a person with a phone to their ear:
these scripts give up after 30 seconds. If Uttera has not answered by then the
call is already ruined, and the thing to do is say so, not keep waiting.
