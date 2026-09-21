export interface StreamEvent<T = unknown> {
  event: string;
  data: T;
  id?: string;
}

type Listener = (event: StreamEvent) => void;

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api/v2";

export class SessionEventStream {
  private source?: EventSource;
  private listeners = new Set<Listener>();

  connect(sessionId: string): void {
    this.close();
    const url = `${API_BASE_URL}/sessions/${encodeURIComponent(sessionId)}/events`;
    this.source = new EventSource(url);

    const forward = (event: MessageEvent<string>) => {
      let data: unknown = event.data;
      try {
        data = JSON.parse(event.data);
      } catch {
        // Text events are valid too.
      }
      const next = { event: event.type, data, id: event.lastEventId || undefined };
      this.listeners.forEach((listener) => listener(next));
    };

    this.source.onmessage = forward;
    ["signal", "decision", "risk", "order", "session", "bar"].forEach((name) => {
      this.source?.addEventListener(name, forward as EventListener);
    });
  }

  subscribe(listener: Listener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  close(): void {
    this.source?.close();
    this.source = undefined;
  }
}
