import { TraceEventContractPayload } from "@/types/api";

function normalizeDateTime(value: string): string {
    const normalized = value.trim();
    if (!normalized.includes("T")) {
        return normalized;
    }

    const hasExplicitTimezone = /Z$|[+-]\d{2}:\d{2}$/.test(normalized);
    const parseTarget = hasExplicitTimezone ? normalized : `${normalized}Z`;
    const date = new Date(parseTarget);
    if (Number.isNaN(date.getTime())) {
        return normalized;
    }

    const year = date.getUTCFullYear();
    const month = String(date.getUTCMonth() + 1).padStart(2, "0");
    const day = String(date.getUTCDate()).padStart(2, "0");
    const hour = String(date.getUTCHours()).padStart(2, "0");
    const minute = String(date.getUTCMinutes()).padStart(2, "0");
    const second = String(date.getUTCSeconds()).padStart(2, "0");
    const ms = date.getUTCMilliseconds();

    if (ms === 0) {
        return `${year}-${month}-${day}T${hour}:${minute}:${second}Z`;
    }

    const microseconds = `${String(ms).padStart(3, "0")}000`;
    return `${year}-${month}-${day}T${hour}:${minute}:${second}.${microseconds}Z`;
}

function canonicalizeValue(value: unknown): unknown {
    if (Array.isArray(value)) {
        return value.map((item) => canonicalizeValue(item));
    }

    if (value !== null && typeof value === "object") {
        const entries = Object.entries(value as Record<string, unknown>)
            .sort(([a], [b]) => a.localeCompare(b))
            .map(([key, item]) => [key, canonicalizeValue(item)] as const);
        return Object.fromEntries(entries);
    }

    if (typeof value === "string") {
        return normalizeDateTime(value);
    }

    return value;
}

function canonicalizePayload(payload: unknown): string {
    const compactJson = JSON.stringify(canonicalizeValue(payload));
    return compactJson.replace(/[\u007f-\uffff]/g, (char) => {
        const code = char.charCodeAt(0);
        return `\\u${code.toString(16).padStart(4, "0")}`;
    });
}

async function hmacSha256Hex(secret: string, message: string): Promise<string> {
    const encoder = new TextEncoder();
    const cryptoKey = await window.crypto.subtle.importKey(
        "raw",
        encoder.encode(secret),
        { name: "HMAC", hash: "SHA-256" },
        false,
        ["sign"]
    );
    const signature = await window.crypto.subtle.sign("HMAC", cryptoKey, encoder.encode(message));
    const bytes = new Uint8Array(signature);
    return Array.from(bytes)
        .map((byte) => byte.toString(16).padStart(2, "0"))
        .join("");
}

export async function signTraceEventPayload(payload: TraceEventContractPayload, secret: string): Promise<TraceEventContractPayload> {
    const signingPayload = {
        version: payload.version,
        device_id: payload.device_id,
        batch_id: payload.batch_id,
        timestamp: payload.timestamp,
        sensor_payload: payload.sensor_payload,
        signature_envelope: {
            algorithm: payload.signature_envelope.algorithm,
            key_id: payload.signature_envelope.key_id,
        },
    };

    const canonical = canonicalizePayload(signingPayload);
    const signature = await hmacSha256Hex(secret, canonical);
    return {
        ...payload,
        signature_envelope: {
            ...payload.signature_envelope,
            signature,
        },
    };
}

