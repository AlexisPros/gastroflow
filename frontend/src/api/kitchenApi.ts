import { apiRequest } from "./apiClient";

export type KitchenTask = {
  id: number;
  order_item_id: number;
  kitchen_section_id: number;
  product_kitchen_step_id: number | null;
  assigned_user_id: number | null;
  status: "NEW" | "PENDING" | "IN_PROGRESS" | "COMPLETED";
  estimated_time: number | null;
  started_at: string | null;
  completed_at: string | null;
  step_name: string | null;
  step_description: string | null;
};

export type KitchenOrderItem = {
  id: number;
  product_id: number;
  product_name: string;
  quantity: number;
  notes: string | null;
  course_number: number;
  status: string;
  kitchen_tasks: KitchenTask[];
};

export type KitchenOrder = {
  id: number;
  table_id: number | null;
  table_number: string | null;
  waiter_name: string | null;
  created_at: string;
  status: string;
  estimated_time: number | null;
  items: KitchenOrderItem[];
};

export type KitchenSectionTask = {
  id: number;
  order_id: number;
  order_item_id: number;
  kitchen_section_id: number;
  order_created_at: string;
  order_estimated_time: number | null;
  table_number: string | null;
  product_name: string;
  quantity: number;
  notes: string | null;
  course_number: number;
  status: "NEW" | "PENDING" | "IN_PROGRESS" | "COMPLETED";
  estimated_time: number | null;
  step_name: string | null;
  step_description: string | null;
  step_sequence: number | null;
  depends_on_sequence: number | null;
  can_start: boolean;
  blocked_by_step_name: string | null;
  started_at: string | null;
  completed_at: string | null;
};

export async function getActiveKitchenOrders(token: string): Promise<KitchenOrder[]> {
  return apiRequest<KitchenOrder[]>("/kitchen/orders/active", { token });
}

export async function acceptKitchenOrder(token: string, orderId: number): Promise<{ success: boolean }> {
  return apiRequest<{ success: boolean }>(`/kitchen/orders/${orderId}/accept`, {
    method: "POST",
    token,
  });
}

export async function completeKitchenOrder(token: string, orderId: number): Promise<{ success: boolean }> {
  return apiRequest<{ success: boolean }>(`/kitchen/orders/${orderId}/complete`, {
    method: "POST",
    token,
  });
}

export async function getActiveSectionTasks(
  token: string,
  sectionId?: number,
): Promise<KitchenSectionTask[]> {
  const query = sectionId !== undefined ? `?section_id=${sectionId}` : "";
  return apiRequest<KitchenSectionTask[]>(`/kitchen/tasks/active${query}`, { token });
}

export async function startKitchenTask(token: string, taskId: number): Promise<KitchenTask> {
  return apiRequest<KitchenTask>(`/kitchen-tasks/${taskId}/start`, {
    method: "POST",
    token,
  });
}

export async function completeKitchenTask(token: string, taskId: number): Promise<KitchenTask> {
  return apiRequest<KitchenTask>(`/kitchen-tasks/${taskId}/complete`, {
    method: "POST",
    token,
  });
}

export type KitchenSection = {
  id: number;
  name: string;
};

export async function getKitchenSections(token: string): Promise<KitchenSection[]> {
  return apiRequest<KitchenSection[]>("/kitchen-sections", { token });
}
