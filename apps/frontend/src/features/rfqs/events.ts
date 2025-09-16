'use client';

import type { RFQ } from '@/types/rfqs';

const target = typeof window !== 'undefined' ? (window as unknown as EventTarget) : new EventTarget();

export function emitRfqUpdated(updated: RFQ) {
    const evt = new CustomEvent<RFQ>('rfq-updated', { detail: updated });
    target.dispatchEvent(evt);
}

export function onRfqUpdated(handler: (updated: RFQ) => void) {
    const listener = (e: Event) => {
        const ce = e as CustomEvent<RFQ>;
        handler(ce.detail);
    };
    target.addEventListener('rfq-updated', listener as EventListener);
    return () => target.removeEventListener('rfq-updated', listener as EventListener);
}


