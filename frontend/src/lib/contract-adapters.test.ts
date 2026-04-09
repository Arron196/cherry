import { describe, expect, it } from "vitest";

import { adaptBatchStages, adaptDashboardStats, adaptPublicTrace } from "./contract-adapters";

describe("adaptBatchStages", () => {
    it("adapts dashboard-relevant canonical stage contracts", () => {
        const payload = {
            batch_id: "batch-001",
            stages: [
                {
                    stage: "transport",
                    event_count: 2,
                    start_time: "2026-01-03T10:00:00Z",
                    end_time: "2026-01-03T12:00:00Z",
                    events: [
                        {
                            event_id: 1002,
                            timestamp: "2026-01-03T10:30:00Z",
                            device_id: "dev-2",
                            temperature_c: 4.2,
                            humidity_pct: 77.5,
                        },
                    ],
                },
                {
                    stage: "harvest",
                    event_count: 1,
                    start_time: "2026-01-03T08:00:00Z",
                    end_time: "2026-01-03T09:30:00Z",
                    events: [
                        {
                            event_id: 1001,
                            timestamp: "2026-01-03T08:15:00Z",
                            device_id: "dev-1",
                        },
                    ],
                },
            ],
        };

        const adapted = adaptBatchStages(payload);

        expect(adapted.batch_id).toBe("batch-001");
        expect(adapted.stages).toHaveLength(2);
        expect(adapted.stages[0]).toMatchObject({
            stage: "harvest",
            label: "harvest",
            event_count: 1,
            status: "completed",
            entered_at: "2026-01-03T08:00:00Z",
            exited_at: "2026-01-03T09:30:00Z",
        });
        expect(adapted.stages[1]).toMatchObject({
            stage: "transport",
            label: "transport",
            event_count: 2,
            status: "active",
            entered_at: "2026-01-03T10:00:00Z",
        });
        expect(adapted.stages[1].exited_at).toBeUndefined();
    });

    it("throws on contract drift for missing required keys", () => {
        const payload = {
            batch_id: "batch-001",
        };

        expect(() => adaptBatchStages(payload)).toThrow(/contract mismatch/);
    });

    it("throws on contract drift for invalid field types", () => {
        const payload = {
            batch_id: "batch-001",
            stages: [
                {
                    stage: "harvest",
                    event_count: "1",
                    start_time: "2026-01-03T08:00:00Z",
                    end_time: "2026-01-03T09:30:00Z",
                    events: [],
                },
            ],
        };

        expect(() => adaptBatchStages(payload)).toThrow(/expected number/);
    });
});

describe("adaptPublicTrace", () => {
    it("adapts canonical public trace contracts", () => {
        const payload = {
            batch_info: {
                batch_id: "batch-002",
                total_events: 2,
                first_event_at: "2026-01-03T08:00:00Z",
                last_event_at: "2026-01-03T12:00:00Z",
            },
            timeline: [
                {
                    event_id: 2001,
                    timestamp: "2026-01-03T08:05:00Z",
                    device_id: "dev-1",
                    supply_chain_stage: "harvest",
                    sensor_data: {
                        temperature_c: 3.4,
                        humidity_pct: 80.1,
                        co2_ppm: 415.2,
                    },
                },
                {
                    event_id: 2002,
                    timestamp: "2026-01-03T11:30:00Z",
                    device_id: "dev-2",
                    supply_chain_stage: "transport",
                    sensor_data: {
                        temperature_c: 4.1,
                    },
                },
            ],
            stage_environments: [
                {
                    stage: "transport",
                    event_count: 1,
                    avg_temperature_c: 4.1,
                    avg_humidity_pct: 70.2,
                    start_time: "2026-01-03T10:00:00Z",
                    end_time: "2026-01-03T12:00:00Z",
                },
                {
                    stage: "harvest",
                    event_count: 1,
                    avg_temperature_c: 3.4,
                    avg_humidity_pct: 80.1,
                    start_time: "2026-01-03T08:00:00Z",
                    end_time: "2026-01-03T09:00:00Z",
                },
            ],
            quality: {
                grade: "A",
                max_score: 100,
            },
            blockchain_anchor: {
                is_anchored: true,
                anchored_count: 2,
                total_events: 2,
                latest_transaction_hash: "0xabc",
            },
        };

        const adapted = adaptPublicTrace(payload);

        expect(adapted.batch_id).toBe("batch-002");
        expect(adapted.quality).toEqual({
            grade: "A",
            score: 0,
            max_score: 100,
        });
        expect(adapted.anchor).toEqual({
            status: "ANCHORED",
            tx_hash: "0xabc",
            anchored_count: 2,
            total_events: 2,
        });
        expect(adapted.stages).toEqual([
            {
                stage: "harvest",
                entered_at: "2026-01-03T08:00:00Z",
                status: "completed",
            },
            {
                stage: "transport",
                entered_at: "2026-01-03T10:00:00Z",
                status: "active",
            },
        ]);
        expect(adapted.sensor_history).toHaveLength(1);
        expect(adapted.sensor_history[0]).toMatchObject({
            timestamp: "2026-01-03T08:05:00Z",
            temperature_c: 3.4,
            humidity_pct: 80.1,
            co2_ppm: 415.2,
            supply_chain_stage: "harvest",
        });
    });

    it("throws on contract drift for missing required keys", () => {
        const payload = {
            batch_info: {
                batch_id: "batch-002",
                total_events: 2,
            },
            timeline: [],
            stage_environments: [],
            quality: {
                grade: "A",
            },
            blockchain_anchor: {
                is_anchored: true,
                anchored_count: 2,
                total_events: 2,
            },
        };

        expect(() => adaptPublicTrace(payload)).toThrow(/expected number/);
    });

    it("throws on contract drift for invalid field types", () => {
        const payload = {
            batch_info: {
                batch_id: "batch-002",
                total_events: 2,
            },
            timeline: [],
            stage_environments: [],
            quality: {
                max_score: 100,
            },
            blockchain_anchor: {
                is_anchored: "yes",
                anchored_count: 2,
                total_events: 2,
            },
        };

        expect(() => adaptPublicTrace(payload)).toThrow(/expected boolean/);
    });
});

describe("adaptDashboardStats", () => {
    it("adapts the aggregated dashboard stats contract", () => {
        const payload = {
            overview: {
                total_batches: 2,
                total_events: 3,
                active_devices: 1,
                avg_quality_score: 92.5,
                grade_distribution: {
                    A: 2,
                    B: 1,
                    C: 0,
                },
                open_alerts: 1,
            },
            temperature_trend: [
                {
                    timestamp: "2026-01-03T10:00:00Z",
                    avg_temperature: 4.2,
                    min_temperature: 4.0,
                    max_temperature: 4.4,
                },
            ],
            quality_distribution: [
                {
                    grade: "A",
                    count: 2,
                    percentage: 66.7,
                },
            ],
            stage_distribution: [
                {
                    stage: "transport",
                    count: 2,
                },
            ],
            recent_events: [
                {
                    id: 1001,
                    batch_id: "batch-1",
                    device_id: "dev-1",
                    timestamp: "2026-01-03T10:00:00Z",
                    ingest_status: "ANCHORED",
                    temperature_c: 4.2,
                    humidity_pct: 77.5,
                    supply_chain_stage: "transport",
                    quality_grade: "A",
                },
            ],
        };

        expect(adaptDashboardStats(payload)).toEqual(payload);
    });

    it("throws on contract drift for missing overview", () => {
        const payload = {
            temperature_trend: [],
            quality_distribution: [],
            stage_distribution: [],
            recent_events: [],
        };

        expect(() => adaptDashboardStats(payload)).toThrow(/expected object/);
    });

    it("throws on contract drift for invalid overview totals", () => {
        const payload = {
            overview: {
                total_batches: "2",
                total_events: 3,
                active_devices: 1,
                avg_quality_score: 92.5,
                grade_distribution: {
                    A: 2,
                    B: 1,
                    C: 0,
                },
                open_alerts: 1,
            },
            temperature_trend: [],
            quality_distribution: [],
            stage_distribution: [],
            recent_events: [],
        };

        expect(() => adaptDashboardStats(payload)).toThrow(/expected number/);
    });
});
