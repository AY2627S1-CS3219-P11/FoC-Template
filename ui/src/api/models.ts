export type FieldType = 'formData' | 'path' | 'query';

export type EndpointConfigEntry = {
    url: string;
    verb: 'DELETE' | 'GET' | 'PATCH' | 'POST' | 'PUT';
    fieldMap?: Record<string, FieldType>;
    keepalive?: boolean;
    retry?: boolean;
};

export type APIRequest = Record<string, unknown> | null;

export class CampusErrandsAPIError extends Error {
    status: number;
    data?: unknown;

    constructor(message: string, status: number, data?: unknown) {
        super(message);
        this.name = 'CampusErrandsAPIError';
        this.status = status;
        this.data = data;
    }
}

export class RetryableCampusErrandsAPIError extends CampusErrandsAPIError {}

export class RetryableNetworkError extends TypeError {
    constructor(error: TypeError) {
        super(error.message, { cause: error });
        this.name = error.name;
    }
}
