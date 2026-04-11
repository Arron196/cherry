"use client";

import { useEffect, useState } from "react";
import {
    DEFAULT_ONLINE_WINDOW_SECONDS,
    DEVICE_LIST_PREFERENCES_KEY,
    DeviceStatusView,
    ONLINE_WINDOW_OPTIONS,
    PAGE_SIZE_OPTIONS,
} from "./device-admin.utils";

type UseDeviceListPreferencesParams = {
    initialPageJumpInput?: string;
};

export function useDeviceListPreferences({
    initialPageJumpInput = "1",
}: UseDeviceListPreferencesParams) {
    const [statusFilter, setStatusFilter] = useState<DeviceStatusView>("all");
    const [pageIndex, setPageIndex] = useState(0);
    const [pageSize, setPageSize] = useState<number>(20);
    const [onlineWindowSeconds, setOnlineWindowSeconds] = useState<number>(DEFAULT_ONLINE_WINDOW_SECONDS);
    const [pageJumpInput, setPageJumpInput] = useState(initialPageJumpInput);
    const [isListPreferencesReady, setIsListPreferencesReady] = useState(false);

    useEffect(() => {
        try {
            const raw = window.localStorage.getItem(DEVICE_LIST_PREFERENCES_KEY);
            if (!raw) {
                return;
            }

            const parsed = JSON.parse(raw) as {
                status_filter?: string;
                page_size?: number;
                online_window_seconds?: number;
            };
            if (parsed.status_filter === "all" || parsed.status_filter === "active" || parsed.status_filter === "disabled") {
                setStatusFilter(parsed.status_filter);
            }
            if (typeof parsed.page_size === "number" && PAGE_SIZE_OPTIONS.includes(parsed.page_size as 10 | 20 | 50)) {
                setPageSize(parsed.page_size);
            }
            if (
                typeof parsed.online_window_seconds === "number"
                && ONLINE_WINDOW_OPTIONS.includes(parsed.online_window_seconds as 60 | 300 | 900 | 1800)
            ) {
                setOnlineWindowSeconds(parsed.online_window_seconds);
            }
        } catch {
        } finally {
            setIsListPreferencesReady(true);
        }
    }, []);

    useEffect(() => {
        if (!isListPreferencesReady) {
            return;
        }
        try {
            window.localStorage.setItem(
                DEVICE_LIST_PREFERENCES_KEY,
                JSON.stringify({
                    status_filter: statusFilter,
                    page_size: pageSize,
                    online_window_seconds: onlineWindowSeconds,
                })
            );
        } catch {
        }
    }, [isListPreferencesReady, statusFilter, pageSize, onlineWindowSeconds]);

    const handleStatusFilterChange = (nextStatus: DeviceStatusView) => {
        setStatusFilter(nextStatus);
        setPageIndex(0);
    };

    const handlePageSizeChange = (nextPageSize: number) => {
        setPageSize(nextPageSize);
        setPageIndex(0);
    };

    return {
        statusFilter,
        pageIndex,
        pageSize,
        onlineWindowSeconds,
        pageJumpInput,
        setPageIndex,
        setOnlineWindowSeconds,
        setPageJumpInput,
        handleStatusFilterChange,
        handlePageSizeChange,
    };
}
