import { useSyncExternalStore } from 'react';
import type {
  MissionData,
  MissionSnapshot,
  CanonicalMissionEvent,
} from '../../../protocol/websocket';

export type ConnectionStatus = 'CONNECTED' | 'RECONNECTING' | 'OFFLINE';

export type MissionUiStateCategory =
  | 'NO_MISSIONS'
  | 'LOADING_MISSIONS'
  | 'SYNCING_MISSIONS'
  | 'CONNECTED'
  | 'RECONNECTING'
  | 'OFFLINE'
  | 'MISSION_ACTIVE'
  | 'MISSION_COMPLETED'
  | 'MISSION_FAILED'
  | 'MISSION_CANCELLED'
  | 'MISSION_REMOVED';

export interface MissionMetrics {
  mission_state_sync_latency_ms: number;
  mission_event_delivery_latency_ms: number;
  mission_event_gap_count: number;
  mission_event_duplicate_count: number;
  mission_reconciliation_count: number;
  mission_reconnect_count: number;
  mission_stale_count: number;
  mission_cancel_latency_ms: number;
}

export interface MissionRuntimeState {
  missions: MissionData[];
  selectedMissionId: string | null;
  selectedMission: MissionData | null;
  selectedMissionSnapshot: MissionSnapshot | null;
  connectionState: ConnectionStatus;
  lastServerSyncAt: number;
  lastEventAt: Record<string, number>;
  lastEventSequence: Record<string, number>;
  filterProjectId: string;
  isSyncing: boolean;
  events: CanonicalMissionEvent[];
  metrics: MissionMetrics;
}

type Listener = () => void;

class MissionRuntimeStore {
  private state: MissionRuntimeState = {
    missions: [],
    selectedMissionId: null,
    selectedMission: null,
    selectedMissionSnapshot: null,
    connectionState: 'OFFLINE',
    lastServerSyncAt: 0,
    lastEventAt: {},
    lastEventSequence: {},
    filterProjectId: 'ALL',
    isSyncing: false,
    events: [],
    metrics: {
      mission_state_sync_latency_ms: 0,
      mission_event_delivery_latency_ms: 0,
      mission_event_gap_count: 0,
      mission_event_duplicate_count: 0,
      mission_reconciliation_count: 0,
      mission_reconnect_count: 0,
      mission_stale_count: 0,
      mission_cancel_latency_ms: 0,
    },
  };

  private listeners = new Set<Listener>();
  private gapRecoveryHandler: ((projectId: string, missionId: string) => void) | null = null;
  private cancelStartTimes = new Map<string, number>();

  public subscribe = (listener: Listener): (() => void) => {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  };

  public getSnapshot = (): MissionRuntimeState => {
    return this.state;
  };

  private notify() {
    this.listeners.forEach((l) => l());
  }

  public registerGapRecoveryHandler(handler: (projectId: string, missionId: string) => void) {
    this.gapRecoveryHandler = handler;
  }

  public setConnectionState(connectionState: ConnectionStatus) {
    if (this.state.connectionState === connectionState) return;
    const isReconnected =
      (this.state.connectionState === 'OFFLINE' || this.state.connectionState === 'RECONNECTING') &&
      connectionState === 'CONNECTED';

    this.state = {
      ...this.state,
      connectionState,
      metrics: {
        ...this.state.metrics,
        mission_reconnect_count: isReconnected
          ? this.state.metrics.mission_reconnect_count + 1
          : this.state.metrics.mission_reconnect_count,
      },
    };
    this.notify();
  }

  public setFilterProjectId(projectId: string) {
    const trimmed = (projectId || 'ALL').trim();
    if (this.state.filterProjectId === trimmed) return;
    this.state = {
      ...this.state,
      filterProjectId: trimmed,
    };
    this.notify();
  }

  public setSelectedMissionId(missionId: string | null) {
    const selected = missionId ? this.state.missions.find((m) => m.mission_id === missionId) || null : null;
    this.state = {
      ...this.state,
      selectedMissionId: missionId,
      selectedMission: selected,
    };
    this.notify();
  }

  public setMissionSnapshot(snapshot: MissionSnapshot | null) {
    if (!snapshot) {
      this.state = { ...this.state, selectedMissionSnapshot: null };
      this.notify();
      return;
    }
    const mission = snapshot.mission;
    const now = Date.now();
    const mid = mission.mission_id;
    const existingSeq = this.state.lastEventSequence[mid] || 0;
    const newSeq = Math.max(existingSeq, mission.last_event_sequence || mission.version || 1);

    // Update in missions list as well
    const updatedMissions = this.state.missions.map((m) =>
      m.mission_id === mid ? { ...m, ...mission } : m
    );
    if (!updatedMissions.some((m) => m.mission_id === mid)) {
      updatedMissions.unshift(mission);
    }

    this.state = {
      ...this.state,
      missions: updatedMissions,
      selectedMissionSnapshot: snapshot,
      selectedMission: mid === this.state.selectedMissionId ? mission : this.state.selectedMission,
      isSyncing: false,
      lastEventAt: {
        ...this.state.lastEventAt,
        [mid]: now,
      },
      lastEventSequence: {
        ...this.state.lastEventSequence,
        [mid]: newSeq,
      },
      metrics: {
        ...this.state.metrics,
        mission_reconciliation_count: this.state.metrics.mission_reconciliation_count + 1,
      },
    };
    this.notify();
  }

  public setMissions(missions: MissionData[]) {
    const now = Date.now();
    const lastEventAt = { ...this.state.lastEventAt };
    const lastEventSeq = { ...this.state.lastEventSequence };

    missions.forEach((m) => {
      const mid = m.mission_id;
      if (!lastEventAt[mid]) {
        lastEventAt[mid] = m.last_event_at ? m.last_event_at * 1000 : (Date.parse(m.updated_at) || now);
      }
      if (!lastEventSeq[mid]) {
        lastEventSeq[mid] = m.last_event_sequence || m.version || 1;
      }
    });

    const selectedMission = this.state.selectedMissionId
      ? missions.find((m) => m.mission_id === this.state.selectedMissionId) || null
      : null;

    this.state = {
      ...this.state,
      missions,
      selectedMission,
      lastServerSyncAt: now,
      lastEventAt,
      lastEventSequence: lastEventSeq,
      isSyncing: false,
    };
    this.notify();
  }

  public recordCancelStart(missionId: string) {
    this.cancelStartTimes.set(missionId, Date.now());
  }

  public applyEvent(
    event: CanonicalMissionEvent,
    triggerSnapshot?: (projectId: string, missionId: string) => void
  ): 'APPLIED' | 'DEDUPLICATED' | 'IGNORED' | 'GAP_DETECTED' {
    const mid = event.mission_id;
    const now = Date.now();
    const eventTime = event.timestamp ? event.timestamp * 1000 : now;
    const deliveryLatency = Math.max(0, now - eventTime);

    // Sequence checking
    const lastSeq = this.state.lastEventSequence[mid] || 0;
    const eventSeq = event.sequence;

    // Special case for non-sequenced system events
    if (eventSeq > 0) {
      if (eventSeq < lastSeq) {
        this.state = {
          ...this.state,
          metrics: {
            ...this.state.metrics,
            mission_event_duplicate_count: this.state.metrics.mission_event_duplicate_count + 1,
          },
        };
        this.notify();
        return 'IGNORED';
      }
      if (eventSeq === lastSeq) {
        this.state = {
          ...this.state,
          metrics: {
            ...this.state.metrics,
            mission_event_duplicate_count: this.state.metrics.mission_event_duplicate_count + 1,
          },
        };
        this.notify();
        return 'DEDUPLICATED';
      }
      if (eventSeq > lastSeq + 1 && lastSeq > 0) {
        // STATE GAP DETECTED
        this.state = {
          ...this.state,
          isSyncing: true,
          metrics: {
            ...this.state.metrics,
            mission_event_gap_count: this.state.metrics.mission_event_gap_count + 1,
          },
        };
        this.notify();
        const handler = triggerSnapshot || this.gapRecoveryHandler;
        if (handler) {
          handler(event.project_id, event.mission_id);
        }
        return 'GAP_DETECTED';
      }
    }

    // APPLY EVENT
    let cancelLatency = this.state.metrics.mission_cancel_latency_ms;
    if (event.event_type === 'mission.cancelled' && this.cancelStartTimes.has(mid)) {
      const startTime = this.cancelStartTimes.get(mid)!;
      cancelLatency = Math.max(0, now - startTime);
      this.cancelStartTimes.delete(mid);
    }

    // Update mission in list
    const payload = event.payload || {};
    let updatedMissions = this.state.missions.map((m) => {
      if (m.mission_id !== mid) return m;
      return {
        ...m,
        status: (payload.status as string) || m.status,
        progress: typeof payload.progress === 'number' ? (payload.progress as number) : m.progress,
        current_stage: (payload.current_stage as string) || m.current_stage,
        updated_at: new Date(now).toISOString(),
        last_event_at: now,
        last_event_sequence: eventSeq > 0 ? eventSeq : (m.last_event_sequence || 0) + 1,
      };
    });

    // If mission was deleted
    if (event.event_type === 'mission.deleted' || payload.status === 'REMOVED') {
      updatedMissions = updatedMissions.filter((m) => m.mission_id !== mid);
    }

    // Update selected mission if matches
    const selectedMission =
      this.state.selectedMissionId === mid
        ? updatedMissions.find((m) => m.mission_id === mid) || null
        : this.state.selectedMission;

    this.state = {
      ...this.state,
      missions: updatedMissions,
      selectedMission,
      events: [event, ...this.state.events.slice(0, 99)],
      lastEventAt: {
        ...this.state.lastEventAt,
        [mid]: now,
      },
      lastEventSequence: {
        ...this.state.lastEventSequence,
        [mid]: eventSeq > 0 ? eventSeq : lastSeq + 1,
      },
      metrics: {
        ...this.state.metrics,
        mission_event_delivery_latency_ms: deliveryLatency,
        mission_cancel_latency_ms: cancelLatency,
      },
    };
    this.notify();
    return 'APPLIED';
  }

  public removeMission(missionId: string) {
    const filtered = this.state.missions.filter((m) => m.mission_id !== missionId);
    this.state = {
      ...this.state,
      missions: filtered,
      selectedMissionId: this.state.selectedMissionId === missionId ? null : this.state.selectedMissionId,
      selectedMission: this.state.selectedMissionId === missionId ? null : this.state.selectedMission,
    };
    this.notify();
  }

  public isStale(mission: MissionData, thresholdMs = 15000): boolean {
    const s = (mission.status || '').toUpperCase();
    if (s !== 'RUNNING' && s !== 'CANCELLING') return false;
    const now = Date.now();
    const lastAt =
      this.state.lastEventAt[mission.mission_id] ||
      (mission.last_event_at ? mission.last_event_at * 1000 : 0) ||
      Date.parse(mission.updated_at) ||
      0;
    if (lastAt === 0) return false;
    return now - lastAt > thresholdMs;
  }
}

export const missionRuntimeStore = new MissionRuntimeStore();

export function useMissionRuntimeStore(): MissionRuntimeState {
  return useSyncExternalStore(
    missionRuntimeStore.subscribe,
    missionRuntimeStore.getSnapshot,
    missionRuntimeStore.getSnapshot
  );
}
