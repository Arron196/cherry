import { format, formatDistanceToNow } from "date-fns";
import { zhCN } from "date-fns/locale";
import { DeviceStatusFilter, ManagedDeviceAudit } from "@/types/api";

export type BadgeVariant = "success" | "warning" | "destructive" | "secondary";
export type DeviceStatusView = DeviceStatusFilter | "all";

export const PAGE_SIZE_OPTIONS = [10, 20, 50] as const;
export const ONLINE_WINDOW_OPTIONS = [60, 300, 900, 1800] as const;
export const DEVICE_LIST_PREFERENCES_KEY = "traceability-admin-devices-list-preferences";
export const DEFAULT_ONLINE_WINDOW_SECONDS = 300;

export function toPrettyJson(value: unknown): string {
    try {
        return JSON.stringify(value, null, 2);
    } catch {
        return String(value);
    }
}

export function truncateId(id: string | null | undefined, length: number = 8): string {
    if (!id) return "—";
    if (id.length <= length + 4) return id;
    return `${id.substring(0, Math.ceil(length / 2))}...${id.substring(id.length - Math.floor(length / 2))}`;
}

export function scrollToSection(sectionId: string): void {
    if (typeof document === "undefined") {
        return;
    }
    const target = document.getElementById(sectionId);
    const container = document.getElementById("main-content");
    
    if (target && container) {
        const containerTop = container.getBoundingClientRect().top;
        const targetTop = target.getBoundingClientRect().top;
        
        container.scrollBy({
            top: targetTop - containerTop - 16, // leave 16px top padding space
            behavior: "smooth"
        });
    } else if (target) {
        target.scrollIntoView({ behavior: "smooth", block: "start" });
    }
}

export function buildDefaultBatchId(): string {
    return `batch-demo-${format(new Date(), "yyyyMMdd-HHmmss")}`;
}

export function extractErrorDetail(error: unknown, fallback: string): string {
    if (typeof error === "object" && error !== null && "detail" in error) {
        return String((error as { detail: unknown }).detail);
    }
    return fallback;
}

export function extractErrorStatus(error: unknown): number | null {
    if (typeof error === "object" && error !== null && "status" in error) {
        const status = Number((error as { status: unknown }).status);
        return Number.isFinite(status) ? status : null;
    }
    return null;
}

export function formatDateTime(value?: string | null): string {
    if (!value) {
        return "—";
    }

    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
        return value;
    }
    return format(date, "yyyy-MM-dd HH:mm:ss");
}

export function formatRelativeTime(value?: string | null): string {
    if (!value) return "无记录";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return formatDistanceToNow(date, { addSuffix: true, locale: zhCN });
}

export function getDeviceStatusMeta(status: string): { label: string; variant: BadgeVariant } {
    const normalized = status.trim().toUpperCase();
    if (normalized === "ACTIVE" || normalized === "ENABLED") {
        return { label: "已启用", variant: "success" };
    }
    if (normalized === "DISABLED") {
        return { label: "已停用", variant: "destructive" };
    }
    if (normalized === "PENDING") {
        return { label: "待生效", variant: "warning" };
    }
    return { label: status || "未知状态", variant: "secondary" };
}

export function getOnlineStatusMeta(
    lastSeenAt?: string | null,
    onlineWindowSeconds: number = DEFAULT_ONLINE_WINDOW_SECONDS
): { label: string; variant: BadgeVariant } {
    if (!lastSeenAt) {
        return { label: "未知", variant: "secondary" };
    }

    const lastSeenDate = new Date(lastSeenAt);
    if (Number.isNaN(lastSeenDate.getTime())) {
        return { label: "未知", variant: "secondary" };
    }

    const isOnline = Date.now() - lastSeenDate.getTime() <= onlineWindowSeconds * 1000;
    return isOnline ? { label: "在线", variant: "success" } : { label: "离线", variant: "secondary" };
}

export function toCnKeyStatus(status?: string | null): string {
    const normalized = (status || "").trim().toUpperCase();
    if (normalized === "ACTIVE") {
        return "启用中";
    }
    if (normalized === "RETIRED") {
        return "已退役";
    }
    if (normalized === "DISABLED") {
        return "已停用";
    }
    return status || "未知";
}

export function toCnAuditAction(action: string): string {
    const normalized = action.trim().toLowerCase();
    if (normalized === "admin.device.register") {
        return "设备注册";
    }
    if (normalized === "admin.device.key.rotate") {
        return "密钥轮换";
    }
    if (normalized === "admin.device.disable") {
        return "设备停用";
    }
    if (normalized === "admin.device.enable") {
        return "设备启用";
    }
    if (normalized === "admin.device.update") {
        return "设备更新";
    }
    return action || "未知操作";
}

export function formatOnlineWindowLabel(onlineWindowSeconds: number): string {
    if (onlineWindowSeconds < 60) {
        return `${onlineWindowSeconds} 秒`;
    }
    return `${Math.round(onlineWindowSeconds / 60)} 分钟`;
}

export function normalizeStringValue(value: unknown): string | null {
    if (typeof value !== "string") {
        return null;
    }
    const trimmed = value.trim();
    return trimmed.length > 0 ? trimmed : null;
}

export function normalizeStringArray(value: unknown): string[] {
    if (!Array.isArray(value)) {
        return [];
    }
    return value.map((item) => normalizeStringValue(item)).filter((item): item is string => item !== null);
}

export function formatAuditMetadataValue(value: unknown): string | null {
    if (value === null || value === undefined) {
        return null;
    }
    if (typeof value === "string") {
        return value.trim() ? value.trim() : null;
    }
    if (typeof value === "number" || typeof value === "boolean") {
        return String(value);
    }
    if (Array.isArray(value)) {
        const items = value
            .map((item) => formatAuditMetadataValue(item))
            .filter((item): item is string => item !== null);
        return items.length > 0 ? items.join(", ") : null;
    }
    if (typeof value === "object") {
        try {
            return JSON.stringify(value);
        } catch {
            return null;
        }
    }
    return null;
}

export function toCnMetadataLabel(key: string): string {
    const mapping: Record<string, string> = {
        display_name: "显示名称",
        initial_key_id: "首钥 Key ID",
        initial_key_algorithm: "首钥算法",
        key_id: "Key ID",
        algorithm: "算法",
        reason: "原因",
        retired_key_ids: "退役 Key",
        ip: "来源 IP",
        user_agent: "设备标识",
        source: "来源",
        operator: "操作人",
    };
    return mapping[key] || key;
}

export function summarizeAuditMetadata(item: ManagedDeviceAudit): string[] {
    const action = item.action.trim().toLowerCase();
    const metadata = item.metadata ?? {};
    const displayName = normalizeStringValue(metadata.display_name);
    const initialKeyId = normalizeStringValue(metadata.initial_key_id);
    const initialKeyAlgorithm = normalizeStringValue(metadata.initial_key_algorithm);
    const keyId = normalizeStringValue(metadata.key_id);
    const algorithm = normalizeStringValue(metadata.algorithm);
    const reason = normalizeStringValue(metadata.reason);
    const retiredKeyIds = normalizeStringArray(metadata.retired_key_ids);
    const knownKeys = new Set([
        "display_name",
        "initial_key_id",
        "initial_key_algorithm",
        "key_id",
        "algorithm",
        "reason",
        "retired_key_ids",
    ]);
    const extraEntries = Object.entries(metadata)
        .filter(([key]) => !knownKeys.has(key))
        .map(([key, value]) => {
            const formatted = formatAuditMetadataValue(value);
            return formatted ? `${toCnMetadataLabel(key)}：${formatted}` : null;
        })
        .filter((line): line is string => line !== null);

    if (action === "admin.device.register") {
        return [
            displayName ? `显示名称：${displayName}` : "显示名称：未设置",
            initialKeyId ? `首钥 Key ID：${initialKeyId}` : "首钥：未创建",
            initialKeyAlgorithm ? `首钥算法：${initialKeyAlgorithm}` : "首钥算法：—",
            ...extraEntries,
        ];
    }

    if (action === "admin.device.key.rotate") {
        return [
            keyId ? `新 Key ID：${keyId}` : "新 Key ID：—",
            algorithm ? `算法：${algorithm}` : "算法：—",
            `退役 Key 数：${retiredKeyIds.length}`,
            ...(retiredKeyIds.length > 0 ? [`退役 Key：${retiredKeyIds.join(", ")}`] : []),
            ...extraEntries,
        ];
    }

    if (action === "admin.device.disable") {
        return [
            reason ? `停用原因：${reason}` : "停用原因：未填写",
            `退役 Key 数：${retiredKeyIds.length}`,
            ...(retiredKeyIds.length > 0 ? [`退役 Key：${retiredKeyIds.join(", ")}`] : []),
            ...extraEntries,
        ];
    }

    if (extraEntries.length > 0) {
        return extraEntries;
    }

    return ["暂无可展示的元数据摘要。"];
}
