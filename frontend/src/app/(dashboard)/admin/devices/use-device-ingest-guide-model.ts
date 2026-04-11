"use client";

import { useMemo } from "react";
import { ManagedDeviceDetail } from "@/types/api";
import { DEFAULT_GUIDE_ALGORITHM, GuideContext, InitialKeyDraft, normalizeGuideAlgorithm } from "./device-admin.types";

type UseDeviceIngestGuideModelParams = {
    selectedDeviceDetail: ManagedDeviceDetail | null;
    rotateDeviceId: string;
    newDeviceId: string;
    rotateKeyId: string;
    rotateAlgorithm: string;
    rotateSecret: string;
    initialKeyDraft: InitialKeyDraft;
    guideContext: GuideContext | null;
};

const FALLBACK_GUIDE_SECRET = "demo-secret-8f6e9a5c3d2b1a09";

function hasRealGuideKey(context: GuideContext | null): context is GuideContext {
    return Boolean(context?.keyId.trim());
}

export function useDeviceIngestGuideModel({
    selectedDeviceDetail,
    rotateDeviceId,
    newDeviceId,
    rotateKeyId,
    rotateAlgorithm,
    rotateSecret,
    initialKeyDraft,
    guideContext,
}: UseDeviceIngestGuideModelParams) {
    return useMemo(() => {
        const selectedDetailContext = selectedDeviceDetail
            ? {
                deviceId: selectedDeviceDetail.device_id,
                keyId: selectedDeviceDetail.active_key?.key_id || "",
                algorithm: normalizeGuideAlgorithm(selectedDeviceDetail.active_key?.algorithm),
                secret: null,
            }
            : null;
        const rotateFormContext = rotateDeviceId.trim()
            ? {
                deviceId: rotateDeviceId.trim(),
                keyId: rotateKeyId.trim(),
                algorithm: normalizeGuideAlgorithm(rotateAlgorithm),
                secret: rotateSecret.trim() || null,
            }
            : null;
        const registerFormContext = newDeviceId.trim()
            ? {
                deviceId: newDeviceId.trim(),
                keyId: initialKeyDraft.key_id.trim(),
                algorithm: normalizeGuideAlgorithm(initialKeyDraft.algorithm),
                secret: initialKeyDraft.secret.trim() || null,
            }
            : null;

        const hasRotateDraftIntent = Boolean(
            rotateFormContext
            && (
                rotateFormContext.keyId
                || rotateFormContext.secret
            )
        );

        const hasRegisterDraftIntent = Boolean(
            registerFormContext
            && (
                registerFormContext.keyId
                || registerFormContext.secret
            )
        );

        const activeContext = hasRotateDraftIntent
            ? (hasRealGuideKey(rotateFormContext) ? rotateFormContext : null)
            : hasRegisterDraftIntent
                ? (hasRealGuideKey(registerFormContext) ? registerFormContext : null)
                : hasRealGuideKey(guideContext)
                    ? guideContext
                    : hasRealGuideKey(selectedDetailContext)
                        ? selectedDetailContext
                        : null;

        const guideDeviceId = activeContext?.deviceId || "demo-device-001";
        const resolvedGuideKeyId = activeContext?.keyId || "demo-key-v1";
        const resolvedGuideAlgorithm = activeContext?.algorithm || DEFAULT_GUIDE_ALGORITHM;
        const availableGuideSecret = activeContext?.secret?.trim() || "";
        const hasRealGuideSecret = Boolean(availableGuideSecret);
        const resolvedGuideSecret = availableGuideSecret || FALLBACK_GUIDE_SECRET;

        const guidePayloadExample = JSON.stringify(
            {
                version: "1.0.0",
                device_id: guideDeviceId,
                batch_id: "batch-demo-20260211-001",
                timestamp: "2026-02-11T10:00:00Z",
                sensor_payload: {
                    temperature_c: 4.2,
                    humidity_pct: 72,
                    status: "stable",
                },
                signature_envelope: {
                    algorithm: resolvedGuideAlgorithm,
                    key_id: resolvedGuideKeyId,
                    signature: "<HMAC_SHA256_HEX_SIGNATURE>",
                },
            },
            null,
            2
        );

        const guideRequestExample = `curl -X POST "http://localhost:18941/v1/events" \\
  -H "Content-Type: application/json" \\
  -H "Idempotency-Key: idem-${guideDeviceId}-001" \\
  -d '${JSON.stringify(
            {
                version: "1.0.0",
                device_id: guideDeviceId,
                batch_id: "batch-demo-20260211-001",
                timestamp: "2026-02-11T10:00:00Z",
                sensor_payload: {
                    temperature_c: 4.2,
                    humidity_pct: 72,
                    status: "stable",
                },
                signature_envelope: {
                    algorithm: resolvedGuideAlgorithm,
                    key_id: resolvedGuideKeyId,
                    signature: "<HMAC_SHA256_HEX_SIGNATURE>",
                },
            },
            null,
            2
        )}'`;

        return {
            guideDeviceId,
            resolvedGuideKeyId,
            resolvedGuideAlgorithm,
            availableGuideSecret,
            hasRealGuideSecret,
            resolvedGuideSecret,
            guidePayloadExample,
            guideRequestExample,
        };
    }, [
        guideContext,
        initialKeyDraft.algorithm,
        initialKeyDraft.key_id,
        initialKeyDraft.secret,
        newDeviceId,
        rotateAlgorithm,
        rotateDeviceId,
        rotateKeyId,
        rotateSecret,
        selectedDeviceDetail,
    ]);
}
