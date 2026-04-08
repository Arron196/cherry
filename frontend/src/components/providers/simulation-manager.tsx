"use client";

import { useCallback, useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useSimulationStore } from "@/hooks/use-simulation";
import { useAuthStore } from "@/hooks/use-auth";
import { Services } from "@/lib/services";

const generateDisplayHash = (seed: string) => {
    let value = 0x811c9dc5;
    for (const char of seed) {
        value ^= char.charCodeAt(0);
        value = Math.imul(value, 0x01000193) >>> 0;
    }

    let hex = "";
    for (let index = 0; index < 40; index++) {
        value = (Math.imul(value, 1664525) + 1013904223 + index) >>> 0;
        hex += (value & 0xf).toString(16);
    }
    return `0x${hex}`;
};

const refreshKeys = [
    ["stats"],
    ["events"],
    ["batches"],
    ["alerts"],
    ["managed-devices"],
    ["managed-devices-page"],
    ["anchoring"],
] as const;

const BACKEND_GENERATOR_INTERVAL_SECONDS = 5;
const UI_REFRESH_INTERVAL_MS = 15000;

export function SimulationManager() {
    const { isSimulating, sensorData, initSensorData, addSensorDataPoint, blocks, initBlocks } = useSimulationStore();
    const { role, token } = useAuthStore();
    const queryClient = useQueryClient();
    const initialized = useRef(false);

    const invalidateSimulationQueries = useCallback(() => {
        for (const queryKey of refreshKeys) {
            void queryClient.invalidateQueries({ queryKey });
        }
    }, [queryClient]);

    useEffect(() => {
        if (!initialized.current) {
            // Data hydration
            if (sensorData.length === 0) {
                const initialSensors = Array.from({ length: 20 }, (_, i) => {
                    const past = new Date(Date.now() - (20 - i) * 1200);
                    const phase = i / 3;
                    return {
                        time: past.toLocaleTimeString("en-GB", { hour12: false }),
                        temp: 4.8 + Math.sin(phase) * 0.7,
                        hum: 74 + Math.cos(phase * 0.8) * 1.8,
                        vib: 0.08 + Math.abs(Math.sin(phase * 1.5)) * 0.04,
                    };
                });
                initSensorData(initialSensors);
            }

            if (blocks.length === 0) {
                const initialBlocks = Array.from({ length: 6 }).map((_, i) => ({
                    id: `BLK-${18293 + i}`,
                    hash: generateDisplayHash(`initial-${i}`),
                    time: new Date(Date.now() - (6 - i) * 12000).toLocaleTimeString("en-GB", { hour12: false }),
                    node: ["FarmNode", "ColdChain", "Warehouse", "Retail"][i % 4],
                })).reverse();
                initBlocks(initialBlocks);
            }
            initialized.current = true;
        }
    }, [blocks.length, initBlocks, initSensorData, sensorData.length]);

    useEffect(() => {
        const canUseGenerator = Boolean(token) && (role === "admin" || role === "regulator");
        if (!isSimulating) {
            if (canUseGenerator) {
                void Services.stopSimulationGenerator()
                    .then(() => invalidateSimulationQueries())
                    .catch((error) => {
                        console.error("Failed to stop backend simulation generator", error);
                    });
            }
            return;
        }

        if (canUseGenerator) {
            void Services.startSimulationGenerator({
                interval_seconds: BACKEND_GENERATOR_INTERVAL_SECONDS,
                batches_per_tick: 4,
            })
                .then(() => {
                    invalidateSimulationQueries();
                })
                .catch((error) => {
                    console.error("Failed to start backend simulation generator", error);
                });
        }

        const backendInterval = window.setInterval(() => {
            if (canUseGenerator) {
                invalidateSimulationQueries();
            }
        }, UI_REFRESH_INTERVAL_MS);

        // Small visual telemetry buffer; the persisted business data comes from the backend generator above.
        const sensorInterval = window.setInterval(() => {
            const now = new Date();
            const phase = now.getTime() / 2400;
            addSensorDataPoint({
                time: now.toLocaleTimeString("en-GB", { hour12: false }),
                temp: 4.8 + Math.sin(phase) * 0.8,
                hum: 74 + Math.cos(phase * 0.75) * 2.2,
                vib: 0.08 + Math.abs(Math.sin(phase * 1.7)) * 0.05,
            });
        }, 1200);

        return () => {
            window.clearInterval(backendInterval);
            window.clearInterval(sensorInterval);
        };
    }, [isSimulating, role, token, addSensorDataPoint, invalidateSimulationQueries]);

    return null; // Purely logical hidden component
}
