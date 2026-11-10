type EventCallback = (data: any) => void;

class WebSocketClient {
  private socket: WebSocket | null = null;
  private listeners: Map<string, Set<EventCallback>> = new Map();
  private reconnectInterval = 3000;
  private shouldReconnect = true;
  private isConnecting = false;

  public connect(userId?: string) {
    if (this.socket && (this.socket.readyState === WebSocket.OPEN || this.socket.readyState === WebSocket.CONNECTING)) {
      return;
    }

    this.isConnecting = true;
    const wsBase = import.meta.env.VITE_WS_URL as string | undefined;
    let url: string;
    if (wsBase) {
      const cleanBase = wsBase.replace(/\/$/, '');
      url = userId ? `${cleanBase}/ws/${userId}` : `${cleanBase}/ws`;
    } else {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const host = window.location.host;
      url = userId ? `${protocol}//${host}/ws/${userId}` : `${protocol}//${host}/ws`;
    }

    try {
      this.socket = new WebSocket(url);

      this.socket.onopen = () => {
        this.isConnecting = false;
        console.log('[WebSocket] Connected to ResolveGrid real-time stream.');
        this.emit('_connected', { status: true });
      };

      this.socket.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          if (payload.event) {
            this.emit(payload.event, payload.data);
          }
          this.emit('*', payload);
        } catch (e) {
          console.warn('[WebSocket] Non-JSON payload received:', event.data);
        }
      };

      this.socket.onclose = () => {
        this.isConnecting = false;
        this.emit('_disconnected', { status: false });
        if (this.shouldReconnect) {
          setTimeout(() => this.connect(userId), this.reconnectInterval);
        }
      };

      this.socket.onerror = (err) => {
        console.warn('[WebSocket] Error:', err);
      };
    } catch (e) {
      this.isConnecting = false;
      if (this.shouldReconnect) {
        setTimeout(() => this.connect(userId), this.reconnectInterval);
      }
    }
  }

  public disconnect() {
    this.shouldReconnect = false;
    if (this.socket) {
      this.socket.close();
    }
  }

  public on(event: string, callback: EventCallback) {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set());
    }
    this.listeners.get(event)!.add(callback);
    return () => this.off(event, callback);
  }

  public off(event: string, callback: EventCallback) {
    if (this.listeners.has(event)) {
      this.listeners.get(event)!.delete(callback);
    }
  }

  private emit(event: string, data: any) {
    if (this.listeners.has(event)) {
      this.listeners.get(event)!.forEach((cb) => cb(data));
    }
  }
}

export const wsClient = new WebSocketClient();
