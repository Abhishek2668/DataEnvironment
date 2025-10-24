import { API_BASE } from "./api";

type Unsubscribe = () => void;

type MessageHandler<T> = (data: T) => void;

interface SSEOptions {
  onOpen?: () => void;
  onError?: (event?: Event) => void;
}

export function subscribeSSE<T = unknown>(
  path: string,
  onMessage: MessageHandler<T>,
  options: SSEOptions = {}
): Unsubscribe {
  const url = path.startsWith("http") ? path : `${API_BASE}${path}`;
  let closed = false;
  let eventSource = new EventSource(url);

  const handleMessage = (event: MessageEvent) => {
    try {
      const payload = JSON.parse(event.data);
      onMessage(payload as T);
    } catch (error) {
      console.error("Failed to parse SSE payload", error);
    }
  };

  const handleOpen = () => {
    options.onOpen?.();
  };

  const reconnect = () => {
    if (closed) {
      return;
    }
    if (eventSource.readyState !== EventSource.CLOSED) {
      eventSource.close();
    }
    eventSource = new EventSource(url);
    eventSource.onmessage = handleMessage;
    eventSource.onerror = handleError;
    eventSource.onopen = handleOpen;
  };

  const handleError = (event: Event) => {
    options.onError?.(event);
    eventSource.close();
    setTimeout(reconnect, 1500);
  };

  eventSource.onmessage = handleMessage;
  eventSource.onerror = handleError;
  eventSource.onopen = handleOpen;

  return () => {
    closed = true;
    eventSource.close();
  };
}

export type { SSEOptions };
