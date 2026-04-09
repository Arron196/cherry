export const TRANSLATIONS = {
    // 告警等级
    critical: "严重",
    high: "高",
    medium: "中",
    low: "低",

    // 告警状态
    open: "待处理",
    acknowledged: "处理中",
    resolved: "已解决",

    // 告警类型
    temperature_spike: "温度突增",
    humidity_deviation: "湿度异常",
    vibration_alert: "震动告警",
    quality_degraded: "品质下降",
    route_deviation: "路线偏离",

    // 任务 / 请求状态
    RECEIVED: "已接收",
    ANCHORING: "锚定中",
    ANCHORED: "已完成",
    FAILED_RETRYING: "重试中",
    DEAD_LETTER: "死信队列",

    // 设备状态
    active: "在线",
    disabled: "禁用",
    inactive: "离线",

    // 追踪阶段
    harvest: "采摘",
    processing: "加工",
    transport: "运输",
    storage: "仓储",
    retail: "零售",
};

export function t(key: string | undefined | null): string {
    if (!key) return "";
    return (TRANSLATIONS as Record<string, string>)[key] || key;
}
