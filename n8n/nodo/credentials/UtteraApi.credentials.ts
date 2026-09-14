import type {
	IAuthenticateGeneric,
	ICredentialTestRequest,
	ICredentialType,
	INodeProperties,
} from 'n8n-workflow';

export class UtteraApi implements ICredentialType {
	name = 'utteraApi';

	displayName = 'Uttera API';

	documentationUrl = 'https://app.uttera.ai/docs/conectores';

	properties: INodeProperties[] = [
		{
			displayName: 'API Key',
			name: 'apiKey',
			type: 'string',
			typeOptions: { password: true },
			default: '',
			required: true,
			description: 'La clave que empieza por sk-echo-. Se crea en tu cuenta de Uttera',
		},
		{
			displayName: 'URL base',
			name: 'baseUrl',
			type: 'string',
			default: 'https://api.uttera.ai',
			description:
				'Cámbialo solo si tienes una instalación propia de los motores. Para el servicio de Uttera, déjalo como está',
		},
	];

	authenticate: IAuthenticateGeneric = {
		type: 'generic',
		properties: {
			headers: {
				Authorization: '=Bearer {{$credentials.apiKey}}',
			},
		},
	};

	// n8n prueba la credencial nada más guardarla. Se usa /v1/audio/voices y no
	// /health: /health es público y respondería 200 con una clave inválida, que
	// es justo el fallo que el botón «probar» tiene que cazar.
	test: ICredentialTestRequest = {
		request: {
			baseURL: '={{$credentials.baseUrl}}',
			url: '/v1/audio/voices',
		},
	};
}
