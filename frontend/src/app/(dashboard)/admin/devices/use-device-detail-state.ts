"use client";

import { useRef, useState } from "react";
import { Services } from "@/lib/services";
import { ManagedDeviceAudit, ManagedDeviceDetail, ManagedDeviceKey } from "@/types/api";
import { KeyQueryState } from "./device-admin.types";
import { extractErrorDetail, extractErrorStatus } from "./device-admin.utils";

type QueryManagedDeviceDetailOptions = {
    onFailure?: () => void;
};

export function useDeviceDetailState() {
    const detailRequestIdRef = useRef(0);
    const detailKeyTimelineRequestIdRef = useRef(0);
    const detailAuditTimelineRequestIdRef = useRef(0);
    const selectedDeviceIdRef = useRef("");

    const [selectedDeviceId, setSelectedDeviceId] = useState("");
    const [selectedDeviceDetail, setSelectedDeviceDetail] = useState<ManagedDeviceDetail | null>(null);
    const [isDetailLoading, setIsDetailLoading] = useState(false);
    const [detailError, setDetailError] = useState("");
    const [detailKeyList, setDetailKeyList] = useState<ManagedDeviceKey[]>([]);
    const [detailKeyDeviceId, setDetailKeyDeviceId] = useState("");
    const [detailKeyQueryState, setDetailKeyQueryState] = useState<KeyQueryState>("idle");
    const [detailKeyQueryMessage, setDetailKeyQueryMessage] = useState("");
    const [detailAuditList, setDetailAuditList] = useState<ManagedDeviceAudit[]>([]);
    const [detailAuditDeviceId, setDetailAuditDeviceId] = useState("");
    const [detailAuditQueryState, setDetailAuditQueryState] = useState<KeyQueryState>("idle");
    const [detailAuditQueryMessage, setDetailAuditQueryMessage] = useState("");

    const queryManagedDeviceDetail = async (
        deviceId: string,
        options: QueryManagedDeviceDetailOptions = {}
    ): Promise<boolean> => {
        const target = deviceId.trim();
        if (!target) {
            detailRequestIdRef.current += 1;
            detailKeyTimelineRequestIdRef.current += 1;
            detailAuditTimelineRequestIdRef.current += 1;
            selectedDeviceIdRef.current = "";
            setIsDetailLoading(false);
            setDetailError("请先选择设备。");
            setSelectedDeviceId("");
            setSelectedDeviceDetail(null);
            setDetailKeyList([]);
            setDetailKeyDeviceId("");
            setDetailKeyQueryState("idle");
            setDetailKeyQueryMessage("");
            setDetailAuditList([]);
            setDetailAuditDeviceId("");
            setDetailAuditQueryState("idle");
            setDetailAuditQueryMessage("");
            options.onFailure?.();
            return false;
        }

        const requestId = detailRequestIdRef.current + 1;
        const isSwitchingDevice = target !== selectedDeviceIdRef.current;
        detailRequestIdRef.current = requestId;
        detailKeyTimelineRequestIdRef.current += 1;
        detailAuditTimelineRequestIdRef.current += 1;
        selectedDeviceIdRef.current = target;
        setSelectedDeviceId(target);
        setIsDetailLoading(true);
        setDetailError("");
        if (isSwitchingDevice) {
            setSelectedDeviceDetail(null);
            setDetailKeyList([]);
            setDetailKeyDeviceId("");
            setDetailKeyQueryState("idle");
            setDetailKeyQueryMessage("");
            setDetailAuditList([]);
            setDetailAuditDeviceId("");
            setDetailAuditQueryState("idle");
            setDetailAuditQueryMessage("");
        }
        try {
            const detail = await Services.getManagedDeviceDetail(target);
            const [keysResult, auditsResult] = await Promise.allSettled([
                Services.getManagedDeviceKeys(target),
                Services.getManagedDeviceAudits(target),
            ]);

            if (detailRequestIdRef.current !== requestId) {
                return false;
            }

            setSelectedDeviceDetail(detail);
            setDetailKeyDeviceId(target);
            if (keysResult.status === "fulfilled") {
                const keys = keysResult.value;
                setDetailKeyList(keys);
                setDetailKeyQueryState("loaded");
                setDetailKeyQueryMessage(keys.length === 0 ? "该设备暂无密钥历史。" : "密钥时间线已更新。");
            } else {
                const status = extractErrorStatus(keysResult.reason);
                const detailMessage = extractErrorDetail(keysResult.reason, "请稍后重试");
                setDetailKeyList([]);
                if (status === 404 || status === 405 || status === 501) {
                    setDetailKeyQueryState("unavailable");
                    setDetailKeyQueryMessage("当前后端未提供该设备的密钥列表能力。");
                } else {
                    setDetailKeyQueryState("error");
                    setDetailKeyQueryMessage(`密钥时间线加载失败：${detailMessage}`);
                }
            }

            setDetailAuditDeviceId(target);
            if (auditsResult.status === "fulfilled") {
                const audits = auditsResult.value;
                setDetailAuditList(audits);
                setDetailAuditQueryState("loaded");
                setDetailAuditQueryMessage(audits.length === 0 ? "该设备暂无审计记录。" : "审计时间线已更新。");
            } else {
                const status = extractErrorStatus(auditsResult.reason);
                const detailMessage = extractErrorDetail(auditsResult.reason, "请稍后重试");
                setDetailAuditList([]);
                if (status === 404 || status === 405 || status === 501) {
                    setDetailAuditQueryState("unavailable");
                    setDetailAuditQueryMessage("当前后端未提供该设备的审计时间线能力。");
                } else {
                    setDetailAuditQueryState("error");
                    setDetailAuditQueryMessage(`审计时间线加载失败：${detailMessage}`);
                }
            }

            return true;
        } catch (queryError) {
            if (detailRequestIdRef.current !== requestId) {
                return false;
            }
            setSelectedDeviceDetail(null);
            setDetailKeyList([]);
            setDetailKeyDeviceId(target);
            setDetailKeyQueryState("error");
            setDetailKeyQueryMessage("");
            setDetailAuditList([]);
            setDetailAuditDeviceId(target);
            setDetailAuditQueryState("error");
            setDetailAuditQueryMessage("");
            setDetailError(`设备详情获取失败：${extractErrorDetail(queryError, "请稍后重试")}`);
            options.onFailure?.();
            return false;
        } finally {
            if (detailRequestIdRef.current === requestId) {
                setIsDetailLoading(false);
            }
        }
    };

    const queryDeviceKeyTimeline = async (deviceId: string) => {
        const target = deviceId.trim();
        if (!target) {
            detailKeyTimelineRequestIdRef.current += 1;
            setDetailKeyList([]);
            setDetailKeyDeviceId("");
            setDetailKeyQueryState("error");
            setDetailKeyQueryMessage("请先选择目标设备。");
            return;
        }

        const requestId = detailKeyTimelineRequestIdRef.current + 1;
        detailKeyTimelineRequestIdRef.current = requestId;
        setDetailKeyDeviceId(target);
        setDetailKeyQueryState("loading");
        setDetailKeyQueryMessage("");
        try {
            const keys = await Services.getManagedDeviceKeys(target);
            if (detailKeyTimelineRequestIdRef.current !== requestId || selectedDeviceIdRef.current !== target) {
                return;
            }
            setDetailKeyList(keys);
            setDetailKeyQueryState("loaded");
            setDetailKeyQueryMessage(keys.length === 0 ? "该设备暂无密钥历史。" : "密钥时间线已更新。");
        } catch (queryError) {
            if (detailKeyTimelineRequestIdRef.current !== requestId || selectedDeviceIdRef.current !== target) {
                return;
            }
            const status = extractErrorStatus(queryError);
            const detail = extractErrorDetail(queryError, "请稍后重试");
            setDetailKeyList([]);
            if (status === 404 || status === 405 || status === 501) {
                setDetailKeyQueryState("unavailable");
                setDetailKeyQueryMessage("当前后端未提供该设备的密钥列表能力。");
                return;
            }
            setDetailKeyQueryState("error");
            setDetailKeyQueryMessage(`密钥时间线加载失败：${detail}`);
        }
    };

    const queryDeviceAuditTimeline = async (deviceId: string) => {
        const target = deviceId.trim();
        if (!target) {
            detailAuditTimelineRequestIdRef.current += 1;
            setDetailAuditList([]);
            setDetailAuditDeviceId("");
            setDetailAuditQueryState("error");
            setDetailAuditQueryMessage("请先选择目标设备。");
            return;
        }

        const requestId = detailAuditTimelineRequestIdRef.current + 1;
        detailAuditTimelineRequestIdRef.current = requestId;
        setDetailAuditDeviceId(target);
        setDetailAuditQueryState("loading");
        setDetailAuditQueryMessage("");
        try {
            const audits = await Services.getManagedDeviceAudits(target);
            if (detailAuditTimelineRequestIdRef.current !== requestId || selectedDeviceIdRef.current !== target) {
                return;
            }
            setDetailAuditList(audits);
            setDetailAuditQueryState("loaded");
            setDetailAuditQueryMessage(audits.length === 0 ? "该设备暂无审计记录。" : "审计时间线已更新。");
        } catch (queryError) {
            if (detailAuditTimelineRequestIdRef.current !== requestId || selectedDeviceIdRef.current !== target) {
                return;
            }
            const status = extractErrorStatus(queryError);
            const detail = extractErrorDetail(queryError, "请稍后重试");
            setDetailAuditList([]);
            if (status === 404 || status === 405 || status === 501) {
                setDetailAuditQueryState("unavailable");
                setDetailAuditQueryMessage("当前后端未提供该设备的审计时间线能力。");
                return;
            }
            setDetailAuditQueryState("error");
            setDetailAuditQueryMessage(`审计时间线加载失败：${detail}`);
        }
    };

    return {
        selectedDeviceId,
        selectedDeviceDetail,
        isDetailLoading,
        detailError,
        detailKeyList,
        detailKeyDeviceId,
        detailKeyQueryState,
        detailKeyQueryMessage,
        detailAuditList,
        detailAuditDeviceId,
        detailAuditQueryState,
        detailAuditQueryMessage,
        queryManagedDeviceDetail,
        queryDeviceKeyTimeline,
        queryDeviceAuditTimeline,
    };
}
