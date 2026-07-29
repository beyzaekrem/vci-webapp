/**
 * This module provides typed access to the system_layout.json data
 * and helper functions for mapping cameras to their physical positions.
 * @packageDocumentation
 */

import systemLayoutJson from "./system_layout.json";
import { getServers } from "../../network/capture-server";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

/** A named slot on a pillar, e.g. "ceiling", "center", "rig_low", "floor" */
export type SlotName = "ceiling" | "center" | "rig_low" | "rig_upper" | "floor";

/** Camera shorthand strings grouped by slot */
export interface PillarPositions {
    ceiling?: string[];
    center?: string[];
    rig_low?: string[];
    rig_upper?: string[];
    floor?: string[];
}

/** Full system layout as parsed from JSON */
export interface SystemLayout {
    control: { ip: string; port: string };
    servers: Record<string, { ip: string; port: string; cameras: string[] }>;
    positions: Record<string, PillarPositions>;
    expected_cameras: number;
}

/** A single camera entry with its physical context */
export interface CameraEntry {
    shorthand: string;
    pillarKey: string;       // e.g. "pillar_1"
    pillarIndex: number;     // 1-based
    slot: SlotName;
    slotIndex: number;       // index within that slot array
}

/** Resolved camera: a CameraEntry that has been matched to a capture server */
export interface ResolvedCamera extends CameraEntry {
    serverIndex: number;
    cameraIndex: number;
}

/* ------------------------------------------------------------------ */
/*  Data access                                                        */
/* ------------------------------------------------------------------ */

/** The loaded system layout data */
export const systemLayout: SystemLayout = systemLayoutJson as SystemLayout;

/** Sorted pillar keys, e.g. ["pillar_1", "pillar_2", ...] */
export function getPillarKeys(): string[] {
    return Object.keys(systemLayout.positions).sort((a, b) => {
        const numA = parseInt(a.replace("pillar_", ""));
        const numB = parseInt(b.replace("pillar_", ""));
        return numA - numB;
    });
}

/** Get the pillar number from a key like "pillar_3" → 3 */
export function getPillarNumber(key: string): number {
    return parseInt(key.replace("pillar_", ""));
}

/** Display-friendly slot name */
export function getSlotDisplayName(slot: SlotName): string {
    const names: Record<SlotName, string> = {
        ceiling: "Ceiling",
        center: "Center",
        rig_low: "Rig Low",
        rig_upper: "Rig Upper",
        floor: "Floor",
    };
    return names[slot] || slot;
}

/* ------------------------------------------------------------------ */
/*  Camera enumeration                                                 */
/* ------------------------------------------------------------------ */

const SLOT_ORDER: SlotName[] = ["ceiling", "rig_upper", "center", "rig_low", "floor"];

/**
 * Return a flat list of every camera in the layout together with its
 * pillar / slot context.
 */
export function getAllCamerasFromLayout(): CameraEntry[] {
    const entries: CameraEntry[] = [];
    for (const pillarKey of getPillarKeys()) {
        const pillar = systemLayout.positions[pillarKey];
        const pillarIndex = getPillarNumber(pillarKey);
        for (const slot of SLOT_ORDER) {
            const cameras = pillar[slot];
            if (!cameras) continue;
            cameras.forEach((shorthand, slotIndex) => {
                entries.push({ shorthand, pillarKey, pillarIndex, slot, slotIndex });
            });
        }
    }
    return entries;
}

/* ------------------------------------------------------------------ */
/*  Camera resolution (shorthand → server+camera index)                */
/* ------------------------------------------------------------------ */

/**
 * Build a lookup map from camera shorthand → { serverIndex, cameraIndex }
 * by reading each capture server's `cam_shorthands`.
 */
export function buildShorthandMap(): Map<string, { serverIndex: number; cameraIndex: number }> {
    const map = new Map<string, { serverIndex: number; cameraIndex: number }>();
    const servers = getServers();
    for (let si = 0; si < servers.servers.length; si++) {
        const state = servers.getServer(si).socket.getCurrentCamToolState();
        if (!state?.serial_numbers?.cam_shorthands) continue;
        const shorthands = state.serial_numbers.cam_shorthands;
        for (const [camIdx, sh] of Object.entries(shorthands)) {
            map.set(sh, { serverIndex: si, cameraIndex: Number(camIdx) });
        }
    }
    return map;
}

/**
 * Resolve a CameraEntry to a server+camera pair using the shorthand map.
 * Returns undefined if no matching camera is found on any server.
 */
export function resolveCamera(
    entry: CameraEntry,
    shorthandMap: Map<string, { serverIndex: number; cameraIndex: number }>
): ResolvedCamera | undefined {
    const match = shorthandMap.get(entry.shorthand);
    if (!match) return undefined;
    return { ...entry, ...match };
}

/**
 * Get cameras from layout that belong to a specific server index.
 */
export function getCamerasForServer(
    serverIndex: number,
    shorthandMap: Map<string, { serverIndex: number; cameraIndex: number }>
): ResolvedCamera[] {
    return getAllCamerasFromLayout()
        .map(e => resolveCamera(e, shorthandMap))
        .filter((c): c is ResolvedCamera => c !== undefined && c.serverIndex === serverIndex);
}
