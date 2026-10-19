import type { EndpointConfigEntry } from './models';

export type OrderDemoControls = {
    /** Discard exactly one successful order-creation response, after the server processes it. */
    dropNextCreateResponse: () => void;
};

declare global {
    interface Window {
        orderDemo?: OrderDemoControls;
    }
}

let dropNext = false;

if (typeof window !== 'undefined') {
    window.orderDemo = Object.freeze({
        dropNextCreateResponse: () => {
            dropNext = true;
            console.info('[order-demo] Armed: the next successful order creation response will be discarded.');
        },
    });
}

/** Called only after the transport has received and validated a successful response. */
export const consumeOrderCreateResponseLoss = (config: EndpointConfigEntry): boolean => {
    if (!dropNext || config.service !== 'order' || config.verb !== 'POST' || config.url !== '/orders') {
        return false;
    }
    dropNext = false;
    console.info('[order-demo] Creation succeeded; response deliberately discarded. The UI must retry with the same idempotency key.');
    return true;
};
