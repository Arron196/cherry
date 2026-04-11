"use client";

import { Dispatch, SetStateAction, useEffect, useMemo } from "react";
import { useManagedDevicesPage } from "@/hooks/use-queries";
import { FeedbackState } from "./device-admin.types";
import { getDeviceStatusMeta, getOnlineStatusMeta } from "./device-admin.utils";

type UseDeviceOverviewViewModelParams = {
    statusFilter: "all" | "active" | "disabled";
    pageIndex: number;
    pageSize: number;
    onlineWindowSeconds: number;
    pageJumpInput: string;
    setPageIndex: Dispatch<SetStateAction<number>>;
    setPageJumpInput: Dispatch<SetStateAction<string>>;
    setFeedback: Dispatch<SetStateAction<FeedbackState>>;
};

export function useDeviceOverviewViewModel({
    statusFilter,
    pageIndex,
    pageSize,
    onlineWindowSeconds,
    pageJumpInput,
    setPageIndex,
    setPageJumpInput,
    setFeedback,
}: UseDeviceOverviewViewModelParams) {
    const managedDeviceParams = useMemo(
        () => ({
            limit: pageSize,
            offset: pageIndex * pageSize,
            status: statusFilter === "all" ? undefined : statusFilter,
        }),
        [statusFilter, pageIndex, pageSize]
    );

    const { data: managedDevicePage, isLoading, isFetching, isError, error, refetch } = useManagedDevicesPage(managedDeviceParams);
    const devices = useMemo(() => managedDevicePage?.items ?? [], [managedDevicePage]);
    const totalDevices = managedDevicePage?.total ?? 0;
    const totalPages = Math.max(1, Math.ceil(totalDevices / pageSize));
    const displayCurrentPage = totalDevices === 0 ? 0 : pageIndex + 1;

    const pageEnabledDevices = useMemo(
        () => devices.filter((device) => getDeviceStatusMeta(device.status).variant === "success").length,
        [devices]
    );
    const pageDisabledDevices = useMemo(
        () => devices.filter((device) => getDeviceStatusMeta(device.status).variant === "destructive").length,
        [devices]
    );
    const pageOnlineDevices = useMemo(
        () => devices.filter((device) => getOnlineStatusMeta(device.last_seen_at, onlineWindowSeconds).variant === "success").length,
        [devices, onlineWindowSeconds]
    );

    useEffect(() => {
        setPageJumpInput(String(displayCurrentPage > 0 ? displayCurrentPage : 1));
    }, [displayCurrentPage, setPageJumpInput]);

    useEffect(() => {
        const maxPageIndex = Math.max(0, totalPages - 1);
        if (pageIndex > maxPageIndex) {
            setPageIndex(maxPageIndex);
        }
    }, [pageIndex, setPageIndex, totalPages]);

    const handlePageJump = () => {
        if (totalDevices === 0) {
            setFeedback({ type: "error", text: "当前没有可跳转的分页数据。" });
            return;
        }

        const target = Number.parseInt(pageJumpInput.trim(), 10);
        if (!Number.isFinite(target) || target < 1 || target > totalPages) {
            setFeedback({ type: "error", text: `请输入 1 到 ${totalPages} 之间的页码。` });
            return;
        }

        setPageIndex(target - 1);
    };

    return {
        managedDevicePage,
        isLoading,
        isFetching,
        isError,
        error,
        refetch,
        devices,
        totalDevices,
        totalPages,
        displayCurrentPage,
        pageEnabledDevices,
        pageDisabledDevices,
        pageOnlineDevices,
        handlePageJump,
    };
}
