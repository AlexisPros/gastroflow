import { apiRequest } from "./apiClient";

export type PublicQrTable = {
  id: number;
  table_number: string;
  status: string;
  qr_code_url: string | null;
  is_active: boolean;
};

export async function getPublicQrTable(qrToken: string): Promise<PublicQrTable> {
  return apiRequest<PublicQrTable>(`/qr/${encodeURIComponent(qrToken)}/table`);
}
