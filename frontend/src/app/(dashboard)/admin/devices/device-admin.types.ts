export type FeedbackState = { type: "ok" | "error"; text: string } | null;

export type KeyQueryState = "idle" | "loading" | "loaded" | "unavailable" | "error";

export type InitialKeyDraft = {
    key_id: string;
    algorithm: string;
    secret: string;
};

export type DeviceTestEventResult = {
    idempotency_key: string;
    payload: unknown;
    response: {
        event_id: number;
        ingest_status: string;
    };
};

export type GuideContext = {
    deviceId: string;
    keyId: string;
    algorithm: string;
    secret: string | null;
};

export const DEFAULT_GUIDE_ALGORITHM = "HMAC_SHA256";

export function normalizeGuideAlgorithm(value: string | null | undefined): string {
    const normalized = value?.trim().toUpperCase();
    return normalized || DEFAULT_GUIDE_ALGORITHM;
}
