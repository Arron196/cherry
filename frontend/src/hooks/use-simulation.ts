import { create } from "zustand";
import { persist } from "zustand/middleware";

export interface SensorDataPoint {
    time: string;
    temp: number;
    hum: number;
    vib: number;
}

export interface BlockEntry {
    id: string;
    hash: string;
    time: string;
    node: string;
}

interface SimulationState {
    isSimulating: boolean;
    toggleSimulation: () => void;
    setSimulation: (isSimulating: boolean) => void;

    sensorData: SensorDataPoint[];
    addSensorDataPoint: (point: SensorDataPoint) => void;
    initSensorData: (points: SensorDataPoint[]) => void;

    blocks: BlockEntry[];
    addBlock: (block: BlockEntry) => void;
    initBlocks: (blocks: BlockEntry[]) => void;
}

export const useSimulationStore = create<SimulationState>()(
    persist(
        (set) => ({
            isSimulating: true,
            toggleSimulation: () => set((state) => ({ isSimulating: !state.isSimulating })),
            setSimulation: (isSimulating) => set({ isSimulating }),

            sensorData: [],
            addSensorDataPoint: (point) => set((state) => ({
                sensorData: [...state.sensorData.slice(-19), point] // keep max 20 points
            })),
            initSensorData: (points) => set({ sensorData: points }),

            blocks: [],
            addBlock: (block) => set((state) => ({
                blocks: [block, ...state.blocks].slice(0, 15) // keep max 15 blocks
            })),
            initBlocks: (blocks) => set({ blocks }),
        }),
        {
            name: "simulation-storage",
            partialize: (state) => ({ isSimulating: state.isSimulating }), // Only persist the on/off switch!
        }
    )
);
