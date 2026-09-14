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
		icon: 'file:uttera.svg',
		group: ['transform'],
		version: 1,
		subtitle: '={{$parameter["operation"]}}',
		description: 'Transcribir, resumir, traducir audio y convertir texto en voz',
		defaults: { name: 'Uttera' },
		inputs: [NodeConnectionTypes.Main],
		outputs: [NodeConnectionTypes.Main],
		credentials: [{ name: 'utteraApi', required: true }],
		properties: [
			{
				displayName: 'Operación',
				name: 'operation',
				type: 'options',
				noDataExpression: true,
				default: 'transcribe',
				options: [
					{ name: 'Transcribir audio', value: 'transcribe', action: 'Transcribir un audio' },
					{ name: 'Resumir grabación', value: 'summarize', action: 'Resumir una grabacion' },
					{ name: 'Traducir grabación', value: 'translate', action: 'Traducir una grabacion' },
					{ name: 'Texto a voz', value: 'speech', action: 'Convertir texto en voz' },
				],
			},
			{
				displayName: 'Campo binario',
				name: 'binaryProperty',
				type: 'string',
				default: 'data',
				required: true,
				description: 'Nombre del campo binario que trae el audio',
				displayOptions: { show: { operation: ['transcribe', 'summarize', 'translate'] } },
			},
			{
				displayName: 'Idioma',
				name: 'language',
				type: 'string',
				default: '',
				placeholder: 'es',
				description: 'Código ISO. Vacío = se detecta solo',
				displayOptions: { show: { operation: ['transcribe'] } },
			},
			{
				displayName: 'Análisis de voz',
				name: 'extras',
				type: 'multiOptions',
				default: [],
				description: 'Se piden en la MISMA petición: el audio se sube una sola vez',
				options: [
					{ name: 'Tono', value: 'sentiment' },
					{ name: 'Perfil del hablante', value: 'profile' },
					{ name: 'Quién habla y cuándo', value: 'diarize' },
				],
				displayOptions: { show: { operation: ['transcribe'] } },
			},
			{
				displayName: 'Idioma destino',
				name: 'target',
				type: 'string',
				default: 'en',
				required: true,
				displayOptions: { show: { operation: ['translate'] } },
			},
			{
				displayName: 'Texto',
				name: 'text',
				type: 'string',
				typeOptions: { rows: 3 },
				default: '',
				required: true,
				displayOptions: { show: { operation: ['speech'] } },
			},
			{
				displayName: 'Voz',
				name: 'voice',
				type: 'string',
				default: 'nova',
				displayOptions: { show: { operation: ['speech'] } },
			},
			{
				displayName: 'Formato',
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
