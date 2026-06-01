import { apiRequest } from "./apiClient";
import type { TokenResponse } from "../shared/types";

export async function loginWithPassword(
  username: string,
  password: string,
): Promise<TokenResponse> {
  const formData = new FormData();
  formData.set("username", username);
  formData.set("password", password);

  return apiRequest<TokenResponse>("/auth/token", {
    method: "POST",
    body: formData,
  });
}
