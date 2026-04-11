"use client";

import { useRef, useState } from "react";
import { Services } from "@/lib/services";
import { ManagedDeviceKey } from "@/types/api";
import { KeyQueryState } from "./device-admin.types";
import { extractErrorDetail, extractErrorStatus } from "./device-admin.utils";

export function useDeviceKeyListState() {
    const rotateKeyListRequestIdRef = useRef(0);
    const [keyList, setKeyList] = useState<ManagedDeviceKey[]>([]);
    const [keyListDeviceId, setKeyListDeviceId] = useState("");
    const [keyQueryState, setKeyQueryState] = useState<KeyQueryState>("idle");
    const [keyQueryMessage, setKeyQueryMessage] = useState("");

    const queryManagedDeviceKeys = async (deviceId: string) => {
        const target = deviceId.trim();
        if (!target) {
            rotateKeyListRequestIdRef.current += 1;
            setKeyQueryState("error");
            setKeyQueryMessage("请先输入目标设备 ID。");
            return;
        }

        const requestId = rotateKeyListRequestIdRef.current + 1;
        rotateKeyListRequestIdRef.current = requestId;
        setKeyQueryState("loading");
        setKeyQueryMessage("");

        try {
            const keys = await Services.getManagedDeviceKeys(target);
            if (rotateKeyListRequestIdRef.current !== requestId) {
                return;
            }
            setKeyList(keys);
            setKeyListDeviceId(target);
            setKeyQueryState("loaded");
            setKeyQueryMessage(keys.length === 0 ? "该设备当前没有可展示的密钥。" : "密钥列表已更新。");
        } catch (queryError) {
            if (rotateKeyListRequestIdRef.current !== requestId) {
                return;
            }
            const status = extractErrorStatus(queryError);
            const detail = extractErrorDetail(queryError, "请稍后重试");

            setKeyListDeviceId(target);
            setKeyList([]);

            if (status === 404 || status === 405 || status === 501) {
                setKeyQueryState("unavailable");
                setKeyQueryMessage("当前后端未提供密钥列表接口，将展示最近一次轮换结果。");
                return;
            }

            setKeyQueryState("error");
            setKeyQueryMessage(`密钥列表获取失败：${detail}`);
        }
    };

    return {
        keyList,
        keyListDeviceId,
        keyQueryState,
        keyQueryMessage,
        queryManagedDeviceKeys,
    };
}
