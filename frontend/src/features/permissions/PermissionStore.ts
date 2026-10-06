import { useSyncExternalStore } from 'react';
import type { PermissionRequestData } from '../../protocol/websocket';

export interface PermissionGatewayState {
  pendingRequests: PermissionRequestData[];
  currentRequest: PermissionRequestData | null;
  historyRequests: PermissionRequestData[];
  modalOpen: boolean;
}

export interface PermissionGatewayStore extends PermissionGatewayState {
  setPendingRequests: (requests: PermissionRequestData[]) => void;
  addRequest: (request: PermissionRequestData) => void;
  updateRequest: (request: PermissionRequestData) => void;
  setCurrentRequest: (request: PermissionRequestData | null) => void;
  setModalOpen: (open: boolean) => void;
  removeRequest: (requestId: string) => void;
  markApproved: (requestId: string, request?: PermissionRequestData) => void;
  markDenied: (requestId: string, request?: PermissionRequestData) => void;
  markExpired: (requestId: string) => void;
}

type Listener = () => void;

class PermissionStoreManager {
  private state: PermissionGatewayState = {
    pendingRequests: [],
    currentRequest: null,
    historyRequests: [],
    modalOpen: false,
  };

  private listeners = new Set<Listener>();

  public subscribe = (listener: Listener): (() => void) => {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  };

  public getSnapshot = (): PermissionGatewayState => {
    return this.state;
  };

  private notify() {
    this.listeners.forEach((l) => l());
  }

  public getState(): PermissionGatewayStore {
    return {
      ...this.state,
      setPendingRequests: this.setPendingRequests,
      addRequest: this.addRequest,
      updateRequest: this.updateRequest,
      setCurrentRequest: this.setCurrentRequest,
      setModalOpen: this.setModalOpen,
      removeRequest: this.removeRequest,
      markApproved: this.markApproved,
      markDenied: this.markDenied,
      markExpired: this.markExpired,
    };
  }

  public setPendingRequests = (requests: PermissionRequestData[]) => {
    this.state = {
      ...this.state,
      pendingRequests: requests,
      currentRequest: requests.length > 0 ? requests[0] : null,
      modalOpen: requests.length > 0,
    };
    this.notify();
  };

  public addRequest = (request: PermissionRequestData) => {
    const exists = this.state.pendingRequests.some((r) => r.request_id === request.request_id);
    if (exists) {
      this.state = {
        ...this.state,
        pendingRequests: this.state.pendingRequests.map((r) =>
          r.request_id === request.request_id ? request : r
        ),
        currentRequest:
          this.state.currentRequest?.request_id === request.request_id
            ? request
            : this.state.currentRequest,
      };
    } else {
      const updated = [...this.state.pendingRequests, request];
      this.state = {
        ...this.state,
        pendingRequests: updated,
        currentRequest: this.state.currentRequest || request,
        modalOpen: true,
      };
    }
    this.notify();
  };

  public updateRequest = (request: PermissionRequestData) => {
    this.state = {
      ...this.state,
      pendingRequests: this.state.pendingRequests.map((r) =>
        r.request_id === request.request_id ? request : r
      ),
      currentRequest:
        this.state.currentRequest?.request_id === request.request_id
          ? request
          : this.state.currentRequest,
    };
    this.notify();
  };

  public setCurrentRequest = (request: PermissionRequestData | null) => {
    this.state = {
      ...this.state,
      currentRequest: request,
      modalOpen: request !== null,
    };
    this.notify();
  };

  public setModalOpen = (open: boolean) => {
    this.state = {
      ...this.state,
      modalOpen: open,
    };
    this.notify();
  };

  public removeRequest = (requestId: string) => {
    const remaining = this.state.pendingRequests.filter((r) => r.request_id !== requestId);
    this.state = {
      ...this.state,
      pendingRequests: remaining,
      currentRequest: remaining.length > 0 ? remaining[0] : null,
      modalOpen: remaining.length > 0,
    };
    this.notify();
  };

  public markApproved = (requestId: string, updatedRequest?: PermissionRequestData) => {
    const target =
      updatedRequest ||
      this.state.pendingRequests.find((r) => r.request_id === requestId);
    const remaining = this.state.pendingRequests.filter((r) => r.request_id !== requestId);
    this.state = {
      ...this.state,
      pendingRequests: remaining,
      currentRequest: remaining.length > 0 ? remaining[0] : null,
      modalOpen: remaining.length > 0,
      historyRequests: target ? [target, ...this.state.historyRequests] : this.state.historyRequests,
    };
    this.notify();
  };

  public markDenied = (requestId: string, updatedRequest?: PermissionRequestData) => {
    const target =
      updatedRequest ||
      this.state.pendingRequests.find((r) => r.request_id === requestId);
    const remaining = this.state.pendingRequests.filter((r) => r.request_id !== requestId);
    this.state = {
      ...this.state,
      pendingRequests: remaining,
      currentRequest: remaining.length > 0 ? remaining[0] : null,
      modalOpen: remaining.length > 0,
      historyRequests: target ? [target, ...this.state.historyRequests] : this.state.historyRequests,
    };
    this.notify();
  };

  public markExpired = (requestId: string) => {
    const remaining = this.state.pendingRequests.filter((r) => r.request_id !== requestId);
    this.state = {
      ...this.state,
      pendingRequests: remaining,
      currentRequest: remaining.length > 0 ? remaining[0] : null,
      modalOpen: remaining.length > 0,
    };
    this.notify();
  };
}

export const permissionStore = new PermissionStoreManager();

export function usePermissionStore(): PermissionGatewayStore {
  const state = useSyncExternalStore(permissionStore.subscribe, permissionStore.getSnapshot);
  return {
    ...state,
    setPendingRequests: permissionStore.setPendingRequests,
    addRequest: permissionStore.addRequest,
    updateRequest: permissionStore.updateRequest,
    setCurrentRequest: permissionStore.setCurrentRequest,
    setModalOpen: permissionStore.setModalOpen,
    removeRequest: permissionStore.removeRequest,
    markApproved: permissionStore.markApproved,
    markDenied: permissionStore.markDenied,
    markExpired: permissionStore.markExpired,
  };
}

usePermissionStore.getState = () => permissionStore.getState();

if (typeof window !== 'undefined') {
  (window as any).__JARVIS_PERMISSION_STORE__ = permissionStore;
}
