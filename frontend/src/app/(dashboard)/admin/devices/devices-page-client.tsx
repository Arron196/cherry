"use client";

import { useEffect, useRef, useState } from "react";
import { DeviceAdminPageChrome, DeviceHighFrequencyIntro, DeviceLowFrequencyShell } from "./device-admin-page-chrome";
import { FeedbackState } from "./device-admin.types";
import { DeviceDisableCard } from "./device-disable-card";
import { DeviceDetailCard } from "./device-detail-card";
import { DeviceIngestGuideCard } from "./device-ingest-guide-card";
import { DeviceOverviewCard } from "./device-overview-card";
import { DeviceRegisterCard } from "./device-register-card";
import { DeviceRotateCard } from "./device-rotate-card";
import { DeviceTestEventCard } from "./device-test-event-card";
import { useDeviceAdminActions } from "./use-device-admin-actions";
import { useDeviceAdminPageInteractions } from "./use-device-admin-page-interactions";
import { useDeviceDetailState } from "./use-device-detail-state";
import { useDeviceAdminFormState } from "./use-device-admin-form-state";
import { useGuideContextState } from "./use-guide-context-state";
import { useDeviceIngestGuideModel } from "./use-device-ingest-guide-model";
import { useDeviceKeyListState } from "./use-device-key-list-state";
import { useDeviceOverviewViewModel } from "./use-device-overview-view-model";
import { useDeviceListPreferences } from "./use-device-list-preferences";

type DevicesPageProps = {
    initialDeviceId?: string;
};

export function DevicesPageClient({ initialDeviceId }: DevicesPageProps = {}) {
    const [feedback, setFeedback] = useState<FeedbackState>(null);
    const loadedInitialDeviceIdRef = useRef<string | null>(null);

    const {
        newDeviceId,
        setNewDeviceId,
        displayName,
        setDisplayName,
        enableInitialKey,
        setEnableInitialKey,
        initialKeyDraft,
        setInitialKeyDraft,
        latestInitialKeySecret,
        setLatestInitialKeySecret,
        rotateDeviceId,
        setRotateDeviceId,
        rotateKeyId,
        setRotateKeyId,
        rotateAlgorithm,
        setRotateAlgorithm,
        rotateSecret,
        setRotateSecret,
        disableDeviceId,
        setDisableDeviceId,
        disableReason,
        setDisableReason,
        lastRotateResult,
        setLastRotateResult,
        lastDisableResult,
        setLastDisableResult,
        setLatestRotateSecret,
        testEventBatchId,
        setTestEventBatchId,
        testEventTemperature,
        setTestEventTemperature,
        testEventHumidity,
        setTestEventHumidity,
        testEventStatus,
        setTestEventStatus,
        testEventTimestamp,
        setTestEventTimestamp,
        testEventResult,
        setTestEventResult,
        testEventError,
        setTestEventError,
    } = useDeviceAdminFormState();

    const {
        selectedDeviceId,
        selectedDeviceDetail,
        isDetailLoading,
        detailError,
        detailKeyList,
        detailKeyDeviceId,
        detailKeyQueryState,
        detailKeyQueryMessage,
        detailAuditList,
        detailAuditDeviceId,
        detailAuditQueryState,
        detailAuditQueryMessage,
        queryManagedDeviceDetail,
        queryDeviceKeyTimeline,
        queryDeviceAuditTimeline,
    } = useDeviceDetailState();

    const {
        keyList,
        keyListDeviceId,
        keyQueryState,
        keyQueryMessage,
        queryManagedDeviceKeys,
    } = useDeviceKeyListState();

    const {
        guideContext,
        clearGuideContext,
        setGuideContextFromRegister,
        setGuideContextFromRotate,
        setGuideContextFromDetail,
    } = useGuideContextState({ selectedDeviceDetail });

    const {
        highlightSectionId,
        setPendingDetailScroll,
        handleCopyInitialSecret,
        handleCopyRetiredKeyIds,
        handleFillRotateFromDetail,
        handleFillDisableFromDetail,
        prepareRotateFromOverview,
        prepareDisableFromOverview,
    } = useDeviceAdminPageInteractions({
        latestInitialKeySecret,
        selectedDeviceDetail,
        setFeedback,
        setRotateDeviceId,
        setRotateAlgorithm,
        setRotateKeyId,
        setRotateSecret,
        setDisableDeviceId,
        setDisableReason,
        setGuideContextFromDetail,
    });

    const {
        guideDeviceId,
        resolvedGuideKeyId,
        resolvedGuideAlgorithm,
        availableGuideSecret,
        hasRealGuideSecret,
        resolvedGuideSecret,
        guidePayloadExample,
        guideRequestExample,
    } = useDeviceIngestGuideModel({
        selectedDeviceDetail,
        rotateDeviceId,
        newDeviceId,
        rotateKeyId,
        rotateAlgorithm,
        rotateSecret,
        initialKeyDraft,
        guideContext,
    });

    const {
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
    } = useDeviceListPreferences({});

    const {
        isLoading,
        isFetching,
        isError,
        error,
        refetch,
        devices,
        totalDevices,
        totalPages,
        displayCurrentPage,
        pageEnabledDevices,
        pageDisabledDevices,
        pageOnlineDevices,
        handlePageJump,
    } = useDeviceOverviewViewModel({
        statusFilter,
        pageIndex,
        pageSize,
        onlineWindowSeconds,
        pageJumpInput,
        setPageIndex,
        setPageJumpInput,
        setFeedback,
    });

    const {
        registerMutation,
        rotateKeyMutation,
        disableMutation,
        ingestTestEventMutation,
        refreshManagedDevices,
        handleRegister,
        handleRotateKey,
        handleDisableDevice,
        handleIngestTestEvent,
    } = useDeviceAdminActions({
        refetch,
        selectedDeviceId,
        queryManagedDeviceDetail,
        queryManagedDeviceKeys,
        setFeedback,
        newDeviceId,
        displayName,
        enableInitialKey,
        initialKeyDraft,
        setNewDeviceId,
        setDisplayName,
        setEnableInitialKey,
        setInitialKeyDraft,
        setLatestInitialKeySecret,
        clearGuideContext,
        setGuideContextFromRegister,
        rotateDeviceId,
        rotateKeyId,
        rotateAlgorithm,
        rotateSecret,
        setRotateKeyId,
        setRotateSecret,
        setLastRotateResult,
        setLatestRotateSecret,
        setGuideContextFromRotate,
        disableDeviceId,
        disableReason,
        setDisableDeviceId,
        setDisableReason,
        setLastDisableResult,
        guideContext,
        guideDeviceId,
        resolvedGuideKeyId,
        resolvedGuideAlgorithm,
        availableGuideSecret,
        testEventBatchId,
        testEventTimestamp,
        testEventTemperature,
        testEventHumidity,
        testEventStatus,
        setTestEventResult,
        setTestEventError,
        setTestEventBatchId,
        setTestEventTimestamp,
    });

    useEffect(() => {
        const target = initialDeviceId?.trim();
        if (!target || loadedInitialDeviceIdRef.current === target) {
            return;
        }

        loadedInitialDeviceIdRef.current = target;
        setPendingDetailScroll(true);
        void queryManagedDeviceDetail(target, {
            onFailure: () => setPendingDetailScroll(false),
        });
    }, [initialDeviceId, queryManagedDeviceDetail, setPendingDetailScroll]);

    return (
        <div className="space-y-7">
            <DeviceAdminPageChrome feedback={feedback} />

            <DeviceOverviewCard
                devices={devices}
                isLoading={isLoading}
                isFetching={isFetching}
                isError={isError}
                error={error}
                totalDevices={totalDevices}
                totalPages={totalPages}
                displayCurrentPage={displayCurrentPage}
                statusFilter={statusFilter}
                pageEnabledDevices={pageEnabledDevices}
                pageDisabledDevices={pageDisabledDevices}
                pageOnlineDevices={pageOnlineDevices}
                onlineWindowSeconds={onlineWindowSeconds}
                pageSize={pageSize}
                pageJumpInput={pageJumpInput}
                selectedDeviceId={selectedDeviceId}
                isDetailLoading={isDetailLoading}
                onStatusFilterChange={handleStatusFilterChange}
                onOnlineWindowSecondsChange={setOnlineWindowSeconds}
                onRefresh={() => {
                    void refreshManagedDevices();
                }}
                onViewDetail={(deviceId) => {
                    setPendingDetailScroll(true);
                    void queryManagedDeviceDetail(deviceId, {
                        onFailure: () => setPendingDetailScroll(false),
                    });
                }}
                onPrepareRotate={prepareRotateFromOverview}
                onPrepareDisable={prepareDisableFromOverview}
                onPageSizeChange={handlePageSizeChange}
                onFirstPage={() => setPageIndex(0)}
                onPreviousPage={() => setPageIndex((prev) => Math.max(0, prev - 1))}
                onNextPage={() => setPageIndex((prev) => Math.min(totalPages - 1, prev + 1))}
                onLastPage={() => setPageIndex(Math.max(0, totalPages - 1))}
                onPageJumpInputChange={setPageJumpInput}
                onPageJump={handlePageJump}
            />

            <DeviceDetailCard
                highlightSectionId={highlightSectionId}
                detailError={detailError}
                selectedDeviceId={selectedDeviceId}
                selectedDeviceDetail={selectedDeviceDetail}
                isDetailLoading={isDetailLoading}
                onlineWindowSeconds={onlineWindowSeconds}
                detailKeyList={detailKeyList}
                detailKeyDeviceId={detailKeyDeviceId}
                detailKeyQueryState={detailKeyQueryState}
                detailKeyQueryMessage={detailKeyQueryMessage}
                detailAuditList={detailAuditList}
                detailAuditDeviceId={detailAuditDeviceId}
                detailAuditQueryState={detailAuditQueryState}
                detailAuditQueryMessage={detailAuditQueryMessage}
                onFillRotateFromDetail={handleFillRotateFromDetail}
                onFillDisableFromDetail={handleFillDisableFromDetail}
                onRefreshKeyTimeline={(deviceId) => {
                    void queryDeviceKeyTimeline(deviceId);
                }}
                onRefreshAuditTimeline={(deviceId) => {
                    void queryDeviceAuditTimeline(deviceId);
                }}
            />

            <div className="grid gap-6 md:grid-cols-2" id="section-device-high-frequency">
                <DeviceHighFrequencyIntro />

                <DeviceRegisterCard
                    highlightSectionId={highlightSectionId}
                    newDeviceId={newDeviceId}
                    displayName={displayName}
                    enableInitialKey={enableInitialKey}
                    initialKeyDraft={initialKeyDraft}
                    latestInitialKeySecret={latestInitialKeySecret}
                    isPending={registerMutation.isPending}
                    onNewDeviceIdChange={setNewDeviceId}
                    onDisplayNameChange={setDisplayName}
                    onEnableInitialKeyChange={setEnableInitialKey}
                    onInitialKeyDraftChange={setInitialKeyDraft}
                    onSubmit={handleRegister}
                    onCopyInitialSecret={() => {
                        void handleCopyInitialSecret();
                    }}
                />

                <DeviceRotateCard
                    highlightSectionId={highlightSectionId}
                    rotateDeviceId={rotateDeviceId}
                    rotateKeyId={rotateKeyId}
                    rotateAlgorithm={rotateAlgorithm}
                    rotateSecret={rotateSecret}
                    isPending={rotateKeyMutation.isPending}
                    keyQueryState={keyQueryState}
                    keyQueryMessage={keyQueryMessage}
                    keyList={keyList}
                    keyListDeviceId={keyListDeviceId}
                    lastRotateResult={lastRotateResult}
                    onRotateDeviceIdChange={setRotateDeviceId}
                    onRotateKeyIdChange={setRotateKeyId}
                    onRotateAlgorithmChange={setRotateAlgorithm}
                    onRotateSecretChange={setRotateSecret}
                    onSubmit={handleRotateKey}
                    onQueryManagedDeviceKeys={(deviceId) => {
                        void queryManagedDeviceKeys(deviceId);
                    }}
                    onCopyRetiredKeyIds={(deviceId, keyIds, context) => {
                        void handleCopyRetiredKeyIds(deviceId, keyIds, context);
                    }}
                />

                <DeviceDisableCard
                    highlightSectionId={highlightSectionId}
                    disableDeviceId={disableDeviceId}
                    disableReason={disableReason}
                    isPending={disableMutation.isPending}
                    lastDisableResult={lastDisableResult}
                    onDisableDeviceIdChange={setDisableDeviceId}
                    onDisableReasonChange={setDisableReason}
                    onSubmit={handleDisableDevice}
                    onCopyRetiredKeyIds={(deviceId, keyIds, context) => {
                        void handleCopyRetiredKeyIds(deviceId, keyIds, context);
                    }}
                />

                <DeviceLowFrequencyShell>
                    <DeviceIngestGuideCard
                        guideDeviceId={guideDeviceId}
                        resolvedGuideKeyId={resolvedGuideKeyId}
                        resolvedGuideAlgorithm={resolvedGuideAlgorithm}
                        resolvedGuideSecret={resolvedGuideSecret}
                        hasRealGuideSecret={hasRealGuideSecret}
                        guidePayloadExample={guidePayloadExample}
                        guideRequestExample={guideRequestExample}
                    />

                    <DeviceTestEventCard
                        guideDeviceId={guideDeviceId}
                        resolvedGuideKeyId={resolvedGuideKeyId}
                        resolvedGuideAlgorithm={resolvedGuideAlgorithm}
                        testEventBatchId={testEventBatchId}
                        testEventTimestamp={testEventTimestamp}
                        testEventTemperature={testEventTemperature}
                        testEventHumidity={testEventHumidity}
                        testEventStatus={testEventStatus}
                        isPending={ingestTestEventMutation.isPending}
                        testEventError={testEventError}
                        testEventResult={testEventResult}
                        onBatchIdChange={setTestEventBatchId}
                        onTimestampChange={setTestEventTimestamp}
                        onTemperatureChange={setTestEventTemperature}
                        onHumidityChange={setTestEventHumidity}
                        onStatusChange={setTestEventStatus}
                        onUseCurrentTime={() => setTestEventTimestamp(new Date().toISOString())}
                        onSubmit={handleIngestTestEvent}
                    />
                </DeviceLowFrequencyShell>
            </div>
        </div>
    );
}
