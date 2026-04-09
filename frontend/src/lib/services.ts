import { api } from "./api";
import {
    ActivatePolicyResponse,
    CanonicalBatchStagesResponse,
    CanonicalPublicTraceResponse,
    ContractValidateResponse,
    HealthResponse,
    IngestEventResponse,
    PaginatedResponse,
    QualityGradeRequest,
    QualityGradeResponse,
    TraceBatch,
    TraceEventContractPayload,
    TraceEvent,
    Alert,
    BatchQueryParams,
    EventQueryParams,
    TraceTimeline,
    AdminTask,
    AnchoringTaskQueryParams,
    LoginResponse,
    ManagedDevice,
    ManagedDeviceAudit,
    ManagedDeviceDetail,
    ManagedDeviceKey,
    RegisterDeviceResponse,
    RotateDeviceKeyResponse,
    SimulationBatchResponse,
    SimulationGeneratorRequest,
    SimulationGeneratorStatusResponse,
    SimulationTickResponse,
    DisableDeviceResponse,
    DeviceStatusFilter,
    DashboardStatsResponse,
    StatsOverview,
    TemperatureTrendPoint,
    QualityDistribution,
    StageDistribution,
    RecentEvent,
} from "@/types/api";
import {
    adaptDashboardStats,
    adaptBatchStages,
    adaptPublicTrace,
    assertArrayContract,
} from "@/lib/contract-adapters";

type ManagedDeviceListResponse =
    | PaginatedResponse<ManagedDevice>
    | ManagedDevice[]
    | { items: ManagedDevice[] }
    | { devices: ManagedDevice[] };

type ManagedDevicePage = PaginatedResponse<ManagedDevice>;

type StatsQueryParams = {
    include_simulation?: boolean;
};

type SimulationScopeQueryParams = {
    include_simulation?: boolean;
};

type ManagedDeviceKeysResponse =
    | ManagedDeviceKey[]
    | { items: ManagedDeviceKey[] }
    | { keys: ManagedDeviceKey[] };

type ManagedDeviceKeysListEnvelope = {
    device_id: string;
    items: ManagedDeviceKey[];
};

type ManagedDeviceAuditListEnvelope = {
    device_id: string;
    items: ManagedDeviceAudit[];
};

function normalizeManagedDevices(payload: ManagedDeviceListResponse): ManagedDevice[] {
    if (Array.isArray(payload)) {
        return payload;
    }
    if ("items" in payload && Array.isArray(payload.items)) {
        return payload.items;
    }
    if ("devices" in payload && Array.isArray(payload.devices)) {
        return payload.devices;
    }
    return [];
}

function normalizeManagedDevicesPage(
    payload: ManagedDeviceListResponse,
    fallback: { limit: number; offset: number }
): ManagedDevicePage {
    if (Array.isArray(payload)) {
        return {
            total: payload.length,
            limit: fallback.limit,
            offset: fallback.offset,
            items: payload,
        };
    }

    if (
        "total" in payload
        && typeof payload.total === "number"
        && "limit" in payload
        && typeof payload.limit === "number"
        && "offset" in payload
        && typeof payload.offset === "number"
        && "items" in payload
        && Array.isArray(payload.items)
    ) {
        return payload as ManagedDevicePage;
    }

    const items = normalizeManagedDevices(payload);
    return {
        total: items.length,
        limit: fallback.limit,
        offset: fallback.offset,
        items,
    };
}

function normalizeManagedDeviceKeys(payload: ManagedDeviceKeysResponse): ManagedDeviceKey[] {
    if (Array.isArray(payload)) {
        return payload;
    }
    if ("items" in payload && Array.isArray(payload.items)) {
        return payload.items;
    }
    if ("keys" in payload && Array.isArray(payload.keys)) {
        return payload.keys;
    }
    return [];
}

function normalizeManagedDeviceKeysEnvelope(
    payload: ManagedDeviceKeysResponse | ManagedDeviceKeysListEnvelope
): ManagedDeviceKey[] {
    if (
        typeof payload === "object"
        && payload !== null
        && "device_id" in payload
        && "items" in payload
        && Array.isArray(payload.items)
    ) {
        return payload.items;
    }
    return normalizeManagedDeviceKeys(payload as ManagedDeviceKeysResponse);
}

export const Services = {
    login: async (params: { username: string; password: string }) => {
        const { data } = await api.post<LoginResponse>("/v1/auth/login", params);
        return data;
    },

    // Batch
    getBatches: async (params: BatchQueryParams) => {
        const { data } = await api.get<PaginatedResponse<TraceBatch>>("/v1/batches", {
            params,
        });
        return data;
    },

    // Trace
    getTrace: async (batchId: string) => {
        const { data } = await api.get<TraceTimeline>(`/v1/trace/${batchId}`);
        return data;
    },

    // Events
    getEvents: async (params: EventQueryParams) => {
        const { data } = await api.get<PaginatedResponse<TraceEvent>>("/v1/events", {
            params,
        });
        return data;
    },

    ingestEvent: async (params: { payload: TraceEventContractPayload; idempotencyKey: string }) => {
        const { data } = await api.post<IngestEventResponse>("/v1/events", params.payload, {
            headers: {
                "Idempotency-Key": params.idempotencyKey,
            },
        });
        return data;
    },

    seedSimulationBatch: async (batchId: string) => {
        const { data } = await api.post<SimulationBatchResponse>(
            `/v1/simulation/batches/${encodeURIComponent(batchId)}`
        );
        return data;
    },

    getSimulationGeneratorStatus: async () => {
        const { data } = await api.get<SimulationGeneratorStatusResponse>("/v1/simulation/generator");
        return data;
    },

    startSimulationGenerator: async (params?: SimulationGeneratorRequest) => {
        const { data } = await api.post<SimulationGeneratorStatusResponse>(
            "/v1/simulation/generator/start",
            params ?? {}
        );
        return data;
    },

    stopSimulationGenerator: async () => {
        const { data } = await api.post<SimulationGeneratorStatusResponse>(
            "/v1/simulation/generator/stop"
        );
        return data;
    },

    tickSimulationGenerator: async (params?: Pick<SimulationGeneratorRequest, "batches_per_tick">) => {
        const { data } = await api.post<SimulationTickResponse>(
            "/v1/simulation/generator/tick",
            params ?? {}
        );
        return data;
    },

    validateTraceEventContract: async (payload: TraceEventContractPayload) => {
        const { data } = await api.post<ContractValidateResponse>("/contracts/trace-events/validate", payload);
        return data;
    },

    gradeQuality: async (params: QualityGradeRequest) => {
        const { data } = await api.post<QualityGradeResponse>("/v1/quality/grade", params);
        return data;
    },

    getHealth: async () => {
        const { data } = await api.get<HealthResponse>("/health");
        return data;
    },

    // Alerts
    getAlerts: async (params: { limit?: number; offset?: number } & SimulationScopeQueryParams) => {
        const { data } = await api.get<{ alerts: Alert[]; total: number }>(
            "/v1/alerts",
            { params }
        );
        return data;
    },

    ackAlert: async (alertId: number) => {
        const { data } = await api.post(`/v1/alerts/${alertId}/ack`);
        return data;
    },

    resolveAlert: async (alertId: number) => {
        const { data } = await api.post(`/v1/alerts/${alertId}/resolve`);
        return data;
    },

    escalateAlert: async (alertId: number) => {
        const { data } = await api.post(`/v1/alerts/${alertId}/escalate`);
        return data;
    },

    // Admin - Anchoring
    getAnchoringTasks: async (params: AnchoringTaskQueryParams) => {
        const { data } = await api.get<PaginatedResponse<AdminTask>>("/admin/anchoring/tasks", { params });
        return data;
    },

    requeueAnchoringTask: async (ingestRequestId: number) => {
        const { data } = await api.post<{ ingest_request_id: number; status: string; retry_count: number; audit_id: number }>(
            `/admin/anchoring/tasks/${ingestRequestId}/requeue`
        );
        return data;
    },

    runAnchoringOnce: async (params?: { limit?: number }) => {
        const { data } = await api.post<{ processed: number; limit: number; audit_id: number }>(
            "/admin/anchoring/run-once",
            params ?? {}
        );
        return data;
    },

    activatePolicy: async (policyId: string) => {
        const { data } = await api.post<ActivatePolicyResponse>(`/admin/policies/${encodeURIComponent(policyId)}/activate`);
        return data;
    },

    // Admin - Devices
    registerDevice: async (params: {
        device_id: string;
        display_name?: string;
        initial_key?: {
            key_id: string;
            algorithm: string;
            secret: string;
        };
    }) => {
        const { data } = await api.post<RegisterDeviceResponse>("/admin/devices", params);
        return data;
    },

    getManagedDevices: async (params?: { limit?: number; offset?: number; status?: DeviceStatusFilter } & SimulationScopeQueryParams) => {
        const { data } = await api.get<ManagedDeviceListResponse>("/v1/devices", {
            params: {
                limit: params?.limit ?? 200,
                offset: params?.offset ?? 0,
                status: params?.status,
                include_simulation: params?.include_simulation,
            },
        });
        return normalizeManagedDevices(data);
    },

    getManagedDevicesPage: async (params?: { limit?: number; offset?: number; status?: DeviceStatusFilter } & SimulationScopeQueryParams) => {
        const limit = params?.limit ?? 20;
        const offset = params?.offset ?? 0;
        const { data } = await api.get<ManagedDeviceListResponse>("/v1/devices", {
            params: {
                limit,
                offset,
                status: params?.status,
                include_simulation: params?.include_simulation,
            },
        });
        return normalizeManagedDevicesPage(data, { limit, offset });
    },

    rotateDeviceKey: async (
        deviceId: string,
        params: { key_id: string; algorithm: string; public_key: string }
    ) => {
        const { data } = await api.post<RotateDeviceKeyResponse>(`/admin/devices/${deviceId}/keys`, params);
        return data;
    },

    disableManagedDevice: async (deviceId: string, params: { reason?: string }) => {
        const { data } = await api.post<DisableDeviceResponse>(`/admin/devices/${deviceId}/disable`, params);
        return data;
    },

    getManagedDeviceKeys: async (deviceId: string) => {
        const { data } = await api.get<ManagedDeviceKeysResponse | ManagedDeviceKeysListEnvelope>(`/admin/devices/${deviceId}/keys`);
        return normalizeManagedDeviceKeysEnvelope(data);
    },

    getManagedDeviceDetail: async (deviceId: string) => {
        const { data } = await api.get<ManagedDeviceDetail>(`/admin/devices/${deviceId}`);
        return data;
    },

    getManagedDeviceAudits: async (deviceId: string) => {
        const { data } = await api.get<ManagedDeviceAuditListEnvelope>(`/admin/devices/${deviceId}/audits`);
        return data.items;
    },

    // Metrics
    getMetrics: async () => {
        const { data } = await api.get<string>("/metrics");
        return data;
    },

    // Public Trace (no auth required)
    getPublicTrace: async (batchId: string) => {
        const { data } = await api.get<CanonicalPublicTraceResponse>(`/v1/public/trace/${batchId}`);
        return adaptPublicTrace(data);
    },

    // Stats
    getStatsOverview: async (params?: StatsQueryParams) => {
        const { data } = await api.get<StatsOverview>("/v1/stats/overview", {
            params,
        });
        return data;
    },

    getDashboardStats: async (params?: StatsQueryParams) => {
        const { data } = await api.get<DashboardStatsResponse>("/v1/stats/dashboard", {
            params,
        });
        return adaptDashboardStats(data);
    },

    getTemperatureTrend: async (params?: StatsQueryParams) => {
        const { data } = await api.get<TemperatureTrendPoint[]>("/v1/stats/temperature-trend", {
            params,
        });
        return assertArrayContract<TemperatureTrendPoint>(data, "GET /v1/stats/temperature-trend");
    },

    getQualityDistribution: async (params?: StatsQueryParams) => {
        const { data } = await api.get<QualityDistribution[]>("/v1/stats/quality-distribution", {
            params,
        });
        return assertArrayContract<QualityDistribution>(data, "GET /v1/stats/quality-distribution");
    },

    getStageDistribution: async (params?: StatsQueryParams) => {
        const { data } = await api.get<StageDistribution[]>("/v1/stats/stage-distribution", {
            params,
        });
        return assertArrayContract<StageDistribution>(data, "GET /v1/stats/stage-distribution");
    },

    getRecentEvents: async (limit: number = 10, params?: StatsQueryParams) => {
        try {
            const { data } = await api.get<RecentEvent[]>("/v1/events/recent", {
                params: { limit, ...params },
            });
            return assertArrayContract<RecentEvent>(data, "GET /v1/events/recent");
        } catch (error: unknown) {
            const status = (error as { response?: { status?: number } }).response?.status;
            if (status !== 404 && status !== 410) {
                throw error;
            }
        }

        const { data } = await api.get<PaginatedResponse<TraceEvent>>("/v1/events", {
            params: { limit, offset: 0 },
        });
        return assertArrayContract<RecentEvent>(
            data.items,
            "GET /v1/events (recent fallback)"
        );
    },

    getBatchStages: async (batchId: string) => {
        const { data } = await api.get<CanonicalBatchStagesResponse>(`/v1/batches/${batchId}/stages`);
        return adaptBatchStages(data);
    },

    getBatchSensorHistory: async (batchId: string) => {
        const { data } = await api.get<import("@/types/api").SensorDataPoint[]>(`/v1/batches/${batchId}/sensors`);
        return assertArrayContract<import("@/types/api").SensorDataPoint>(
            data,
            "GET /v1/batches/{batch_id}/sensors"
        );
    },

    getBatchEvents: async (batchId: string) => {
        const { data } = await api.get<PaginatedResponse<TraceEvent>>("/v1/events", {
            params: { batch_id: batchId, limit: 100 },
        });
        return data;
    },

    api: api // Exporting raw api for edge cases
};
