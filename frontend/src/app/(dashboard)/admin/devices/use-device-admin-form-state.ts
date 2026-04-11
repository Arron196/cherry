"use client";

import { useState } from "react";
import { DisableDeviceResponse, RotateDeviceKeyResponse } from "@/types/api";
import { DeviceTestEventResult, InitialKeyDraft } from "./device-admin.types";
import { buildDefaultBatchId } from "./device-admin.utils";

export function useDeviceAdminFormState() {
    const [newDeviceId, setNewDeviceId] = useState("");
    const [displayName, setDisplayName] = useState("");
    const [enableInitialKey, setEnableInitialKey] = useState(true);
    const [initialKeyDraft, setInitialKeyDraft] = useState<InitialKeyDraft>({
        key_id: "",
        algorithm: "HMAC_SHA256",
        secret: "",
    });
    const [latestInitialKeySecret, setLatestInitialKeySecret] = useState<string | null>(null);

    const [rotateDeviceId, setRotateDeviceId] = useState("");
    const [rotateKeyId, setRotateKeyId] = useState("");
    const [rotateAlgorithm, setRotateAlgorithm] = useState("HMAC_SHA256");
    const [rotateSecret, setRotateSecret] = useState("");

    const [disableDeviceId, setDisableDeviceId] = useState("");
    const [disableReason, setDisableReason] = useState("");

    const [lastRotateResult, setLastRotateResult] = useState<RotateDeviceKeyResponse | null>(null);
    const [lastDisableResult, setLastDisableResult] = useState<DisableDeviceResponse | null>(null);
    const [latestRotateSecret, setLatestRotateSecret] = useState<string | null>(null);
    const [testEventBatchId, setTestEventBatchId] = useState<string>(buildDefaultBatchId);
    const [testEventTemperature, setTestEventTemperature] = useState<string>("4.2");
    const [testEventHumidity, setTestEventHumidity] = useState<string>("72");
    const [testEventStatus, setTestEventStatus] = useState<string>("stable");
    const [testEventTimestamp, setTestEventTimestamp] = useState<string>(new Date().toISOString());
    const [testEventResult, setTestEventResult] = useState<DeviceTestEventResult | null>(null);
    const [testEventError, setTestEventError] = useState<string>("");

    return {
        newDeviceId,
        setNewDeviceId,
        displayName,
        setDisplayName,
        enableInitialKey,
        setEnableInitialKey,
        initialKeyDraft,
        setInitialKeyDraft,
        latestInitialKeySecret,
        setLatestInitialKeySecret,
        rotateDeviceId,
        setRotateDeviceId,
        rotateKeyId,
        setRotateKeyId,
        rotateAlgorithm,
        setRotateAlgorithm,
        rotateSecret,
        setRotateSecret,
        disableDeviceId,
        setDisableDeviceId,
        disableReason,
        setDisableReason,
        lastRotateResult,
        setLastRotateResult,
        lastDisableResult,
        setLastDisableResult,
        latestRotateSecret,
        setLatestRotateSecret,
        testEventBatchId,
        setTestEventBatchId,
        testEventTemperature,
        setTestEventTemperature,
        testEventHumidity,
        setTestEventHumidity,
        testEventStatus,
        setTestEventStatus,
        testEventTimestamp,
        setTestEventTimestamp,
        testEventResult,
        setTestEventResult,
        testEventError,
        setTestEventError,
    };
}
