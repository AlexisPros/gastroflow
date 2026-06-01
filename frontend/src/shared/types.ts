export type UserRole = "ADMIN" | "MANAGER" | "WAITER" | "KITCHEN" | "BARTENDER";

export type User = {
  id: number;
  first_name: string;
  last_name: string;
  email: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
};

export type TokenResponse = {
  access_token: string;
  token_type: string;
  user: User;
};

export type ApiErrorBody = {
  detail?: string | { msg?: string }[];
};

export type WebSocketChannel = "waiters" | "kitchen" | "bar" | "floor" | "managers";

export type WebSocketMessage<TData = unknown> = {
  event: string;
  data: TData;
};
