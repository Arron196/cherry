// RFC9457 Problem Details
export interface ProblemDetails {
    type: string;
    title: string;
    status: number;
    detail: string;
    instance: string;
    [key: string]: unknown;
}

// Common Responses
export interface PaginatedResponse<T> {
    total: number;
    limit: number;
    offset: number;
    items: T[];
}

// Domain Models

export interface TraceBatch {
    batch_id: string;
    device_id: string;
    event_count: number;
    start_time: string; // ISO 8601
    end_time: string; // ISO 8601
}

export interface TraceEvent {
    id: number;
    batch_id: string;
    device_id: string;
    timestamp: string;
    ingest_status: IngestStatus;
    supply_chain_stage?: string | null;
    temperature_c?: number | null;
    humidity_pct?: number | null;
    co2_ppm?: number | null;
    vibration_g?: number | null;
    quality_grade?: string | null;
    anchor_transaction_hash?: string | null;
}

export interface LoginResponse {
    access_token: string;
    token_type: "Bearer";
    expires_in: number;
    role: "admin" | "regulator";
}

export interface RegisterDeviceResponse {
    device_id: string;
    status: string;
    audit_id: number;
    initial_key?: {
        key_id: string;
        algorithm: string;
        status: string;
    } | null;
}

export interface RotateDeviceKeyResponse {
    device_id: string;
    key_id: string;
    algorithm: string;
    status: string;
    retired_key_ids: string[];
    audit_id: number;
}

export interface DisableDeviceResponse {
    device_id: string;
    status: string;
    retired_key_ids: string[];
    audit_id: number;
}

export interface ManagedDeviceKey {
    key_id: string;
    algorithm: string;
    status: string;
    activated_at: string;
    retired_at?: string | null;
}

export interface ManagedDeviceActiveKey {
    key_id: string;
    algorithm: string;
    status: string;
    activated_at: string;
}

export interface ManagedDevice {
    device_id: string;
    name?: string | null;
    display_name?: string | null;
    status: string;
    last_seen_at?: string | null;
    created_at: string;
}

export interface ManagedDeviceDetail {
    device_id: string;
    name?: string | null;
    status: string;
    last_seen_at?: string | null;
    created_at: string;
    key_count: number;
    active_key?: ManagedDeviceActiveKey | null;
    signature_failures_last_24h?: number;
    latest_signature_failure_reason?: string | null;
    online_status_explanation?: string;
}

export interface ManagedDeviceAudit {
    audit_id: number;
    actor: string;
    action: string;
    target: string;
    metadata?: Record<string, unknown> | null;
    created_at: string;
}

export type IngestStatus = "RECEIVED" | "ANCHORING" | "ANCHORED" | "FAILED_RETRYING" | "DEAD_LETTER" | "UNKNOWN";

export interface TraceEventSignatureEnvelope {
    algorithm: string;
    signature: string;
    key_id: string;
}

export interface TraceEventContractPayload {
    version: string;
    device_id: string;
    batch_id: string;
    timestamp: string;
    sensor_payload: Record<string, unknown>;
    signature_envelope: TraceEventSignatureEnvelope;
}

export interface ContractValidateResponse {
    status: "valid";
    canonical_hash: string;
}

export interface IngestEventResponse {
    event_id: number;
    ingest_status: IngestStatus;
}

export interface SimulationBatchResponse {
    batch_id: string;
    total_events: number;
    created_events: number;
    existing_events: number;
    anchored_events: number;
    processed_anchoring: number;
}

export interface SimulationGeneratorRequest {
    interval_seconds?: number;
    batches_per_tick?: number;
}

export interface SimulationGeneratorStatusResponse {
    running: boolean;
    interval_seconds: number;
    batches_per_tick: number;
    generated_events: number;
    generated_alerts: number;
    active_batches: string[];
    started_at: string | null;
    last_tick_at: string | null;
    last_error: string | null;
}

export interface SimulationTickResponse {
    generated_events: number;
    processed_anchoring: number;
    alerts_created: number;
    active_batches: string[];
}

export interface QualityGradeRequest {
    temperature_c: number;
    humidity_pct: number;
}

export interface QualityGradeResponse {
    grade: "A" | "B" | "C";
    score: number;
    max_score: number;
    reasons: string[];
    threshold_context: Record<string, unknown>;
}

export interface ActivatePolicyResponse {
    policy_id: string;
    status: "activated";
    audit_id: number;
}

export interface HealthResponse {
    status: string;
}

export interface TraceTimeline {
    batch_id: string;
    timeline_order: "oldest_first";
    timeline: TraceTimelineEvent[];
}

export interface TraceTimelineEvent {
    event_id: number;
    timestamp: string;
    ingest_status: string;
    anchor?: {
        status: string;
        transaction_hash?: string | null;
    };
    quality_grade?: string;
    alert_snapshot?: {
        total: number;
        open: number;
        high_open: number;
    };
}

export interface Alert {
    id: number;
    event_id: number;
    alert_type: string;
    severity: "low" | "medium" | "high" | "critical";
    status: "open" | "acknowledged" | "resolved";
    message: string;
    raised_at: string;
    resolved_at: string | null;
}

export interface AdminTask {
    ingest_request_id: number;
    event_id?: number;
    batch_id?: string;
    device_id?: string;
    status: AnchoringTaskStatus;
    retry_count: number;
    last_error?: string;
    created_at: string;
}

export type AnchoringTaskStatus = IngestStatus;

// Query Params
export interface BatchQueryParams {
    limit?: number;
    offset?: number;
    device_id?: string;
    start_time?: string;
    end_time?: string;
    include_simulation?: boolean;
}

export type DeviceStatusFilter = "active" | "disabled";

export interface AnchoringTaskQueryParams {
    status: AnchoringTaskStatus;
    limit?: number;
    offset?: number;
    batch_id?: string;
    device_id?: string;
}

export interface EventQueryParams {
    limit?: number;
    offset?: number;
    batch_id?: string;
    device_id?: string;
    ingest_status?: IngestStatus;
    start_time?: string;
    end_time?: string;
    include_simulation?: boolean;
}

// ── Public Trace ──────────────────────────────────────────────

export interface SensorDataPoint {
    timestamp: string;
    temperature_c: number;
    humidity_pct: number;
    co2_ppm?: number;
    vibration_g?: number;
    supply_chain_stage?: string;
}

// ── Statistics ────────────────────────────────────────────────

export interface StatsOverview {
    total_batches: number;
    total_events: number;
    active_devices: number;
    avg_quality_score: number;
    grade_distribution: { A: number; B: number; C: number };
    open_alerts: number;
}

export interface TemperatureTrendPoint {
    timestamp: string;
    avg_temperature: number;
    min_temperature: number;
    max_temperature: number;
}

export interface QualityDistribution {
    grade: "A" | "B" | "C";
    count: number;
    percentage: number;
}

export interface StageDistribution {
    stage: string;
    count: number;
}

export interface BatchStageInfo {
    batch_id: string;
    stages: {
        stage: string;
        label: string;
        event_count: number;
        entered_at?: string;
        exited_at?: string;
        status: "completed" | "active" | "pending";
    }[];
}

export interface RecentEvent {
    id: number;
    batch_id: string;
    device_id: string;
    timestamp: string;
    ingest_status: IngestStatus;
    temperature_c?: number | null;
    humidity_pct?: number | null;
    co2_ppm?: number | null;
    vibration_g?: number | null;
    supply_chain_stage?: string;
    quality_grade?: string;
    anchor_transaction_hash?: string | null;
}

export interface DashboardStatsResponse {
    overview: StatsOverview;
    temperature_trend: TemperatureTrendPoint[];
    quality_distribution: QualityDistribution[];
    stage_distribution: StageDistribution[];
    recent_events: RecentEvent[];
}

export interface CanonicalPublicTraceSensorData {
    temperature_c?: number;
    humidity_pct?: number;
    co2_ppm?: number;
    vibration_g?: number;
}

export interface CanonicalPublicTraceTimelineEvent {
    event_id: number;
    timestamp: string;
    device_id: string;
    supply_chain_stage?: string;
    sensor_data: CanonicalPublicTraceSensorData;
}

export interface CanonicalPublicTraceStageEnvironment {
    stage: string;
    event_count: number;
    avg_temperature_c?: number;
    avg_humidity_pct?: number;
    avg_co2_ppm?: number;
    avg_vibration_g?: number;
    start_time?: string;
    end_time?: string;
}

export interface CanonicalPublicTraceResponse {
    batch_info: {
        batch_id: string;
        total_events: number;
        first_event_at?: string;
        last_event_at?: string;
    };
    timeline: CanonicalPublicTraceTimelineEvent[];
    stage_environments: CanonicalPublicTraceStageEnvironment[];
    quality: {
        grade?: string;
        score?: number;
        max_score: number;
    };
    blockchain_anchor: {
        is_anchored: boolean;
        anchored_count: number;
        total_events: number;
        latest_transaction_hash?: string;
    };
}

export interface CanonicalBatchStageEvent {
    event_id: number;
    timestamp: string;
    device_id: string;
    temperature_c?: number;
    humidity_pct?: number;
    co2_ppm?: number;
    vibration_g?: number;
}

export interface CanonicalBatchStage {
    stage: string;
    event_count: number;
    start_time?: string;
    end_time?: string;
    events: CanonicalBatchStageEvent[];
}

export interface CanonicalBatchStagesResponse {
    batch_id: string;
    stages: CanonicalBatchStage[];
}

export interface PublicTraceData {
    batch_id: string;
    total_events: number;
    first_event_at?: string;
    last_event_at?: string;
    timeline: CanonicalPublicTraceTimelineEvent[];
    quality: {
        grade?: string;
        score: number;
        max_score: number;
    };
    stages: {
        stage: string;
        entered_at?: string;
        status: "completed" | "active" | "pending";
    }[];
    anchor: {
        status: "ANCHORED" | "PENDING";
        tx_hash?: string;
        anchored_count: number;
        total_events: number;
    };
    sensor_history: SensorDataPoint[];
}
