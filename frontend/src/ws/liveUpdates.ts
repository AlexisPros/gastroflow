import { WS_BASE_URL } from "../shared/config";
import type { WebSocketChannel, WebSocketMessage } from "../shared/types";

type LiveUpdatesOptions = {
  channel: WebSocketChannel;
  token: string;
  onMessage: (message: WebSocketMessage) => void;
  onStatusChange?: (status: "connecting" | "connected" | "disconnected") => void;
};

export function connectLiveUpdates(options: LiveUpdatesOptions): () => void {
  let socket: WebSocket | null = null;
  let reconnectTimer: number | undefined;
  let shouldReconnect = true;

  const connect = () => {
    options.onStatusChange?.("connecting");
    socket = new WebSocket(
      `${WS_BASE_URL}/ws/${options.channel}?token=${encodeURIComponent(options.token)}`,
    );

    socket.onopen = () => {
      options.onStatusChange?.("connected");
    };

    socket.onmessage = (event) => {
      try {
        options.onMessage(JSON.parse(event.data) as WebSocketMessage);
      } catch {
        options.onMessage({ event: "raw_message", data: event.data });
      }
    };

    socket.onclose = () => {
      options.onStatusChange?.("disconnected");
      if (shouldReconnect) {
        reconnectTimer = window.setTimeout(connect, 1500);
      }
    };
  };

  connect();

  return () => {
    shouldReconnect = false;
    if (reconnectTimer !== undefined) {
      window.clearTimeout(reconnectTimer);
    }
    socket?.close();
  };
}
