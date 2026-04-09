import MockAdapter from "axios-mock-adapter";
import axios from "axios";

// Determine delay for realistic network feel
const mockInstance = axios.create();
const mock = new MockAdapter(mockInstance, { delayResponse: 500 });

type MockDevice = {
    device_id: string;
    name: string;
    display_name: string;
    status: "active" | "disabled";
    last_seen_at: string | null;
    created_at: string;
};

type MockDeviceKey = {
    key_id: string;
    algorithm: string;
    status: "active" | "retired";
    activated_at: string;
    retired_at: string | null;
};

type MockAlert = {
    id: number;
    event_id: number;
    alert_type: string;
    severity: "low" | "medium" | "high" | "critical";
    status: "open" | "acknowledged" | "resolved";
    message: string;
    raised_at: string;
    resolved_at: string | null;
};

type MockAnchoringTask = {
    ingest_request_id: number;
    event_id?: number;
    batch_id?: string;
    device_id?: string;
    status: "RECEIVED" | "ANCHORING" | "ANCHORED" | "FAILED_RETRYING" | "DEAD_LETTER";
    retry_count: number;
    last_error?: string;
    created_at: string;
};

const BATCH_ID_SEGMENT_PATTERN = "[^/?#]+";

const parseJsonData = <T>(data: unknown, fallback: T): T => {
    if (typeof data !== "string" || data.trim() === "") {
        return fallback;
    }
    try {
        return JSON.parse(data) as T;
    } catch {
        return fallback;
    }
};

const readNumberParam = (value: unknown, fallback: number) => {
    const parsed = Number(value);
    return Number.isFinite(parsed) && parsed >= 0 ? parsed : fallback;
};

const paginate = <T>(items: T[], params: Record<string, unknown> | undefined, defaultLimit = 20) => {
    const limit = readNumberParam(params?.limit, defaultLimit);
    const offset = readNumberParam(params?.offset, 0);
    return {
        total: items.length,
        limit,
        offset,
        items: items.slice(offset, offset + limit),
    };
};

const problem = (status: number, detail: string, instance = "") => ({
    type: "about:blank",
    title: status === 404 ? "Not Found" : "Mock Error",
    status,
    detail,
    instance,
});

const simpleHash = (value: unknown) => {
    const input = JSON.stringify(value);
    let hash = 0;
    for (let index = 0; index < input.length; index += 1) {
        hash = Math.imul(31, hash) + input.charCodeAt(index) | 0;
    }
    return `mock-${Math.abs(hash).toString(16).padStart(8, "0")}`;
};

const stableHexDigest = (value: unknown, length = 64) => {
    const input = JSON.stringify(value);
    let seedA = 0x811c9dc5;
    let seedB = 0x9e3779b9;

    for (let index = 0; index < input.length; index += 1) {
        const code = input.charCodeAt(index);
        seedA = Math.imul(seedA ^ code, 0x01000193);
        seedB = Math.imul(seedB + code + index, 0x85ebca6b);
        seedB ^= seedB >>> 13;
    }

    let output = "";
    while (output.length < length) {
        seedA = Math.imul(seedA ^ (seedA >>> 16), 0x85ebca6b);
        seedB = Math.imul(seedB ^ (seedB >>> 13), 0xc2b2ae35);
        output += ((seedA ^ seedB) >>> 0).toString(16).padStart(8, "0");
    }

    return output.slice(0, length);
};

const mockTransactionHash = (value: unknown) => `0x${stableHexDigest(value, 64)}`;

const readBatchIdFromUrl = (url: string | undefined, pattern: RegExp, fallback = "batch-sim-1000") => {
    const rawId = (url || "").match(pattern)?.[1];
    return rawId ? decodeURIComponent(rawId) : fallback;
};

// ── Mock Data Generators ──────────────────────────────────────

const generateMockBatches = () => {
    return Array.from({ length: 15 }).map((_, i) => ({
        batch_id: `batch-sim-${1000 + i}`,
        device_id: `dev-sim-${(i % 3) + 1}`,
        event_count: Math.floor(Math.random() * 50) + 10,
        start_time: new Date(Date.now() - i * 86400000).toISOString(),
        end_time: i > 2 ? new Date(Date.now() - (i - 1) * 86400000).toISOString() : null,
    }));
};

const generateMockEvents = () => {
    return Array.from({ length: 20 }).map((_, i) => ({
        id: 10000 + i,
        batch_id: `batch-sim-1000`,
        device_id: `dev-sim-1`,
        timestamp: new Date(Date.now() - i * 3600000).toISOString(),
        ingest_status: i === 0 ? "ANCHORING" : "ANCHORED",
    }));
};

const generateMockAlerts = (): MockAlert[] => {
    return Array.from({ length: 5 }).map((_, i) => ({
        id: 500 + i,
        event_id: 10000 + i,
        alert_type: "temperature_spike",
        severity: i === 0 ? "critical" : "medium",
        status: i < 2 ? "open" : "resolved",
        message: "模拟异常：温度超过预设阈值",
        raised_at: new Date(Date.now() - i * 3600000).toISOString(),
        resolved_at: i >= 2 ? new Date(Date.now() - (i - 1) * 3600000).toISOString() : null,
    }));
};

const mockAlertStore = new Map<number, MockAlert>(generateMockAlerts().map((alert) => [alert.id, alert]));

const getMockAlerts = () => Array.from(mockAlertStore.values()).sort((left, right) => right.id - left.id);

const getMockDeviceLastSeenAt = (index: number) => {
    if (index === 3) {
        return new Date(Date.now() - 86400000 * 5).toISOString();
    }
    return new Date(Date.now() - index * 45000).toISOString();
};

const generateInitialMockDevices = (): MockDevice[] => [
    {
        device_id: "dev-sim-1",
        name: "采摘端温湿度节点",
        display_name: "采摘端温湿度节点",
        status: "active",
        last_seen_at: getMockDeviceLastSeenAt(1),
        created_at: "2024-01-01T00:00:00Z",
    },
    {
        device_id: "dev-sim-2",
        name: "冷链车厢网关",
        display_name: "冷链车厢网关",
        status: "active",
        last_seen_at: getMockDeviceLastSeenAt(2),
        created_at: "2024-01-02T00:00:00Z",
    },
    {
        device_id: "dev-sim-3",
        name: "仓储环境采集器",
        display_name: "仓储环境采集器",
        status: "disabled",
        last_seen_at: getMockDeviceLastSeenAt(3),
        created_at: "2024-01-03T00:00:00Z",
    },
];

const mockDeviceStore = new Map<string, MockDevice>(generateInitialMockDevices().map((device) => [device.device_id, device]));
const mockDeviceKeyStore = new Map<string, MockDeviceKey[]>();

const generateInitialMockDeviceKeys = (deviceId: string): MockDeviceKey[] => [
    {
        key_id: `${deviceId}-key-active`,
        algorithm: "HMAC_SHA256",
        status: "active",
        activated_at: new Date(Date.now() - 86400000 * 2).toISOString(),
        retired_at: null,
    },
    {
        key_id: `${deviceId}-key-retired`,
        algorithm: "HMAC_SHA256",
        status: "retired",
        activated_at: new Date(Date.now() - 86400000 * 14).toISOString(),
        retired_at: new Date(Date.now() - 86400000 * 2).toISOString(),
    },
];

const getMockDeviceKeys = (deviceId: string) => {
    const existing = mockDeviceKeyStore.get(deviceId);
    if (existing) {
        return existing;
    }

    const initialKeys = generateInitialMockDeviceKeys(deviceId);
    mockDeviceKeyStore.set(deviceId, initialKeys);
    return initialKeys;
};

const getMockDevices = () => Array.from(mockDeviceStore.values());

const generateMockDeviceAudits = (deviceId: string) => [
    {
        audit_id: 9001,
        actor: "simulation",
        action: "admin.device.register",
        target: `device:${deviceId}`,
        metadata: {
            display_name: mockDeviceStore.get(deviceId)?.name,
            initial_key_id: `${deviceId}-key-retired`,
            initial_key_algorithm: "HMAC_SHA256",
            source: "simulation",
        },
        created_at: new Date(Date.now() - 86400000 * 14).toISOString(),
    },
    {
        audit_id: 9002,
        actor: "simulation",
        action: "admin.device.key.rotate",
        target: `device:${deviceId}`,
        metadata: {
            key_id: `${deviceId}-key-active`,
            algorithm: "HMAC_SHA256",
            retired_key_ids: [`${deviceId}-key-retired`],
            source: "simulation",
        },
        created_at: new Date(Date.now() - 86400000 * 2).toISOString(),
    },
];

const nextMockAuditId = () => Math.floor(Date.now() / 1000);

const mockAnchoringTasks: MockAnchoringTask[] = [
    {
        ingest_request_id: 9999,
        event_id: 10000,
        batch_id: "batch-sim-1000",
        device_id: "dev-sim-1",
        status: "RECEIVED",
        retry_count: 0,
        created_at: new Date(Date.now() - 600000).toISOString(),
    },
    {
        ingest_request_id: 10001,
        event_id: 10001,
        batch_id: "batch-sim-1001",
        device_id: "dev-sim-2",
        status: "FAILED_RETRYING",
        retry_count: 2,
        last_error: "模拟：链上确认超时，等待重试。",
        created_at: new Date(Date.now() - 1800000).toISOString(),
    },
    {
        ingest_request_id: 10002,
        event_id: 10002,
        batch_id: "batch-sim-1002",
        device_id: "dev-sim-3",
        status: "DEAD_LETTER",
        retry_count: 5,
        last_error: "模拟：超过最大重试次数。",
        created_at: new Date(Date.now() - 3600000).toISOString(),
    },
];

const getMockPublicTrace = (batchId: string) => {
    const timeline = Array.from({ length: 8 }).map((_, index) => {
        const stage = index < 2 ? "harvest" : index < 4 ? "storage" : index < 7 ? "transport" : "retail";
        return {
            event_id: 12000 + index,
            timestamp: new Date(Date.now() - (8 - index) * 3600000).toISOString(),
            device_id: `dev-sim-${(index % 3) + 1}`,
            supply_chain_stage: stage,
            sensor_data: {
                temperature_c: Number((4 + Math.random() * 2).toFixed(1)),
                humidity_pct: Number((72 + Math.random() * 6).toFixed(1)),
                co2_ppm: Math.round(410 + Math.random() * 40),
                vibration_g: Number((0.02 + Math.random() * 0.05).toFixed(3)),
            },
        };
    });

    return {
        batch_info: {
            batch_id: batchId,
            total_events: timeline.length,
            first_event_at: timeline[0]?.timestamp,
            last_event_at: timeline.at(-1)?.timestamp,
        },
        timeline,
        stage_environments: [
            {
                stage: "harvest",
                event_count: 2,
                avg_temperature_c: 5.1,
                avg_humidity_pct: 76.2,
                avg_co2_ppm: 420,
                avg_vibration_g: 0.03,
                start_time: timeline[0]?.timestamp,
                end_time: timeline[1]?.timestamp,
            },
            {
                stage: "storage",
                event_count: 2,
                avg_temperature_c: 4.3,
                avg_humidity_pct: 74.8,
                avg_co2_ppm: 430,
                avg_vibration_g: 0.02,
                start_time: timeline[2]?.timestamp,
                end_time: timeline[3]?.timestamp,
            },
            {
                stage: "transport",
                event_count: 3,
                avg_temperature_c: 5.6,
                avg_humidity_pct: 73.1,
                avg_co2_ppm: 445,
                avg_vibration_g: 0.06,
                start_time: timeline[4]?.timestamp,
                end_time: timeline[6]?.timestamp,
            },
            {
                stage: "retail",
                event_count: 1,
                avg_temperature_c: 6.2,
                avg_humidity_pct: 71.9,
                avg_co2_ppm: 438,
                avg_vibration_g: 0.04,
                start_time: timeline[7]?.timestamp,
                end_time: undefined,
            },
        ],
        quality: {
            grade: "A",
            score: 94.2,
            max_score: 100,
        },
        blockchain_anchor: {
            is_anchored: true,
            anchored_count: timeline.length,
            total_events: timeline.length,
            latest_transaction_hash: mockTransactionHash(batchId),
        },
    };
};

// ── Setup Routes ──────────────────────────────────────────────

// Auth
mock.onPost("/v1/auth/login").reply((config) => {
    const payload = parseJsonData<{ username?: string; password?: string }>(config.data, {});
    if (payload.username && payload.password) {
        return [200, {
            access_token: `mock-token-${payload.username}`,
            token_type: "Bearer",
            expires_in: 86400,
            role: payload.username === "regulator" ? "regulator" : "admin",
        }];
    }
    return [401, problem(401, "Mock login requires username and password.", "/v1/auth/login")];
});

// Stats Overview
mock.onGet("/v1/stats/overview").reply(200, {
    total_batches: 1420,
    total_events: 53920,
    active_devices: 24,
    avg_quality_score: 92.5,
    grade_distribution: { A: 1200, B: 200, C: 20 },
    open_alerts: 2,
});

// Dashboard Stats
let baseBatches = 1420;
let baseEvents = 53920;
let baseAlerts = 2;

mock.onGet("/v1/stats/dashboard").reply(() => {
    baseBatches += Math.floor(Math.random() * 3);
    baseEvents += Math.floor(Math.random() * 8) + 1;
    baseAlerts = Math.random() > 0.8 ? baseAlerts + 1 : Math.max(0, baseAlerts - (Math.random() > 0.5 ? 1 : 0));
    
    return [200, {
        overview: {
            total_batches: baseBatches,
            total_events: baseEvents,
            active_devices: 24 + Math.floor(Math.random() * 4) - 2,
            avg_quality_score: 92.5 + (Math.random() * 0.4 - 0.2),
            grade_distribution: { A: 1200, B: 200, C: 20 },
            open_alerts: baseAlerts,
        },
        temperature_trend: Array.from({ length: 24 }).map((_, i) => ({
            timestamp: new Date(Date.now() - (24 - i) * 3600000).toISOString(),
            avg_temperature: 4 + Math.random() * 2,
            min_temperature: 3 + Math.random(),
            max_temperature: 5 + Math.random() * 2,
        })),
        quality_distribution: [
            { grade: "A", count: 1200 + Math.floor(Math.random()*10), percentage: 84.5 },
            { grade: "B", count: 200 + Math.floor(Math.random()*5), percentage: 14.1 },
            { grade: "C", count: 20 + Math.floor(Math.random()*2), percentage: 1.4 },
        ],
        stage_distribution: [
            { stage: "harvest", count: 50 + Math.floor(Math.random()*5) },
            { stage: "processing", count: 350 + Math.floor(Math.random()*10) },
            { stage: "transport", count: 800 + Math.floor(Math.random()*20) },
            { stage: "storage", count: 220 + Math.floor(Math.random()*5) },
        ],
        recent_events: generateMockEvents().slice(0, 5),
    }];
});

// Temperature Trend
mock.onGet("/v1/stats/temperature-trend").reply(200, 
    Array.from({ length: 24 }).map((_, i) => ({
        timestamp: new Date(Date.now() - (24 - i) * 3600000).toISOString(),
        avg_temperature: 4 + Math.random() * 2,
        min_temperature: 3 + Math.random(),
        max_temperature: 5 + Math.random() * 2,
    }))
);

// Quality & Stage Distribution
mock.onGet("/v1/stats/quality-distribution").reply(200, [
    { grade: "A", count: 1200, percentage: 84.5 },
    { grade: "B", count: 200, percentage: 14.1 },
    { grade: "C", count: 20, percentage: 1.4 },
]);
mock.onGet("/v1/stats/stage-distribution").reply(200, [
    { stage: "harvest", count: 50 },
    { stage: "processing", count: 350 },
    { stage: "transport", count: 800 },
    { stage: "storage", count: 220 },
]);

// Batches
mock.onGet(/\/v1\/batches(?!\/)/).reply((config) => {
    const deviceId = typeof config.params?.device_id === "string" ? config.params.device_id : "";
    const items = generateMockBatches().filter((batch) => !deviceId || batch.device_id === deviceId);
    return [200, paginate(items, config.params, 20)];
});

// Single Batch details (not actually used by trace dashboard but good to have)
mock.onGet(new RegExp(`^/v1/batches/${BATCH_ID_SEGMENT_PATTERN}$`)).reply((config) => {
    const batchId = readBatchIdFromUrl(config.url, /\/v1\/batches\/([^/]+)$/);
    return [200, {
        batch_id: batchId,
        device_id: `dev-sim-${Math.floor(Math.random() * 3) + 1}`,
        event_count: Math.floor(Math.random() * 50) + 10,
        start_time: new Date(Date.now() - 86400000).toISOString(),
        end_time: Math.random() > 0.5 ? new Date().toISOString() : null,
    }];
});

// Single Batch tracing data
mock.onGet(new RegExp(`^/v1/trace/${BATCH_ID_SEGMENT_PATTERN}$`)).reply((config) => {
    const batchId = readBatchIdFromUrl(config.url, /\/v1\/trace\/([^/]+)$/);
    return [200, {
        batch_id: batchId,
        device_id: `dev-sim-1`,
        timeline_order: "oldest_first",
        status: "in_transit",
        quality_grade: "A",
        score: 95.5,
        created_at: new Date(Date.now() - 86400000).toISOString(),
        updated_at: new Date().toISOString(),
        timeline: generateMockEvents().map((e, index) => ({
            event_id: e.id,
            batch_id: batchId,
            ingest_status: e.ingest_status,
            timestamp: new Date(Date.now() - (20 - index) * 3600000).toISOString(),
            quality_grade: index % 5 === 0 ? "B" : "A",
            anchor: e.ingest_status === "ANCHORED"
                ? {
                    status: "ANCHORED",
                    transaction_hash: mockTransactionHash(`${batchId}-${e.id}`),
                }
                : undefined,
            alert_snapshot: index === 3
                ? {
                    total: 1,
                    open: 1,
                    high_open: 1,
                }
                : undefined,
        }))
    }];
});

// Single Batch stages
mock.onGet(new RegExp(`^/v1/batches/${BATCH_ID_SEGMENT_PATTERN}/stages$`)).reply((config) => {
    const batchId = readBatchIdFromUrl(config.url, /\/v1\/batches\/([^/]+)\/stages$/);
    
    return [200, {
        batch_id: batchId,
        stages: [
            {
                stage: "harvest",
                event_count: 5,
                start_time: new Date(Date.now() - 86400000).toISOString(),
                end_time: new Date(Date.now() - 43200000).toISOString(),
                events: []
            },
            {
                stage: "storage",
                event_count: 2,
                start_time: new Date(Date.now() - 43200000).toISOString(),
                end_time: new Date(Date.now() - 21600000).toISOString(),
                events: []
            },
            {
                stage: "transport",
                event_count: 12,
                start_time: new Date(Date.now() - 21600000).toISOString(),
                end_time: null,
                events: []
            }
        ]
    }];
});

// Single Batch sensors
mock.onGet(new RegExp(`^/v1/batches/${BATCH_ID_SEGMENT_PATTERN}/sensors$`)).reply(200, Array.from({ length: 20 }).map((_, i) => ({
    timestamp: new Date(Date.now() - (20 - i) * 3600000).toISOString(),
    temperature_c: 4 + Math.random() * 2,
    humidity_pct: 85 + Math.random() * 5,
    co2_ppm: 400 + Math.random() * 50,
    vibration_g: Number((0.02 + Math.random() * 0.08).toFixed(3)),
})));

// Events
mock.onGet(/\/v1\/events(?!\/)/).reply((config) => {
    const batchId = typeof config.params?.batch_id === "string" ? config.params.batch_id : "";
    const deviceId = typeof config.params?.device_id === "string" ? config.params.device_id : "";
    const ingestStatus = typeof config.params?.ingest_status === "string" ? config.params.ingest_status : "";
    const items = generateMockEvents().filter((event) => {
        return (!batchId || event.batch_id === batchId)
            && (!deviceId || event.device_id === deviceId)
            && (!ingestStatus || event.ingest_status === ingestStatus);
    });
    return [200, paginate(items, config.params, 20)];
});

// Recent Events
mock.onGet("/v1/events/recent").reply(200, generateMockEvents().slice(0, 5));

// Public trace
mock.onGet(new RegExp(`^/v1/public/trace/.+$`)).reply((config) => {
    const batchId = decodeURIComponent((config.url || "").match(/\/v1\/public\/trace\/(.+)$/)?.[1] || "batch-sim-1000");
    return [200, getMockPublicTrace(batchId)];
});

// Metrics
mock.onGet("/metrics").reply(200, [
    "# HELP traceability_mock_requests_total Total mock requests.",
    "# TYPE traceability_mock_requests_total counter",
    "traceability_mock_requests_total{mode=\"simulation\"} 42",
    "# HELP traceability_mock_frontend_info Mock frontend info.",
    "# TYPE traceability_mock_frontend_info gauge",
    "traceability_mock_frontend_info 1",
].join("\n"));

// Alerts
mock.onGet("/v1/alerts").reply((config) => {
    const page = paginate(getMockAlerts(), config.params, 50);
    return [200, {
        total: page.total,
        alerts: page.items,
    }];
});

mock.onPost(new RegExp(`^/v1/alerts/\\d+/ack$`)).reply((config) => {
    const alertId = Number((config.url || "").match(/\/v1\/alerts\/(\d+)\/ack$/)?.[1]);
    const alert = mockAlertStore.get(alertId);
    if (!alert) {
        return [404, problem(404, "Mock alert was not found.", config.url)];
    }
    const updated: MockAlert = { ...alert, status: "acknowledged" };
    mockAlertStore.set(alertId, updated);
    return [200, updated];
});

// API tools
mock.onGet("/health").reply(200, { status: "ok" });

mock.onPost("/contracts/trace-events/validate").reply((config) => {
    const payload = parseJsonData<Record<string, unknown>>(config.data, {});
    return [200, {
        status: "valid",
        canonical_hash: simpleHash(payload),
    }];
});

mock.onPost("/v1/quality/grade").reply((config) => {
    const payload = parseJsonData<{ temperature_c?: number; humidity_pct?: number }>(config.data, {});
    const temperature = Number(payload.temperature_c ?? 0);
    const humidity = Number(payload.humidity_pct ?? 0);
    const tempPenalty = Math.abs(temperature - 4) * 4;
    const humidityPenalty = Math.abs(humidity - 75) * 0.4;
    const score = Math.max(0, Math.min(100, 100 - tempPenalty - humidityPenalty));
    const grade = score >= 90 ? "A" : score >= 75 ? "B" : "C";

    return [200, {
        grade,
        score: Number(score.toFixed(1)),
        max_score: 100,
        reasons: grade === "A"
            ? ["温湿度处于仿真最优区间。"]
            : ["温度或湿度偏离仿真最佳区间。"],
        threshold_context: {
            ideal_temperature_c: 4,
            ideal_humidity_pct: 75,
            source: "simulation",
        },
    }];
});

mock.onPost(new RegExp(`^/admin/policies/.+/activate$`)).reply((config) => {
    const policyId = decodeURIComponent((config.url || "").match(/\/admin\/policies\/(.+)\/activate$/)?.[1] || "policy-sim");
    return [200, {
        policy_id: policyId,
        status: "activated",
        audit_id: nextMockAuditId(),
    }];
});

mock.onPost(new RegExp(`^/v1/alerts/\\d+/resolve$`)).reply((config) => {
    const alertId = Number((config.url || "").match(/\/v1\/alerts\/(\d+)\/resolve$/)?.[1]);
    const alert = mockAlertStore.get(alertId);
    if (!alert) {
        return [404, problem(404, "Mock alert was not found.", config.url)];
    }
    const updated: MockAlert = { ...alert, status: "resolved", resolved_at: new Date().toISOString() };
    mockAlertStore.set(alertId, updated);
    return [200, updated];
});

mock.onPost(new RegExp(`^/v1/alerts/\\d+/escalate$`)).reply((config) => {
    const alertId = Number((config.url || "").match(/\/v1\/alerts\/(\d+)\/escalate$/)?.[1]);
    const alert = mockAlertStore.get(alertId);
    if (!alert) {
        return [404, problem(404, "Mock alert was not found.", config.url)];
    }
    const nextSeverity = alert.severity === "low" ? "medium" : alert.severity === "medium" ? "high" : "critical";
    const updated: MockAlert = { ...alert, severity: nextSeverity };
    mockAlertStore.set(alertId, updated);
    return [200, updated];
});

// Devices
mock.onGet("/v1/devices").reply(config => {
    const status = typeof config.params?.status === "string" ? config.params.status : "";
    const devices = getMockDevices().filter((device) => !status || device.status === status);
    return [200, paginate(devices, config.params, 200)];
});

mock.onGet(new RegExp(`^/admin/devices/dev-sim-\\d+$`)).reply((config) => {
    const url = config.url || "";
    const match = url.match(/\/admin\/devices\/(dev-sim-\d+)$/);
    const deviceId = match ? match[1] : "dev-sim-1";
    const device = mockDeviceStore.get(deviceId);

    if (!device) {
        return [404, {
            status: 404,
            title: "Not Found",
            detail: "Mock device was not found.",
        }];
    }

    const keys = getMockDeviceKeys(deviceId);
    const activeKey = keys.find((key) => key.status === "active")!;
    return [200, {
        device_id: device.device_id,
        name: device.name,
        status: device.status,
        last_seen_at: device.last_seen_at,
        created_at: device.created_at,
        key_count: keys.length,
        active_key: activeKey,
        signature_failures_last_24h: deviceId === "dev-sim-2" ? 1 : 0,
        latest_signature_failure_reason: deviceId === "dev-sim-2" ? "模拟：最近一次上报签名延迟校验" : null,
        online_status_explanation: "仿真模式：设备状态由前端模拟数据生成，不访问真实后端。",
    }];
});

mock.onPost("/admin/devices").reply((config) => {
    const payload = parseJsonData<{
        device_id?: string;
        display_name?: string;
        initial_key?: { key_id?: string; algorithm?: string; secret?: string };
    }>(config.data, {});
    const deviceId = payload.device_id?.trim();
    if (!deviceId) {
        return [400, problem(400, "Mock device_id is required.", "/admin/devices")];
    }
    if (mockDeviceStore.has(deviceId)) {
        return [409, problem(409, "Mock device already exists.", "/admin/devices")];
    }

    const now = new Date().toISOString();
    const device: MockDevice = {
        device_id: deviceId,
        name: payload.display_name?.trim() || deviceId,
        display_name: payload.display_name?.trim() || deviceId,
        status: "active",
        last_seen_at: now,
        created_at: now,
    };
    mockDeviceStore.set(deviceId, device);

    const initialKey = payload.initial_key?.key_id?.trim()
        ? {
            key_id: payload.initial_key.key_id.trim(),
            algorithm: payload.initial_key.algorithm?.trim() || "HMAC_SHA256",
            status: "active",
            activated_at: now,
            retired_at: null,
        } satisfies MockDeviceKey
        : null;
    if (initialKey) {
        mockDeviceKeyStore.set(deviceId, [initialKey]);
    }

    return [201, {
        device_id: deviceId,
        status: "active",
        audit_id: nextMockAuditId(),
        initial_key: initialKey
            ? {
                key_id: initialKey.key_id,
                algorithm: initialKey.algorithm,
                status: initialKey.status,
            }
            : null,
    }];
});

mock.onGet(new RegExp(`^/admin/devices/(?!dev-sim-)[^/]+$`)).reply((config) => {
    const deviceId = decodeURIComponent((config.url || "").match(/\/admin\/devices\/([^/]+)$/)?.[1] || "");
    const device = mockDeviceStore.get(deviceId);
    if (!device) {
        return [404, problem(404, "Mock device was not found.", config.url)];
    }
    const keys = getMockDeviceKeys(deviceId);
    const activeKey = keys.find((key) => key.status === "active") || null;
    return [200, {
        device_id: device.device_id,
        name: device.name,
        status: device.status,
        last_seen_at: device.last_seen_at,
        created_at: device.created_at,
        key_count: keys.length,
        active_key: activeKey,
        signature_failures_last_24h: 0,
        latest_signature_failure_reason: null,
        online_status_explanation: "仿真模式：该设备由前端 mock 注册生成。",
    }];
});

mock.onGet(new RegExp(`^/admin/devices/dev-sim-\\d+/keys$`)).reply((config) => {
    const url = config.url || "";
    const match = url.match(/\/admin\/devices\/(dev-sim-\d+)\/keys$/);
    const deviceId = match ? match[1] : "dev-sim-1";
    return [200, {
        device_id: deviceId,
        items: getMockDeviceKeys(deviceId),
    }];
});

mock.onGet(new RegExp(`^/admin/devices/(?!dev-sim-)[^/]+/keys$`)).reply((config) => {
    const deviceId = decodeURIComponent((config.url || "").match(/\/admin\/devices\/([^/]+)\/keys$/)?.[1] || "");
    if (!mockDeviceStore.has(deviceId)) {
        return [404, problem(404, "Mock device was not found.", config.url)];
    }
    return [200, {
        device_id: deviceId,
        items: getMockDeviceKeys(deviceId),
    }];
});

mock.onPost(new RegExp(`^/admin/devices/dev-sim-\\d+/keys$`)).reply((config) => {
    const url = config.url || "";
    const match = url.match(/\/admin\/devices\/(dev-sim-\d+)\/keys$/);
    const deviceId = match ? match[1] : "dev-sim-1";
    const payload = typeof config.data === "string" && config.data
        ? JSON.parse(config.data) as { key_id?: string; algorithm?: string }
        : {};
    const previousKeys = getMockDeviceKeys(deviceId);
    const now = new Date().toISOString();
    const retiredKeyIds = previousKeys
        .filter((key) => key.status === "active")
        .map((key) => key.key_id);
    const nextKeys: MockDeviceKey[] = [
        {
            key_id: payload.key_id || `${deviceId}-key-rotated`,
            algorithm: payload.algorithm || "HMAC_SHA256",
            status: "active",
            activated_at: now,
            retired_at: null,
        },
        ...previousKeys.map((key) => key.status === "active"
            ? { ...key, status: "retired" as const, retired_at: now }
            : key
        ),
    ];
    mockDeviceKeyStore.set(deviceId, nextKeys);

    return [201, {
        device_id: deviceId,
        key_id: payload.key_id || `${deviceId}-key-rotated`,
        algorithm: payload.algorithm || "HMAC_SHA256",
        status: "active",
        retired_key_ids: retiredKeyIds,
        audit_id: nextMockAuditId(),
    }];
});

mock.onPost(new RegExp(`^/admin/devices/(?!dev-sim-)[^/]+/keys$`)).reply((config) => {
    const deviceId = decodeURIComponent((config.url || "").match(/\/admin\/devices\/([^/]+)\/keys$/)?.[1] || "");
    if (!mockDeviceStore.has(deviceId)) {
        return [404, problem(404, "Mock device was not found.", config.url)];
    }
    const payload = parseJsonData<{ key_id?: string; algorithm?: string }>(config.data, {});
    const keyId = payload.key_id?.trim() || `${deviceId}-key-${Date.now()}`;
    const algorithm = payload.algorithm?.trim() || "HMAC_SHA256";
    const previousKeys = getMockDeviceKeys(deviceId);
    const now = new Date().toISOString();
    const retiredKeyIds = previousKeys.filter((key) => key.status === "active").map((key) => key.key_id);
    mockDeviceKeyStore.set(deviceId, [
        {
            key_id: keyId,
            algorithm,
            status: "active",
            activated_at: now,
            retired_at: null,
        },
        ...previousKeys.map((key) => key.status === "active"
            ? { ...key, status: "retired" as const, retired_at: now }
            : key
        ),
    ]);

    return [201, {
        device_id: deviceId,
        key_id: keyId,
        algorithm,
        status: "active",
        retired_key_ids: retiredKeyIds,
        audit_id: nextMockAuditId(),
    }];
});

mock.onPost(new RegExp(`^/admin/devices/dev-sim-\\d+/disable$`)).reply((config) => {
    const url = config.url || "";
    const match = url.match(/\/admin\/devices\/(dev-sim-\d+)\/disable$/);
    const deviceId = match ? match[1] : "dev-sim-1";
    const device = mockDeviceStore.get(deviceId);
    if (!device) {
        return [404, problem(404, "Mock device was not found.", config.url)];
    }
    mockDeviceStore.set(deviceId, { ...device, status: "disabled" });
    const now = new Date().toISOString();
    const keys = getMockDeviceKeys(deviceId);
    mockDeviceKeyStore.set(deviceId, keys.map((key) => key.status === "active"
        ? { ...key, status: "retired" as const, retired_at: now }
        : key
    ));

    return [200, {
        device_id: deviceId,
        status: "disabled",
        retired_key_ids: keys.map((key) => key.key_id),
        audit_id: nextMockAuditId(),
    }];
});

mock.onPost(new RegExp(`^/admin/devices/(?!dev-sim-)[^/]+/disable$`)).reply((config) => {
    const deviceId = decodeURIComponent((config.url || "").match(/\/admin\/devices\/([^/]+)\/disable$/)?.[1] || "");
    const device = mockDeviceStore.get(deviceId);
    if (!device) {
        return [404, problem(404, "Mock device was not found.", config.url)];
    }
    mockDeviceStore.set(deviceId, { ...device, status: "disabled" });
    const now = new Date().toISOString();
    const keys = getMockDeviceKeys(deviceId);
    mockDeviceKeyStore.set(deviceId, keys.map((key) => key.status === "active"
        ? { ...key, status: "retired" as const, retired_at: now }
        : key
    ));
    return [200, {
        device_id: deviceId,
        status: "disabled",
        retired_key_ids: keys.map((key) => key.key_id),
        audit_id: nextMockAuditId(),
    }];
});

mock.onGet(new RegExp(`^/admin/devices/dev-sim-\\d+/audits$`)).reply((config) => {
    const url = config.url || "";
    const match = url.match(/\/admin\/devices\/(dev-sim-\d+)\/audits$/);
    const deviceId = match ? match[1] : "dev-sim-1";
    return [200, {
        device_id: deviceId,
        items: generateMockDeviceAudits(deviceId),
    }];
});

mock.onGet(new RegExp(`^/admin/devices/(?!dev-sim-)[^/]+/audits$`)).reply((config) => {
    const deviceId = decodeURIComponent((config.url || "").match(/\/admin\/devices\/([^/]+)\/audits$/)?.[1] || "");
    if (!mockDeviceStore.has(deviceId)) {
        return [404, problem(404, "Mock device was not found.", config.url)];
    }
    return [200, {
        device_id: deviceId,
        items: generateMockDeviceAudits(deviceId),
    }];
});

mock.onPost("/__mock/v1/events").reply((config) => {
    const payload = parseJsonData<{ device_id?: string; batch_id?: string }>(config.data, {});

    if (!payload.device_id && !payload.batch_id) {
        return [404, {
            status: 404,
            title: "Not Found",
            detail: "No simulation event route matched.",
        }];
    }

    return [202, {
        event_id: Math.floor(Date.now() / 1000),
        ingest_status: "RECEIVED",
    }];
});

// Admin Tasks
mock.onGet("/admin/anchoring/tasks").reply((config) => {
    const status = typeof config.params?.status === "string" ? config.params.status : "";
    const items = mockAnchoringTasks.filter((task) => !status || task.status === status);
    return [200, paginate(items, config.params, 20)];
});

mock.onPost(new RegExp(`^/admin/anchoring/tasks/\\d+/requeue$`)).reply((config) => {
    const taskId = Number((config.url || "").match(/\/admin\/anchoring\/tasks\/(\d+)\/requeue$/)?.[1]);
    const task = mockAnchoringTasks.find((item) => item.ingest_request_id === taskId);
    if (!task) {
        return [404, problem(404, "Mock anchoring task was not found.", config.url)];
    }
    task.status = "RECEIVED";
    task.retry_count = 0;
    delete task.last_error;
    return [200, {
        ingest_request_id: task.ingest_request_id,
        status: task.status,
        retry_count: task.retry_count,
        audit_id: nextMockAuditId(),
    }];
});

mock.onPost("/admin/anchoring/run-once").reply((config) => {
    const payload = parseJsonData<{ limit?: number }>(config.data, {});
    const limit = readNumberParam(payload.limit, 100);
    const candidates = mockAnchoringTasks.filter((task) => task.status === "RECEIVED" || task.status === "ANCHORING");
    candidates.slice(0, limit).forEach((task) => {
        task.status = "ANCHORED";
        task.retry_count = 0;
    });
    return [200, {
        processed: Math.min(candidates.length, limit),
        limit,
        audit_id: nextMockAuditId(),
    }];
});

mock.onAny().reply((config) => {
    return [501, problem(
        501,
        `Simulation mock does not implement ${String(config.method || "GET").toUpperCase()} ${config.url || ""}.`,
        config.url
    )];
});

export const mockApiAdapter = mockInstance.defaults.adapter!;
