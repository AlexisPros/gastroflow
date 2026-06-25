export type UserRole = "ADMIN" | "MANAGER" | "WAITER" | "KITCHEN" | "CHEF" | "WYDAWKA" | "BARTENDER";

export type User = {
  id: number;
  first_name: string;
  last_name: string;
  email: string;
  role: UserRole;
  kitchen_section_id?: number | null;
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

export type WebSocketChannel = "waiters" | "kitchen" | "bar" | "floor" | "managers" | "public_qr";

export type WebSocketMessage<TData = unknown> = {
  event: string;
  data: TData;
};
