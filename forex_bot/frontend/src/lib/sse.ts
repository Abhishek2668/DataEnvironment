import { API_BASE } from "./api";

type Unsubscribe = () => void;

type MessageHandler<T> = (data: T) => void;

export function subscribeSSE<T = unknown>(path: string, onMessage: MessageHandler<T>): Unsubscribe {
  const url = `${API_BASE}${path}`;
  let eventSource = new EventSource(url);

  const reconnect = () => {
    if (eventSource.readyState === EventSource.CLOSED) {
      eventSource.close();
    }
    eventSource = new EventSource(url);
    eventSource.onmessage = handleMessage;
    eventSource.onerror = handleError;
  };

  const handleMessage = (event: MessageEvent) => {
    try {
      const payload = JSON.parse(event.data);
      onMessage(payload as T);
    } catch (error) {
      console.error("Failed to parse SSE payload", error);
    }
  };

  const handleError = () => {
    eventSource.close();
    setTimeout(reconnect, 1500);
  };

  eventSource.onmessage = handleMessage;
  eventSource.onerror = handleError;

  return () => eventSource.close();
}
