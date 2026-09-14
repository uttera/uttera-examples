// Uttera through the official OpenAI SDK for Node. Only baseURL and apiKey change.
//
//     npm install openai
//     export UTTERA_API_KEY=sk-echo-...
//     node node.mjs
import OpenAI from "openai";
import fs from "node:fs";

const client = new OpenAI({
  apiKey: process.env.UTTERA_API_KEY,
  baseURL: (process.env.UTTERA_API ?? "https://api.uttera.ai") + "/v1",
  // Uttera holds the connection for up to 7200 s so long recordings finish.
  timeout: 7_200_000,
});

const speech = await client.audio.speech.create({
  model: "tts-1",
  voice: "nova",
  input: "Your order ships tomorrow.",
});
fs.writeFileSync("out.mp3", Buffer.from(await speech.arrayBuffer()));
console.log("wrote out.mp3");

const text = await client.audio.transcriptions.create({
  model: "whisper-1",
  file: fs.createReadStream("out.mp3"),
  response_format: "text",
});
console.log("transcript:", String(text).trim());
