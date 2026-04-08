import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Services } from "@/lib/services";
import { BatchQueryParams, DeviceStatusFilter, EventQueryParams } from "@/types/api";
import { useSimulationStore } from "@/hooks/use-simulation";

const SIMULATION_BATCH_PATTERN = /^batch-sim-\d+$/;

async function ensureBackendSimulationBatch(batchId: string) {
    if (SIMULATION_BATCH_PATTERN.test(batchId)) {
        try {
            await Services.seedSimulationBatch(batchId);
        } catch (error) {
            const status = typeof error === "object" && error !== null && "status" in error
                ? Number((error as { status: unknown }).status)
                : null;
            if (status !== 401 && status !== 403) {
                throw error;
            }
        }
    }
}

export const useBatches = (params: BatchQueryParams) => {
    const includeSimulation = useSimulationStore((state) => state.isSimulating);
    const scopedParams = { ...params, include_simulation: includeSimulation };
    return useQuery({
        queryKey: ["batches", scopedParams],
        queryFn: () => Services.getBatches(scopedParams),
    });
};

export const useTrace = (batchId: string) => {
    return useQuery({
        queryKey: ["trace", batchId],
        queryFn: async () => {
            await ensureBackendSimulationBatch(batchId);
            return Services.getTrace(batchId);
        },
        enabled: !!batchId,
    });
};

export const useEvents = (params: EventQueryParams) => {
    const includeSimulation = useSimulationStore((state) => state.isSimulating);
    const scopedParams = { ...params, include_simulation: includeSimulation };
    return useQuery({
        queryKey: ["events", scopedParams],
        queryFn: () => Services.getEvents(scopedParams),
    });
};

export const useAlerts = (params: { limit?: number; offset?: number }) => {
    const includeSimulation = useSimulationStore((state) => state.isSimulating);
    const scopedParams = { ...params, include_simulation: includeSimulation };
    return useQuery({
        queryKey: ["alerts", scopedParams],
        queryFn: () => Services.getAlerts(scopedParams),
        // Poll every 30s for alerts
        refetchInterval: 30000,
    });
};

export const useAlertActions = () => {
    const queryClient = useQueryClient();

    const ack = useMutation({
        mutationFn: Services.ackAlert,
        onSuccess: () => queryClient.invalidateQueries({ queryKey: ["alerts"] }),
    });

    const resolve = useMutation({
        mutationFn: Services.resolveAlert,
        onSuccess: () => queryClient.invalidateQueries({ queryKey: ["alerts"] }),
    });

    const escalate = useMutation({
        mutationFn: Services.escalateAlert,
        onSuccess: () => queryClient.invalidateQueries({ queryKey: ["alerts"] }),
    });

    return { ack, resolve, escalate };
};

export const useMetrics = () => {
    return useQuery({
        queryKey: ["metrics"],
        queryFn: Services.getMetrics,
        refetchInterval: 60000,
    });
};

export const useManagedDevices = (params?: { limit?: number; offset?: number; status?: DeviceStatusFilter }) => {
    const includeSimulation = useSimulationStore((state) => state.isSimulating);
    const scopedParams = { ...params, include_simulation: includeSimulation };
    return useQuery({
        queryKey: ["managed-devices", scopedParams],
        queryFn: () => Services.getManagedDevices(scopedParams),
    });
};

export const useManagedDevicesPage = (params?: { limit?: number; offset?: number; status?: DeviceStatusFilter }) => {
    const includeSimulation = useSimulationStore((state) => state.isSimulating);
    const scopedParams = { ...params, include_simulation: includeSimulation };
    return useQuery({
        queryKey: ["managed-devices-page", scopedParams],
        queryFn: () => Services.getManagedDevicesPage(scopedParams),
    });
};

// ── Public Trace ──────────────────────────────────────────────

export const usePublicTrace = (batchId: string) => {
    return useQuery({
        queryKey: ["public-trace", batchId],
        queryFn: async () => {
            await ensureBackendSimulationBatch(batchId);
            return Services.getPublicTrace(batchId);
        },
        enabled: !!batchId,
        staleTime: 5 * 60 * 1000,
    });
};

// ── Stats ─────────────────────────────────────────────────────

export const useStatsOverview = () => {
    const includeSimulation = useSimulationStore((state) => state.isSimulating);
    return useQuery({
        queryKey: ["stats", "overview", { includeSimulation }],
        queryFn: () => Services.getStatsOverview({ include_simulation: includeSimulation }),
        refetchInterval: 60000,
    });
};

export const useDashboardStats = () => {
    const includeSimulation = useSimulationStore((state) => state.isSimulating);
    return useQuery({
        queryKey: ["stats", "dashboard", { includeSimulation }],
        queryFn: () => Services.getDashboardStats({ include_simulation: includeSimulation }),
        refetchInterval: 30000,
    });
};

export const useTemperatureTrend = () => {
    const includeSimulation = useSimulationStore((state) => state.isSimulating);
    return useQuery({
        queryKey: ["stats", "temperature-trend", { includeSimulation }],
        queryFn: () => Services.getTemperatureTrend({ include_simulation: includeSimulation }),
        refetchInterval: 60000,
    });
};

export const useQualityDistribution = () => {
    const includeSimulation = useSimulationStore((state) => state.isSimulating);
    return useQuery({
        queryKey: ["stats", "quality-distribution", { includeSimulation }],
        queryFn: () => Services.getQualityDistribution({ include_simulation: includeSimulation }),
        refetchInterval: 60000,
    });
};

export const useStageDistribution = () => {
    const includeSimulation = useSimulationStore((state) => state.isSimulating);
    return useQuery({
        queryKey: ["stats", "stage-distribution", { includeSimulation }],
        queryFn: () => Services.getStageDistribution({ include_simulation: includeSimulation }),
        refetchInterval: 60000,
    });
};

export const useRecentEvents = (limit: number = 10) => {
    const includeSimulation = useSimulationStore((state) => state.isSimulating);
    return useQuery({
        queryKey: ["events", "recent", limit, { includeSimulation }],
        queryFn: () => Services.getRecentEvents(limit, { include_simulation: includeSimulation }),
        refetchInterval: 30000,
    });
};

// ── Batch Detail ──────────────────────────────────────────────

export const useBatchStages = (batchId: string) => {
    return useQuery({
        queryKey: ["batch-stages", batchId],
        queryFn: async () => {
            await ensureBackendSimulationBatch(batchId);
            return Services.getBatchStages(batchId);
        },
        enabled: !!batchId,
    });
};

export const useBatchSensorHistory = (batchId: string) => {
    return useQuery({
        queryKey: ["batch-sensors", batchId],
        queryFn: async () => {
            await ensureBackendSimulationBatch(batchId);
            return Services.getBatchSensorHistory(batchId);
        },
        enabled: !!batchId,
    });
};

export const useBatchEvents = (batchId: string) => {
    return useQuery({
        queryKey: ["batch-events", batchId],
        queryFn: async () => {
            await ensureBackendSimulationBatch(batchId);
            return Services.getBatchEvents(batchId);
        },
        enabled: !!batchId,
    });
};
