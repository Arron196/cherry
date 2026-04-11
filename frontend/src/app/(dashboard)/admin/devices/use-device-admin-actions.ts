"use client";

import type { Dispatch, SetStateAction } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { signTraceEventPayload } from "@/lib/signing";
import { Services } from "@/lib/services";
import { DisableDeviceResponse, RotateDeviceKeyResponse, TraceEventContractPayload } from "@/types/api";
import { DeviceTestEventResult, FeedbackState, GuideContext, InitialKeyDraft } from "./device-admin.types";
import { buildDefaultBatchId, extractErrorDetail } from "./device-admin.utils";

type DeviceAdminActionDependencies = {
    refetch: () => Promise<unknown>;
    selectedDeviceId: string;
    queryManagedDeviceDetail: (deviceId: string, options?: { onFailure?: () => void }) => Promise<boolean>;
    queryManagedDeviceKeys: (deviceId: string) => Promise<void>;
    setFeedback: Dispatch<SetStateAction<FeedbackState>>;
    newDeviceId: string;
    displayName: string;
    enableInitialKey: boolean;
    initialKeyDraft: InitialKeyDraft;
    setNewDeviceId: Dispatch<SetStateAction<string>>;
    setDisplayName: Dispatch<SetStateAction<string>>;
    setEnableInitialKey: Dispatch<SetStateAction<boolean>>;
    setInitialKeyDraft: Dispatch<SetStateAction<InitialKeyDraft>>;
    setLatestInitialKeySecret: Dispatch<SetStateAction<string | null>>;
    clearGuideContext: () => void;
    setGuideContextFromRegister: (params: { deviceId: string; keyId: string; algorithm: string; secret: string | null }) => void;
    rotateDeviceId: string;
    rotateKeyId: string;
    rotateAlgorithm: string;
    rotateSecret: string;
    setRotateKeyId: Dispatch<SetStateAction<string>>;
    setRotateSecret: Dispatch<SetStateAction<string>>;
    setLastRotateResult: Dispatch<SetStateAction<RotateDeviceKeyResponse | null>>;
    setLatestRotateSecret: Dispatch<SetStateAction<string | null>>;
    setGuideContextFromRotate: (params: { deviceId: string; keyId: string; algorithm: string; secret: string | null }) => void;
    disableDeviceId: string;
    disableReason: string;
    setDisableDeviceId: Dispatch<SetStateAction<string>>;
    setDisableReason: Dispatch<SetStateAction<string>>;
    setLastDisableResult: Dispatch<SetStateAction<DisableDeviceResponse | null>>;
    guideContext: GuideContext | null;
    guideDeviceId: string;
    resolvedGuideKeyId: string;
    resolvedGuideAlgorithm: string;
    availableGuideSecret: string;
    testEventBatchId: string;
    testEventTimestamp: string;
    testEventTemperature: string;
    testEventHumidity: string;
    testEventStatus: string;
    setTestEventResult: Dispatch<SetStateAction<DeviceTestEventResult | null>>;
    setTestEventError: Dispatch<SetStateAction<string>>;
    setTestEventBatchId: Dispatch<SetStateAction<string>>;
    setTestEventTimestamp: Dispatch<SetStateAction<string>>;
};

export function useDeviceAdminActions({
    refetch,
    selectedDeviceId,
    queryManagedDeviceDetail,
    queryManagedDeviceKeys,
    setFeedback,
    newDeviceId,
    displayName,
    enableInitialKey,
    initialKeyDraft,
    setNewDeviceId,
    setDisplayName,
    setEnableInitialKey,
    setInitialKeyDraft,
    setLatestInitialKeySecret,
    clearGuideContext,
    setGuideContextFromRegister,
    rotateDeviceId,
    rotateKeyId,
    rotateAlgorithm,
    rotateSecret,
    setRotateKeyId,
    setRotateSecret,
    setLastRotateResult,
    setLatestRotateSecret,
    setGuideContextFromRotate,
    disableDeviceId,
    disableReason,
    setDisableDeviceId,
    setDisableReason,
    setLastDisableResult,
    guideContext,
    guideDeviceId,
    resolvedGuideKeyId,
    resolvedGuideAlgorithm,
    availableGuideSecret,
    testEventBatchId,
    testEventTimestamp,
    testEventTemperature,
    testEventHumidity,
    testEventStatus,
    setTestEventResult,
    setTestEventError,
    setTestEventBatchId,
    setTestEventTimestamp,
}: DeviceAdminActionDependencies) {
    const queryClient = useQueryClient();

    const refreshManagedDevices = async () => {
        await queryClient.invalidateQueries({ queryKey: ["managed-devices-page"] });
        await queryClient.invalidateQueries({ queryKey: ["managed-devices"] });
        await refetch();
    };

    const registerMutation = useMutation({
        mutationFn: async (payload: {
            device_id: string;
            display_name?: string;
            initial_key?: {
                key_id: string;
                algorithm: string;
                secret: string;
            };
        }) => Services.registerDevice(payload),
        onSuccess: async (result, variables) => {
            if (result.initial_key) {
                setLatestInitialKeySecret(variables.initial_key?.secret ?? null);
                setGuideContextFromRegister({
                    deviceId: variables.device_id,
                    keyId: result.initial_key.key_id,
                    algorithm: result.initial_key.algorithm || "HMAC_SHA256",
                    secret: variables.initial_key?.secret ?? null,
                });
                setFeedback({
                    type: "ok",
                    text: `设备 ${variables.device_id} 注册成功，并已创建首个密钥 ${result.initial_key.key_id}。`,
                });
                await queryManagedDeviceKeys(variables.device_id);
            } else {
                setLatestInitialKeySecret(null);
                clearGuideContext();
                setFeedback({ type: "ok", text: `设备 ${variables.device_id} 注册成功。` });
            }
            setNewDeviceId("");
            setDisplayName("");
            setEnableInitialKey(true);
            setInitialKeyDraft({ key_id: "", algorithm: "HMAC_SHA256", secret: "" });
            await refreshManagedDevices();
            if (selectedDeviceId === variables.device_id) {
                await queryManagedDeviceDetail(variables.device_id);
            }
        },
        onError: (mutationError) => {
            const detail = extractErrorDetail(mutationError, "未知错误");
            setFeedback({ type: "error", text: `注册失败：${detail}` });
        },
    });

    const rotateKeyMutation = useMutation({
        mutationFn: async (payload: { device_id: string; key_id: string; algorithm: string; public_key: string }) => {
            return Services.rotateDeviceKey(payload.device_id, {
                key_id: payload.key_id,
                algorithm: payload.algorithm,
                public_key: payload.public_key,
            });
        },
        onSuccess: async (result, variables) => {
            setLastRotateResult(result);
            setLatestRotateSecret(variables.public_key);
            setGuideContextFromRotate({
                deviceId: variables.device_id,
                keyId: result.key_id,
                algorithm: result.algorithm || "HMAC_SHA256",
                secret: variables.public_key,
            });
            setFeedback({ type: "ok", text: `设备 ${variables.device_id} 密钥轮换成功。` });
            setRotateKeyId("");
            setRotateSecret("");
            await refreshManagedDevices();
            await queryManagedDeviceKeys(variables.device_id);
            if (selectedDeviceId === variables.device_id) {
                await queryManagedDeviceDetail(variables.device_id);
            }
        },
        onError: (mutationError) => {
            const detail = extractErrorDetail(mutationError, "未知错误");
            setFeedback({ type: "error", text: `密钥轮换失败：${detail}` });
        },
    });

    const disableMutation = useMutation({
        mutationFn: async (payload: { device_id: string; reason?: string }) => {
            return Services.disableManagedDevice(payload.device_id, { reason: payload.reason });
        },
        onSuccess: async (result, variables) => {
            setLastDisableResult(result);
            if (guideContext?.deviceId === variables.device_id) {
                clearGuideContext();
            }

            if (rotateDeviceId.trim() === variables.device_id && (rotateKeyId.trim() || rotateSecret.trim())) {
                setRotateKeyId("");
                setRotateSecret("");
            }

            if (newDeviceId.trim() === variables.device_id && (initialKeyDraft.key_id.trim() || initialKeyDraft.secret.trim())) {
                setInitialKeyDraft((current) => ({
                    ...current,
                    key_id: "",
                    secret: "",
                }));
            }

            setFeedback({
                type: "ok",
                text: `设备 ${variables.device_id} 已停用，退役密钥 ${result.retired_key_ids.length} 个。`,
            });
            setDisableDeviceId("");
            setDisableReason("");
            await refreshManagedDevices();
            if (selectedDeviceId === variables.device_id) {
                await queryManagedDeviceDetail(variables.device_id);
            }
        },
        onError: (mutationError) => {
            const detail = extractErrorDetail(mutationError, "未知错误");
            setFeedback({ type: "error", text: `停用设备失败：${detail}` });
        },
    });

    const ingestTestEventMutation = useMutation({
        mutationFn: async (payload: {
            device_id: string;
            key_id: string;
            algorithm: string;
            secret: string;
            batch_id: string;
            timestamp: string;
            temperature: number;
            humidity: number;
            status: string;
        }) => {
            const draftPayload: TraceEventContractPayload = {
                version: "1.0.0",
                device_id: payload.device_id,
                batch_id: payload.batch_id,
                timestamp: payload.timestamp,
                sensor_payload: {
                    temperature_c: payload.temperature,
                    humidity_pct: payload.humidity,
                    status: payload.status,
                },
                signature_envelope: {
                    algorithm: payload.algorithm,
                    key_id: payload.key_id,
                    signature: "",
                },
            };

            const signedPayload = await signTraceEventPayload(draftPayload, payload.secret);
            const idempotencyKey = `idem-${payload.device_id}-${Date.now()}`;
            const response = await Services.ingestEvent({
                payload: signedPayload,
                idempotencyKey,
            });

            return {
                idempotency_key: idempotencyKey,
                payload: signedPayload,
                response,
            } as DeviceTestEventResult;
        },
        onSuccess: async (result, variables) => {
            setTestEventResult(result);
            setTestEventError("");
            setFeedback({
                type: "ok",
                text: `设备 ${variables.device_id} 测试事件上报成功，事件 ID：${result.response.event_id}。`,
            });
            setTestEventBatchId(buildDefaultBatchId());
            setTestEventTimestamp(new Date().toISOString());
            await refreshManagedDevices();
            if (selectedDeviceId === variables.device_id) {
                await queryManagedDeviceDetail(variables.device_id);
            }
        },
        onError: (mutationError) => {
            const detail = extractErrorDetail(mutationError, "未知错误");
            setTestEventError(detail);
            setTestEventResult(null);
            setFeedback({ type: "error", text: `测试事件上报失败：${detail}` });
        },
    });

    const handleRegister = () => {
        const trimmedDeviceId = newDeviceId.trim();
        const trimmedDisplayName = displayName.trim();
        if (!trimmedDeviceId) {
            setFeedback({ type: "error", text: "请先填写设备 ID。" });
            return;
        }

        const payload: {
            device_id: string;
            display_name?: string;
            initial_key?: {
                key_id: string;
                algorithm: string;
                secret: string;
            };
        } = {
            device_id: trimmedDeviceId,
            display_name: trimmedDisplayName || undefined,
        };

        if (enableInitialKey) {
            const keyId = initialKeyDraft.key_id.trim();
            const algorithm = initialKeyDraft.algorithm.trim();
            const secret = initialKeyDraft.secret.trim();
            if (!keyId || !algorithm || !secret) {
                setFeedback({ type: "error", text: "已开启首钥创建，请完整填写首钥 Key ID、算法和密钥。" });
                return;
            }
            payload.initial_key = {
                key_id: keyId,
                algorithm,
                secret,
            };
        }

        registerMutation.mutate(payload);
    };

    const handleRotateKey = () => {
        const trimmedDeviceId = rotateDeviceId.trim();
        const trimmedKeyId = rotateKeyId.trim();
        const trimmedAlgorithm = rotateAlgorithm.trim();
        const trimmedSecret = rotateSecret.trim();

        if (!trimmedDeviceId || !trimmedKeyId || !trimmedAlgorithm || !trimmedSecret) {
            setFeedback({ type: "error", text: "请完整填写密钥轮换信息。" });
            return;
        }

        rotateKeyMutation.mutate({
            device_id: trimmedDeviceId,
            key_id: trimmedKeyId,
            algorithm: trimmedAlgorithm,
            public_key: trimmedSecret,
        });
    };

    const handleDisableDevice = () => {
        const trimmedDeviceId = disableDeviceId.trim();
        const trimmedReason = disableReason.trim();

        if (!trimmedDeviceId) {
            setFeedback({ type: "error", text: "请先输入要停用的设备 ID。" });
            return;
        }

        disableMutation.mutate({
            device_id: trimmedDeviceId,
            reason: trimmedReason || undefined,
        });
    };

    const handleIngestTestEvent = () => {
        setTestEventError("");

        const deviceId = guideDeviceId.trim();
        const keyId = resolvedGuideKeyId.trim();
        const algorithm = resolvedGuideAlgorithm.trim().toUpperCase();
        const secret = availableGuideSecret.trim();
        const batchId = testEventBatchId.trim();
        const timestamp = testEventTimestamp.trim();
        const eventStatus = testEventStatus.trim() || "stable";
        const temperature = Number(testEventTemperature);
        const humidity = Number(testEventHumidity);

        if (!deviceId || deviceId === "demo-device-001") {
            setTestEventError("请先选择真实设备，或先完成设备注册。\n提示：可在列表点击“查看详情”后再发送测试事件。");
            return;
        }

        if (!keyId || keyId === "demo-key-v1") {
            setTestEventError("请先准备可用的 key_id（注册首钥或完成密钥轮换后可自动带出）。");
            return;
        }

        if (!secret) {
            setTestEventError("缺少真实签名 secret。请先注册首钥或执行密钥轮换，并使用页面返回的 secret。");
            return;
        }

        if (algorithm !== "HMAC_SHA256") {
            setTestEventError("当前仅支持 HMAC_SHA256 自动签名，请调整算法后重试。");
            return;
        }

        if (!batchId) {
            setTestEventError("请填写批次 ID。建议使用默认值后直接发送。");
            return;
        }

        if (!timestamp || Number.isNaN(new Date(timestamp).getTime())) {
            setTestEventError("时间戳格式无效，请使用 ISO8601，例如 2026-02-11T10:00:00Z。");
            return;
        }

        if (!Number.isFinite(temperature)) {
            setTestEventError("温度必须是数字。示例：4.2");
            return;
        }

        if (!Number.isFinite(humidity)) {
            setTestEventError("湿度必须是数字。示例：72");
            return;
        }

        ingestTestEventMutation.mutate({
            device_id: deviceId,
            key_id: keyId,
            algorithm,
            secret,
            batch_id: batchId,
            timestamp,
            temperature,
            humidity,
            status: eventStatus,
        });
    };

    return {
        registerMutation,
        rotateKeyMutation,
        disableMutation,
        ingestTestEventMutation,
        refreshManagedDevices,
        handleRegister,
        handleRotateKey,
        handleDisableDevice,
        handleIngestTestEvent,
    };
}
