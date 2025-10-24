import { useEffect } from "react";
import { SSEOptions, subscribeSSE } from "../lib/sse";

type Handler<T> = (data: T) => void;

export function useEventStream<T>(path: string, handler: Handler<T>, options?: SSEOptions) {
  useEffect(() => {
    const unsubscribe = subscribeSSE<T>(path, handler, options);
    return () => unsubscribe();
  }, [path, handler, options]);
}
