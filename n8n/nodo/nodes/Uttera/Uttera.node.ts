import type {
	IExecuteFunctions,
	INodeExecutionData,
	INodeType,
	INodeTypeDescription,
	IDataObject,
} from 'n8n-workflow';
import { NodeOperationError, NodeConnectionTypes } from 'n8n-workflow';

export class Uttera implements INodeType {
	description: INodeTypeDescription = {
		displayName: 'Uttera',
		name: 'uttera',
		icon: 'file:uttera.png',
		group: ['transform'],
		version: 1,
		subtitle: '={{$parameter["operation"]}}',
		description: 'Transcribe, summarise and translate audio, turn text into speech, and generate sound effects and music',
		defaults: { name: 'Uttera' },
		inputs: [NodeConnectionTypes.Main],
		outputs: [NodeConnectionTypes.Main],
		credentials: [{ name: 'utteraApi', required: true }],
		properties: [
			{
				displayName: 'Operation',
				name: 'operation',
				type: 'options',
				noDataExpression: true,
				default: 'transcribe',
				options: [
					{ name: 'Transcribe Audio', value: 'transcribe', action: 'Transcribe an audio file' },
					{ name: 'Summarise Recording', value: 'summarize', action: 'Summarise a recording' },
					{ name: 'Translate Recording', value: 'translate', action: 'Translate a recording' },
					{ name: 'Text to Speech', value: 'speech', action: 'Turn text into speech' },
					{ name: 'Sound Effect', value: 'soundEffect', action: 'Generate a sound effect' },
					{ name: 'Music', value: 'music', action: 'Generate a piece of music' },
				],
			},
			{
				displayName: 'Description',
				name: 'prompt',
				type: 'string',
				typeOptions: { rows: 2 },
				default: '',
				required: true,
				description: 'What you want to hear. English works noticeably better',
				displayOptions: { show: { operation: ['soundEffect', 'music'] } },
			},
			{
				displayName: 'Seconds',
				name: 'seconds',
				type: 'number',
				default: 10,
				description: 'Up to 30 for a sound effect, up to 380 for music',
				displayOptions: { show: { operation: ['soundEffect', 'music'] } },
			},
			{
				// El precio de la musica es duracion POR pasos, asi que este campo
				// cuesta dinero y el texto lo dice en vez de esconderlo.
				displayName: 'Quality (Steps)',
				name: 'steps',
				type: 'number',
				default: 32,
				description: 'From 32 to 128. Price is length multiplied by steps, so 128 costs four times 32',
				displayOptions: { show: { operation: ['music'] } },
			},
			{
				displayName: 'Seed',
				name: 'seed',
				type: 'number',
				default: -1,
				description: 'Same description and same seed give the same audio. -1 picks one at random',
				displayOptions: { show: { operation: ['soundEffect', 'music'] } },
			},
			{
				displayName: 'Input Binary Field',
				name: 'binaryProperty',
				type: 'string',
				default: 'data',
				required: true,
				description: 'Name of the binary field holding the audio',
				displayOptions: { show: { operation: ['transcribe', 'summarize', 'translate'] } },
			},
			{
				displayName: 'Language',
				name: 'language',
				type: 'string',
				default: '',
				placeholder: 'es',
				description: 'ISO code. Leave empty to detect it automatically',
				displayOptions: { show: { operation: ['transcribe'] } },
			},
			{
				displayName: 'Voice Analysis',
				name: 'extras',
				type: 'multiOptions',
				default: [],
				description: 'Requested in the SAME call, so the audio is uploaded only once',
				options: [
					{ name: 'Tone', value: 'sentiment' },
					{ name: 'Speaker Profile', value: 'profile' },
					{ name: 'Who Speaks and When', value: 'diarize' },
				],
				displayOptions: { show: { operation: ['transcribe'] } },
			},
			{
				displayName: 'Target Language',
				name: 'target',
				type: 'string',
				default: 'en',
				required: true,
				displayOptions: { show: { operation: ['translate'] } },
			},
			{
				displayName: 'Text',
				name: 'text',
				type: 'string',
				typeOptions: { rows: 3 },
				default: '',
				required: true,
				displayOptions: { show: { operation: ['speech'] } },
			},
			{
				displayName: 'Voice',
				name: 'voice',
				type: 'string',
				default: 'nova',
				displayOptions: { show: { operation: ['speech'] } },
			},
			{
				displayName: 'Format',
				name: 'format',
				type: 'options',
				default: 'mp3',
				options: ['mp3', 'wav', 'opus', 'flac'].map((f) => ({ name: f, value: f })),
				displayOptions: { show: { operation: ['speech'] } },
			},
		],
	};

	async execute(this: IExecuteFunctions): Promise<INodeExecutionData[][]> {
		const items = this.getInputData();
		const salida: INodeExecutionData[] = [];
		const cred = await this.getCredentials('utteraApi');
		const base = ((cred.baseUrl as string) || 'https://api.uttera.ai').replace(/\/$/, '');

		for (let i = 0; i < items.length; i++) {
			const op = this.getNodeParameter('operation', i) as string;
			try {
				if (op === 'soundEffect' || op === 'music') {
					// Los dos devuelven WAV y se cobran distinto; lo unico que
					// comparten es que la descripcion va en ingles al motor, asi que
					// se pide la traduccion al servicio.
					const seed = this.getNodeParameter('seed', i) as number;
					const segundos = this.getNodeParameter('seconds', i) as number;
					const esMusica = op === 'music';
					// Desde el 2026-09-21 los dos motores piden LO MISMO
					// (`prompt`, `seconds`, `translate`); antes sonidos los
					// pedia en castellano y habia que escribir dos cuerpos.
					const cuerpo: IDataObject = {
						prompt: this.getNodeParameter('prompt', i) as string,
						seconds: segundos,
						translate: true,
					};
					if (esMusica) cuerpo.steps = this.getNodeParameter('steps', i) as number;
					if (seed >= 0) cuerpo.seed = seed;

					const generado = (await this.helpers.httpRequestWithAuthentication.call(
						this,
						'utteraApi',
						{
							method: 'POST',
							url: `${base}/v1/audio/${esMusica ? 'music' : 'sfx'}`,
							body: cuerpo,
							json: true,
							encoding: 'arraybuffer',
							returnFullResponse: false,
							// La primera peticion del dia carga el modelo y tarda mucho
							// mas que las siguientes.
							timeout: 900_000,
						},
					)) as Buffer;
					salida.push({
						json: {},
						binary: {
							data: await this.helpers.prepareBinaryData(
								Buffer.from(generado),
								esMusica ? 'music.wav' : 'sound.wav',
								'audio/wav',
							),
						},
						pairedItem: { item: i },
					});
					continue;
				}

				if (op === 'speech') {
					const formato = this.getNodeParameter('format', i) as string;
					const audio = (await this.helpers.httpRequestWithAuthentication.call(this, 'utteraApi', {
						method: 'POST',
						url: `${base}/v1/audio/speech`,
						body: {
							model: 'tts-1',
							voice: this.getNodeParameter('voice', i) as string,
							input: this.getNodeParameter('text', i) as string,
							response_format: formato,
						},
						json: true,
						encoding: 'arraybuffer',
						returnFullResponse: false,
					})) as Buffer;
					salida.push({
						json: {},
						binary: {
							data: await this.helpers.prepareBinaryData(
								Buffer.from(audio),
								`voz.${formato}`,
								`audio/${formato}`,
							),
						},
						pairedItem: { item: i },
					});
					continue;
				}

				// Las tres operaciones sobre audio mandan el fichero igual: multipart
				// con el binario que venga del nodo anterior, sin volcarlo a disco.
				const campo = this.getNodeParameter('binaryProperty', i) as string;
				const meta = this.helpers.assertBinaryData(i, campo);
				const contenido = await this.helpers.getBinaryDataBuffer(i, campo);

				let url: string;
				const form = new FormData();
				form.append(
					'file',
					new Blob([new Uint8Array(contenido)], { type: meta.mimeType }),
					meta.fileName || 'audio',
				);

				if (op === 'transcribe') {
					const extras = this.getNodeParameter('extras', i) as string[];
					const idioma = this.getNodeParameter('language', i) as string;
					form.append('model', 'whisper-1');
					if (idioma) form.append('language', idioma);
					url = `${base}/v1/audio/transcriptions`;
					if (extras.length) url += `?extras=${extras.join(',')}`;
				} else if (op === 'summarize') {
					url = `${base}/v1/summarize`;
				} else {
					const destino = this.getNodeParameter('target', i) as string;
					url = `${base}/v1/translate?target=${encodeURIComponent(destino)}&response=text`;
				}

				const r = (await this.helpers.httpRequestWithAuthentication.call(this, 'utteraApi', {
					method: 'POST',
					url,
					body: form,
					// ⚠ Dos horas. El valor por defecto de n8n corta trabajos largos que
					// iban perfectamente: una grabación de una hora tarda en subir más de
					// lo que cualquier valor por defecto tolera.
					timeout: 7_200_000,
				})) as IDataObject;

				salida.push({ json: r, pairedItem: { item: i } });
			} catch (error) {
				// Con «continuar en caso de error» activado, un fichero que falle no
				// tumba el lote entero: es lo normal al procesar una carpeta de
				// grabaciones, donde siempre hay alguna corrupta.
				if (this.continueOnFail()) {
					salida.push({ json: { error: (error as Error).message }, pairedItem: { item: i } });
					continue;
				}
				throw new NodeOperationError(this.getNode(), error as Error, { itemIndex: i });
			}
		}

		return [salida];
	}
}
