import { apiRequest } from "./apiClient";
import type { TokenResponse } from "../shared/types";

export async function loginWithPin(pin: string): Promise<TokenResponse> {
  return apiRequest<TokenResponse>("/auth/pin-login", {
    method: "POST",
    body: { pin },
  });
}
