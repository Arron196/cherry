import { DevicesPageClient } from "../devices-page-client";

type DeviceDetailRouteProps = {
    params: Promise<{ deviceId: string }> | { deviceId: string };
};

export default async function DeviceDetailRoute({ params }: DeviceDetailRouteProps) {
    const resolvedParams = await params;

    return <DevicesPageClient initialDeviceId={decodeURIComponent(resolvedParams.deviceId)} />;
}
