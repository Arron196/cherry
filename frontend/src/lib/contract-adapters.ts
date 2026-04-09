import {
    BatchStageInfo,
    CanonicalBatchStagesResponse,
    CanonicalPublicTraceResponse,
    DashboardStatsResponse,
    PublicTraceData,
    SensorDataPoint,
} from "@/types/api";

const STAGE_ORDER = ["harvest", "storage", "transport", "retail", "unknown"] as const;

function asRecord(value: unknown, context: string): Record<string, unknown> {
    if (typeof value !== "object" || value === null || Array.isArray(value)) {
        throw new Error(`${context} contract mismatch: expected object`);
    }
    return value as Record<string, unknown>;
}

function asArray(value: unknown, context: string): unknown[] {
    if (!Array.isArray(value)) {
        throw new Error(`${context} contract mismatch: expected array`);
    }
    return value;
}

function asString(value: unknown, context: string): string {
    if (typeof value !== "string") {
        throw new Error(`${context} contract mismatch: expected string`);
    }
    return value;
}

function asNumber(value: unknown, context: string): number {
    if (typeof value !== "number" || Number.isNaN(value)) {
        throw new Error(`${context} contract mismatch: expected number`);
    }
    return value;
}

function asBoolean(value: unknown, context: string): boolean {
    if (typeof value !== "boolean") {
        throw new Error(`${context} contract mismatch: expected boolean`);
    }
    return value;
}

function asOptionalString(value: unknown, context: string): string | undefined {
    if (value == null) {
        return undefined;
    }
    return asString(value, context);
}

function asOptionalNumber(value: unknown, context: string): number | undefined {
    if (value == null) {
        return undefined;
    }
    return asNumber(value, context);
}

function asStatus(value: unknown, context: string): "completed" | "active" | "pending" {
    if (value === "completed" || value === "active" || value === "pending") {
        return value;
    }
    throw new Error(`${context} contract mismatch: invalid status`);
}

export function assertArrayContract<T>(value: unknown, context: string): T[] {
    return asArray(value, context) as T[];
}

export function adaptDashboardStats(payload: unknown): DashboardStatsResponse {
    const root = asRecord(payload, "GET /v1/stats/dashboard");
    const overview = asRecord(root.overview, "GET /v1/stats/dashboard.overview");

    return {
        overview: {
            total_batches: asNumber(
                overview.total_batches,
                "GET /v1/stats/dashboard.overview.total_batches"
            ),
            total_events: asNumber(
                overview.total_events,
                "GET /v1/stats/dashboard.overview.total_events"
            ),
            active_devices: asNumber(
                overview.active_devices,
                "GET /v1/stats/dashboard.overview.active_devices"
            ),
            avg_quality_score: asNumber(
                overview.avg_quality_score,
                "GET /v1/stats/dashboard.overview.avg_quality_score"
            ),
            grade_distribution: {
                A: asNumber(
                    asRecord(
                        overview.grade_distribution,
                        "GET /v1/stats/dashboard.overview.grade_distribution"
                    ).A,
                    "GET /v1/stats/dashboard.overview.grade_distribution.A"
                ),
                B: asNumber(
                    asRecord(
                        overview.grade_distribution,
                        "GET /v1/stats/dashboard.overview.grade_distribution"
                    ).B,
                    "GET /v1/stats/dashboard.overview.grade_distribution.B"
                ),
                C: asNumber(
                    asRecord(
                        overview.grade_distribution,
                        "GET /v1/stats/dashboard.overview.grade_distribution"
                    ).C,
                    "GET /v1/stats/dashboard.overview.grade_distribution.C"
                ),
            },
            open_alerts: asNumber(
                overview.open_alerts,
                "GET /v1/stats/dashboard.overview.open_alerts"
            ),
        },
        temperature_trend: assertArrayContract(
            root.temperature_trend,
            "GET /v1/stats/dashboard.temperature_trend"
        ),
        quality_distribution: assertArrayContract(
            root.quality_distribution,
            "GET /v1/stats/dashboard.quality_distribution"
        ),
        stage_distribution: assertArrayContract(
            root.stage_distribution,
            "GET /v1/stats/dashboard.stage_distribution"
        ),
        recent_events: assertArrayContract(
            root.recent_events,
            "GET /v1/stats/dashboard.recent_events"
        ),
    };
}

function computeStageStatuses(stages: string[]): Array<"completed" | "active" | "pending"> {
    if (stages.length === 0) {
        return [];
    }
    const activeIndex = stages.length - 1;
    return stages.map((_, index) => (index === activeIndex ? "active" : "completed"));
}

export function adaptBatchStages(payload: unknown): BatchStageInfo {
    const root = asRecord(payload, "GET /v1/batches/{batch_id}/stages");
    const batchId = asString(root.batch_id, "GET /v1/batches/{batch_id}/stages.batch_id");
    const stagesRaw = asArray(root.stages, "GET /v1/batches/{batch_id}/stages.stages");

    const canonical = {
        batch_id: batchId,
        stages: stagesRaw.map((item, index) => {
            const row = asRecord(item, `GET /v1/batches/{batch_id}/stages.stages[${index}]`);
            return {
                stage: asString(row.stage, `GET /v1/batches/{batch_id}/stages.stages[${index}].stage`),
                event_count: asNumber(
                    row.event_count,
                    `GET /v1/batches/{batch_id}/stages.stages[${index}].event_count`
                ),
                start_time: asOptionalString(
                    row.start_time,
                    `GET /v1/batches/{batch_id}/stages.stages[${index}].start_time`
                ),
                end_time: asOptionalString(
                    row.end_time,
                    `GET /v1/batches/{batch_id}/stages.stages[${index}].end_time`
                ),
                events: asArray(
                    row.events,
                    `GET /v1/batches/{batch_id}/stages.stages[${index}].events`
                ).map((eventItem, eventIndex) => {
                    const eventRow = asRecord(
                        eventItem,
                        `GET /v1/batches/{batch_id}/stages.stages[${index}].events[${eventIndex}]`
                    );
                    return {
                        event_id: asNumber(
                            eventRow.event_id,
                            `GET /v1/batches/{batch_id}/stages.stages[${index}].events[${eventIndex}].event_id`
                        ),
                        timestamp: asString(
                            eventRow.timestamp,
                            `GET /v1/batches/{batch_id}/stages.stages[${index}].events[${eventIndex}].timestamp`
                        ),
                        device_id: asString(
                            eventRow.device_id,
                            `GET /v1/batches/{batch_id}/stages.stages[${index}].events[${eventIndex}].device_id`
                        ),
                        temperature_c: asOptionalNumber(
                            eventRow.temperature_c,
                            `GET /v1/batches/{batch_id}/stages.stages[${index}].events[${eventIndex}].temperature_c`
                        ),
                        humidity_pct: asOptionalNumber(
                            eventRow.humidity_pct,
                            `GET /v1/batches/{batch_id}/stages.stages[${index}].events[${eventIndex}].humidity_pct`
                        ),
                        co2_ppm: asOptionalNumber(
                            eventRow.co2_ppm,
                            `GET /v1/batches/{batch_id}/stages.stages[${index}].events[${eventIndex}].co2_ppm`
                        ),
                        vibration_g: asOptionalNumber(
                            eventRow.vibration_g,
                            `GET /v1/batches/{batch_id}/stages.stages[${index}].events[${eventIndex}].vibration_g`
                        ),
                    };
                }),
            };
        }),
    } satisfies CanonicalBatchStagesResponse;

    const ordered = [...canonical.stages].sort((left, right) => {
        const leftIndex = STAGE_ORDER.indexOf(left.stage as (typeof STAGE_ORDER)[number]);
        const rightIndex = STAGE_ORDER.indexOf(right.stage as (typeof STAGE_ORDER)[number]);
        const normalizedLeft = leftIndex === -1 ? STAGE_ORDER.length : leftIndex;
        const normalizedRight = rightIndex === -1 ? STAGE_ORDER.length : rightIndex;
        return normalizedLeft - normalizedRight;
    });
    const statuses = computeStageStatuses(ordered.map((entry) => entry.stage));

    return {
        batch_id: canonical.batch_id,
        stages: ordered.map((entry, index) => ({
            stage: entry.stage,
            label: entry.stage,
            event_count: entry.event_count,
            entered_at: entry.start_time,
            exited_at: statuses[index] === "completed" ? entry.end_time : undefined,
            status: asStatus(statuses[index], `GET /v1/batches/{batch_id}/stages.stages[${index}].status`),
        })),
    };
}

export function adaptPublicTrace(payload: unknown): PublicTraceData {
    const root = asRecord(payload, "GET /v1/public/trace/{batch_id}");
    const batchInfo = asRecord(root.batch_info, "GET /v1/public/trace/{batch_id}.batch_info");
    const timeline = asArray(root.timeline, "GET /v1/public/trace/{batch_id}.timeline");
    const stageEnvironments = asArray(
        root.stage_environments,
        "GET /v1/public/trace/{batch_id}.stage_environments"
    );
    const quality = asRecord(root.quality, "GET /v1/public/trace/{batch_id}.quality");
    const blockchainAnchor = asRecord(
        root.blockchain_anchor,
        "GET /v1/public/trace/{batch_id}.blockchain_anchor"
    );

    const canonical = {
        batch_info: {
            batch_id: asString(batchInfo.batch_id, "GET /v1/public/trace/{batch_id}.batch_info.batch_id"),
            total_events: asNumber(
                batchInfo.total_events,
                "GET /v1/public/trace/{batch_id}.batch_info.total_events"
            ),
            first_event_at: asOptionalString(
                batchInfo.first_event_at,
                "GET /v1/public/trace/{batch_id}.batch_info.first_event_at"
            ),
            last_event_at: asOptionalString(
                batchInfo.last_event_at,
                "GET /v1/public/trace/{batch_id}.batch_info.last_event_at"
            ),
        },
        timeline: timeline.map((item, index) => {
            const row = asRecord(item, `GET /v1/public/trace/{batch_id}.timeline[${index}]`);
            const sensorData = asRecord(
                row.sensor_data,
                `GET /v1/public/trace/{batch_id}.timeline[${index}].sensor_data`
            );
            return {
                event_id: asNumber(row.event_id, `GET /v1/public/trace/{batch_id}.timeline[${index}].event_id`),
                timestamp: asString(
                    row.timestamp,
                    `GET /v1/public/trace/{batch_id}.timeline[${index}].timestamp`
                ),
                device_id: asString(
                    row.device_id,
                    `GET /v1/public/trace/{batch_id}.timeline[${index}].device_id`
                ),
                supply_chain_stage: asOptionalString(
                    row.supply_chain_stage,
                    `GET /v1/public/trace/{batch_id}.timeline[${index}].supply_chain_stage`
                ),
                sensor_data: {
                    temperature_c: asOptionalNumber(
                        sensorData.temperature_c,
                        `GET /v1/public/trace/{batch_id}.timeline[${index}].sensor_data.temperature_c`
                    ),
                    humidity_pct: asOptionalNumber(
                        sensorData.humidity_pct,
                        `GET /v1/public/trace/{batch_id}.timeline[${index}].sensor_data.humidity_pct`
                    ),
                    co2_ppm: asOptionalNumber(
                        sensorData.co2_ppm,
                        `GET /v1/public/trace/{batch_id}.timeline[${index}].sensor_data.co2_ppm`
                    ),
                    vibration_g: asOptionalNumber(
                        sensorData.vibration_g,
                        `GET /v1/public/trace/{batch_id}.timeline[${index}].sensor_data.vibration_g`
                    ),
                },
            };
        }),
        stage_environments: stageEnvironments.map((item, index) => {
            const row = asRecord(
                item,
                `GET /v1/public/trace/{batch_id}.stage_environments[${index}]`
            );
            return {
                stage: asString(
                    row.stage,
                    `GET /v1/public/trace/{batch_id}.stage_environments[${index}].stage`
                ),
                event_count: asNumber(
                    row.event_count,
                    `GET /v1/public/trace/{batch_id}.stage_environments[${index}].event_count`
                ),
                avg_temperature_c: asOptionalNumber(
                    row.avg_temperature_c,
                    `GET /v1/public/trace/{batch_id}.stage_environments[${index}].avg_temperature_c`
                ),
                avg_humidity_pct: asOptionalNumber(
                    row.avg_humidity_pct,
                    `GET /v1/public/trace/{batch_id}.stage_environments[${index}].avg_humidity_pct`
                ),
                avg_co2_ppm: asOptionalNumber(
                    row.avg_co2_ppm,
                    `GET /v1/public/trace/{batch_id}.stage_environments[${index}].avg_co2_ppm`
                ),
                avg_vibration_g: asOptionalNumber(
                    row.avg_vibration_g,
                    `GET /v1/public/trace/{batch_id}.stage_environments[${index}].avg_vibration_g`
                ),
                start_time: asOptionalString(
                    row.start_time,
                    `GET /v1/public/trace/{batch_id}.stage_environments[${index}].start_time`
                ),
                end_time: asOptionalString(
                    row.end_time,
                    `GET /v1/public/trace/{batch_id}.stage_environments[${index}].end_time`
                ),
            };
        }),
        quality: {
            grade: asOptionalString(quality.grade, "GET /v1/public/trace/{batch_id}.quality.grade"),
            score: asOptionalNumber(quality.score, "GET /v1/public/trace/{batch_id}.quality.score"),
            max_score: asNumber(quality.max_score, "GET /v1/public/trace/{batch_id}.quality.max_score"),
        },
        blockchain_anchor: {
            is_anchored: asBoolean(
                blockchainAnchor.is_anchored,
                "GET /v1/public/trace/{batch_id}.blockchain_anchor.is_anchored"
            ),
            anchored_count: asNumber(
                blockchainAnchor.anchored_count,
                "GET /v1/public/trace/{batch_id}.blockchain_anchor.anchored_count"
            ),
            total_events: asNumber(
                blockchainAnchor.total_events,
                "GET /v1/public/trace/{batch_id}.blockchain_anchor.total_events"
            ),
            latest_transaction_hash: asOptionalString(
                blockchainAnchor.latest_transaction_hash,
                "GET /v1/public/trace/{batch_id}.blockchain_anchor.latest_transaction_hash"
            ),
        },
    } satisfies CanonicalPublicTraceResponse;

    const sensorHistory: SensorDataPoint[] = canonical.timeline
        .filter((event) => event.sensor_data.temperature_c != null && event.sensor_data.humidity_pct != null)
        .map((event) => ({
            timestamp: event.timestamp,
            temperature_c: event.sensor_data.temperature_c as number,
            humidity_pct: event.sensor_data.humidity_pct as number,
            co2_ppm: event.sensor_data.co2_ppm,
            vibration_g: event.sensor_data.vibration_g,
            supply_chain_stage: event.supply_chain_stage,
        }));

    const orderedStages = [...canonical.stage_environments].sort((left, right) => {
        const leftIndex = STAGE_ORDER.indexOf(left.stage as (typeof STAGE_ORDER)[number]);
        const rightIndex = STAGE_ORDER.indexOf(right.stage as (typeof STAGE_ORDER)[number]);
        const normalizedLeft = leftIndex === -1 ? STAGE_ORDER.length : leftIndex;
        const normalizedRight = rightIndex === -1 ? STAGE_ORDER.length : rightIndex;
        return normalizedLeft - normalizedRight;
    });
    const stageStatuses = computeStageStatuses(orderedStages.map((stage) => stage.stage));

    return {
        batch_id: canonical.batch_info.batch_id,
        total_events: canonical.batch_info.total_events,
        first_event_at: canonical.batch_info.first_event_at,
        last_event_at: canonical.batch_info.last_event_at,
        timeline: canonical.timeline,
        quality: {
            grade: canonical.quality.grade,
            score: canonical.quality.score ?? 0,
            max_score: canonical.quality.max_score,
        },
        stages: orderedStages.map((stage, index) => ({
            stage: stage.stage,
            entered_at: stage.start_time,
            status: asStatus(
                stageStatuses[index],
                `GET /v1/public/trace/{batch_id}.stage_environments[${index}].status`
            ),
        })),
        anchor: {
            status: canonical.blockchain_anchor.is_anchored ? "ANCHORED" : "PENDING",
            tx_hash: canonical.blockchain_anchor.latest_transaction_hash,
            anchored_count: canonical.blockchain_anchor.anchored_count,
            total_events: canonical.blockchain_anchor.total_events,
        },
        sensor_history: sensorHistory,
    };
}
