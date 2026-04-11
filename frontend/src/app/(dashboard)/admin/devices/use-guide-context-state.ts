"use client";

import { useState } from "react";
import { ManagedDeviceDetail } from "@/types/api";
import { GuideContext, normalizeGuideAlgorithm } from "./device-admin.types";

type UseGuideContextStateParams = {
    selectedDeviceDetail: ManagedDeviceDetail | null;
};

type GuideContextInput = {
    deviceId: string;
    keyId: string;
    algorithm: string;
    secret: string | null;
};

export function useGuideContextState({ selectedDeviceDetail }: UseGuideContextStateParams) {
    const [guideContext, setGuideContext] = useState<GuideContext | null>(null);
    const [prevDetailRef, setPrevDetailRef] = useState<string>("");

    const currentHash = selectedDeviceDetail
        ? `${selectedDeviceDetail.device_id}:${selectedDeviceDetail.active_key?.key_id}:${selectedDeviceDetail.active_key?.algorithm}`
        : "";

    if (selectedDeviceDetail && currentHash !== prevDetailRef) {
        setPrevDetailRef(currentHash);
        const nextKeyId = selectedDeviceDetail.active_key?.key_id || "";
        const nextAlgorithm = normalizeGuideAlgorithm(selectedDeviceDetail.active_key?.algorithm);

        setGuideContext((current) => {
            if (current?.deviceId === selectedDeviceDetail.device_id) {
                const keyStillMatches = current.keyId === nextKeyId && current.algorithm === nextAlgorithm;
                return {
                    deviceId: current.deviceId,
                    keyId: nextKeyId,
                    algorithm: nextAlgorithm,
                    secret: keyStillMatches ? current.secret : null,
                };
            }

            return {
                deviceId: selectedDeviceDetail.device_id,
                keyId: nextKeyId,
                algorithm: nextAlgorithm,
                secret: null,
            };
        });
    }

    const clearGuideContext = () => {
        setGuideContext(null);
    };

    const setGuideContextFromRegister = ({ deviceId, keyId, algorithm, secret }: GuideContextInput) => {
        setGuideContext({
            deviceId,
            keyId,
            algorithm: normalizeGuideAlgorithm(algorithm),
            secret,
        });
    };

    const setGuideContextFromRotate = ({ deviceId, keyId, algorithm, secret }: GuideContextInput) => {
        setGuideContext({
            deviceId,
            keyId,
            algorithm: normalizeGuideAlgorithm(algorithm),
            secret,
        });
    };

    const setGuideContextFromDetail = (detail: ManagedDeviceDetail) => {
        const nextKeyId = detail.active_key?.key_id || "";
        const nextAlgorithm = normalizeGuideAlgorithm(detail.active_key?.algorithm);
        setGuideContext((current) => ({
            deviceId: detail.device_id,
            keyId: nextKeyId,
            algorithm: nextAlgorithm,
            secret:
                current?.deviceId === detail.device_id
                && current.keyId === nextKeyId
                && current.algorithm === nextAlgorithm
                    ? current.secret
                    : null,
        }));
    };

    return {
        guideContext,
        clearGuideContext,
        setGuideContextFromRegister,
        setGuideContextFromRotate,
        setGuideContextFromDetail,
    };
}
