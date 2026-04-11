"use client";

import { Dispatch, SetStateAction, useEffect, useState } from "react";
import { ManagedDeviceDetail } from "@/types/api";
import { DEFAULT_GUIDE_ALGORITHM, FeedbackState } from "./device-admin.types";
import { scrollToSection } from "./device-admin.utils";

type UseDeviceAdminPageInteractionsParams = {
    latestInitialKeySecret: string | null;
    selectedDeviceDetail: ManagedDeviceDetail | null;
    setFeedback: Dispatch<SetStateAction<FeedbackState>>;
    setRotateDeviceId: Dispatch<SetStateAction<string>>;
    setRotateAlgorithm: Dispatch<SetStateAction<string>>;
    setRotateKeyId: Dispatch<SetStateAction<string>>;
    setRotateSecret: Dispatch<SetStateAction<string>>;
    setDisableDeviceId: Dispatch<SetStateAction<string>>;
    setDisableReason: Dispatch<SetStateAction<string>>;
    setGuideContextFromDetail: (detail: ManagedDeviceDetail) => void;
};

export function useDeviceAdminPageInteractions({
    latestInitialKeySecret,
    selectedDeviceDetail,
    setFeedback,
    setRotateDeviceId,
    setRotateAlgorithm,
    setRotateKeyId,
    setRotateSecret,
    setDisableDeviceId,
    setDisableReason,
    setGuideContextFromDetail,
}: UseDeviceAdminPageInteractionsParams) {
    const [pendingDetailScroll, setPendingDetailScroll] = useState(false);
    const [highlightSectionId, setHighlightSectionId] = useState<string | null>(null);

    const copyTextWithFeedback = async (text: string, successMessage: string, errorMessage: string) => {
        try {
            await navigator.clipboard.writeText(text);
            setFeedback({ type: "ok", text: successMessage });
        } catch {
            setFeedback({ type: "error", text: errorMessage });
        }
    };

    const handleCopyInitialSecret = async () => {
        if (!latestInitialKeySecret) {
            return;
        }
        await copyTextWithFeedback(latestInitialKeySecret, "首钥密钥已复制到剪贴板，请妥善保存。", "复制失败，请手动复制并妥善保存。");
    };

    const handleCopyRetiredKeyIds = async (deviceId: string, keyIds: string[], context: "轮换" | "停用") => {
        if (keyIds.length === 0) {
            setFeedback({ type: "error", text: `设备 ${deviceId} 在${context}操作中没有退役密钥可复制。` });
            return;
        }
        await copyTextWithFeedback(
            keyIds.join("\n"),
            `设备 ${deviceId} 的退役密钥 ID 已复制（${context}）。`,
            "复制失败，请手动复制退役密钥 ID。"
        );
    };

    const focusSection = (sectionId: string) => {
        setPendingDetailScroll(false);
        scrollToSection(sectionId);
        setHighlightSectionId(sectionId);
    };

    const handleFillRotateFromDetail = () => {
        if (!selectedDeviceDetail) {
            return;
        }
        setRotateDeviceId(selectedDeviceDetail.device_id);
        setRotateAlgorithm(DEFAULT_GUIDE_ALGORITHM);
        setRotateKeyId("");
        setRotateSecret("");
        setGuideContextFromDetail(selectedDeviceDetail);
        setFeedback({ type: "ok", text: `已填充设备 ${selectedDeviceDetail.device_id} 到密钥轮换表单。` });
        focusSection("section-device-rotate");
    };

    const handleFillDisableFromDetail = () => {
        if (!selectedDeviceDetail) {
            return;
        }
        setDisableDeviceId(selectedDeviceDetail.device_id);
        setDisableReason("");
        setFeedback({ type: "ok", text: `已填充设备 ${selectedDeviceDetail.device_id} 到停用表单。` });
        focusSection("section-device-disable");
    };

    const prepareRotateFromOverview = (deviceId: string) => {
        setRotateDeviceId(deviceId);
        setRotateAlgorithm(DEFAULT_GUIDE_ALGORITHM);
        setRotateKeyId("");
        setRotateSecret("");
        setFeedback({ type: "ok", text: `已将 ${deviceId} 填充到密钥轮换表单。` });
        focusSection("section-device-rotate");
    };

    const prepareDisableFromOverview = (deviceId: string) => {
        setDisableDeviceId(deviceId);
        setDisableReason("");
        setFeedback({ type: "ok", text: `已将 ${deviceId} 填充到停用设备表单。` });
        focusSection("section-device-disable");
    };

    useEffect(() => {
        if (!pendingDetailScroll || !selectedDeviceDetail) {
            return;
        }
        const timer = window.setTimeout(() => {
            scrollToSection("section-device-detail");
            setHighlightSectionId("section-device-detail");
            setPendingDetailScroll(false);
        }, 120);
        return () => window.clearTimeout(timer);
    }, [pendingDetailScroll, selectedDeviceDetail]);

    useEffect(() => {
        if (!highlightSectionId) {
            return;
        }
        const timer = window.setTimeout(() => setHighlightSectionId(null), 1500);
        return () => window.clearTimeout(timer);
    }, [highlightSectionId]);

    return {
        highlightSectionId,
        pendingDetailScroll,
        setPendingDetailScroll,
        handleCopyInitialSecret,
        handleCopyRetiredKeyIds,
        handleFillRotateFromDetail,
        handleFillDisableFromDetail,
        focusSection,
        prepareRotateFromOverview,
        prepareDisableFromOverview,
    };
}
