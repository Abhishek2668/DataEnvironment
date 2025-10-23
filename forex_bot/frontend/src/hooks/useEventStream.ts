import { useEffect } from "react";
import { subscribeSSE } from "../lib/sse";

type Handler<T> = (data: T) => void;

export function useEventStream<T>(path: string, handler: Handler<T>) {
  useEffect(() => {
    const unsubscribe = subscribeSSE<T>(path, handler);
    return () => unsubscribe();
  }, [path, handler]);
}
