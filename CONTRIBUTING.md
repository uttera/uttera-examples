# Contributing

## The one rule

**Nothing gets published here that hasn't been run.** Not a snippet copied from
the docs, not code written from memory. If an example can't be tested end to end
— an Asterisk dialplan, say, which needs a live PBX — then its README has to say
which part was tested and which part wasn't.

That rule is the whole point of this repository. A sample that doesn't run wastes
more of the reader's time than no sample at all.

## Practical

- Every directory carries its own `README.md`, including the traps you hit while
  building it. That's usually worth more than the code.
- Keep the credentials out. `UTTERA_API_KEY` comes from the environment, never
  from a file in the repository.
- Set the timeout to 7200 s wherever audio is uploaded. Library defaults cut off
  long recordings that were going perfectly, and it's the most common mistake
  when integrating.
- Handle errors by reading `error` first and falling back to `detail`: edge
  errors and engine errors don't have the same shape.

## Reporting something that doesn't work

Open an issue with the `X-Request-Id` of the failed request — every response
carries one. With it we can tell you exactly what happened; without it the
conversation starts by working out which request you mean.
