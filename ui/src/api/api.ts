import type { APIRequest, APIService, EndpointConfigEntry } from './models';
import { CampusErrandsAPIError } from './models';
import { routes } from '../routes';

const apiUrls: Record<APIService, string> = {
    supplier: import.meta.env.VITE_SUPPLIER_API_URL || '/supplier-api',
    user: import.meta.env.VITE_USER_API_URL || '/user-api',
};
const PUBLIC_ROUTES = new Set<string>([routes.signIn]);
type RequestDetails = {
    init: RequestInit;
    url: string;
};

export type AuthenticatedRequestOptions = {
    onUnauthenticated?: () => void;
};

const appendQueryValue = (query: URLSearchParams, field: string, value: unknown): void => {
    if (!Array.isArray(value)) {
        query.append(field, String(value));
        return;
    }

    if (value.length === 0) {
        query.append(field, '');
        return;
    }

    value.forEach((item) => query.append(field, String(item)));
};

const buildRequest = (request: APIRequest, config: EndpointConfigEntry): RequestDetails => {
    let url = `${apiUrls[config.service].replace(/\/$/, '')}/${config.url.replace(/^\//, '')}`;
    const body: Record<string, unknown> = {};
    const query = new URLSearchParams();
    let formData: FormData | undefined;

    Object.entries(request ?? {}).forEach(([field, value]) => {
        if (value === undefined) return;
        const fieldType = config.fieldMap?.[field];

        if (fieldType === 'path') {
            url = url.replace(`:${field}`, encodeURIComponent(String(value)));
        } else if (fieldType === 'query' || (config.verb === 'GET' && !fieldType)) {
            appendQueryValue(query, field, value);
        } else if (fieldType === 'formData') {
            formData ??= new FormData();
            formData.append(field, value instanceof Blob ? value : String(value));
        } else {
            body[field] = value;
        }
    });

    const queryString = query.toString();
    if (queryString) {
        url += `${url.includes('?') ? '&' : '?'}${queryString}`;
    }

    const headers: Record<string, string> = {};
    const init: RequestInit = { method: config.verb, credentials: 'include', headers };
    if (config.keepalive) {
        init.keepalive = true;
    }
    if (formData) {
        init.body = formData;
    } else if (Object.keys(body).length > 0) {
        headers['Content-Type'] = 'application/json';
        init.body = JSON.stringify(body);
    }

    return { init, url };
};

const parseResponse = async <T>(response: Response): Promise<T> => {
    if (response.status === 204) {
        return null as T;
    }

    const contentType = response.headers?.get('content-type');
    if (!contentType) {
        return null as T;
    }
    if (contentType.includes('application/json')) {
        return (await response.json()) as T;
    }
    return (await response.text()) as T;
};

const getErrorMessage = (data: unknown, fallback: string): string => {
    if (typeof data === 'string') {
        return data;
    }
    if (!data || typeof data !== 'object') {
        return fallback;
    }

    const errorBody = data as { detail?: unknown; message?: unknown };
    if (typeof errorBody.message === 'string') {
        return errorBody.message;
    }
    if (typeof errorBody.detail === 'string') {
        return errorBody.detail;
    }

    return fallback;
};

const sendRequest = async <TResponse>({ init, url }: RequestDetails): Promise<TResponse> => {
    const response = await fetch(url, init);
    const data = await parseResponse<TResponse>(response);
    const contentType = response.headers?.get('content-type') ?? '';

    if (
        response.ok &&
        contentType.includes('text/html') &&
        typeof data === 'string' &&
        /<!doctype html|<html[\s>]/i.test(data)
    ) {
        throw new CampusErrandsAPIError('The API returned an unexpected HTML page.', 502);
    }

    if (!response.ok) {
        const message = getErrorMessage(data, response.statusText || 'Unknown error');
        throw new CampusErrandsAPIError(message, response.status, data);
    }

    return data;
};

export const makeCampusErrandsAPIRequest = async <TRequest extends APIRequest, TResponse>(
    request: TRequest,
    config: EndpointConfigEntry
): Promise<TResponse> => {
    return await sendRequest<TResponse>(buildRequest(request, config));
};

const redirectToSignIn = (): void => {
    if (!PUBLIC_ROUTES.has(window.location.pathname)) {
        window.location.replace(routes.signIn);
    }
};

export const makeAuthenticatedCampusErrandsAPIRequest = async <TRequest extends APIRequest, TResponse>(
    request: TRequest,
    config: EndpointConfigEntry,
    options: AuthenticatedRequestOptions = {}
): Promise<TResponse> => {
    try {
        return await makeCampusErrandsAPIRequest<TRequest, TResponse>(request, config);
    } catch (error) {
        if (error instanceof CampusErrandsAPIError && error.status === 401) {
            (options.onUnauthenticated ?? redirectToSignIn)();
        }
        throw error;
    }
};
