import { apiRequest } from "./apiClient";

export type FloorPlan = {
  id: number;
  name: string;
  width: number;
  height: number;
  background_image_url: string | null;
  is_active: boolean;
  created_at: string;
};

export type FloorPlanTable = {
  id: number;
  floor_plan_id: number;
  table_id: number;
  x: string;
  y: string;
  width: string;
  height: string;
  rotation: string;
  shape: "RECTANGLE" | "CIRCLE" | string;
};

export type FloorPlanDecoration = {
  id: number;
  floor_plan_id: number;
  x: string;
  y: string;
  width: string;
  height: string;
  rotation: string;
  shape: "RECTANGLE" | "CIRCLE" | string;
  color: string;
  label: string | null;
};

export type RestaurantTableStatus =
  | "FREE"
  | "PENDING_ORDER"
  | "OCCUPIED"
  | "RESERVED"
  | string;

export type RestaurantTable = {
  id: number;
  table_number: string;
  current_guests: number | null;
  status: RestaurantTableStatus;
  qr_code_url: string | null;
  qr_token: string | null;
  is_active: boolean;
};

export type FloorTableView = FloorPlanTable & {
  table: RestaurantTable | null;
};

export type FloorPlanTablePositionInput = {
  x: number;
  y: number;
  width: number;
  height: number;
  rotation?: number;
  shape?: "RECTANGLE" | "CIRCLE";
};

export async function getActiveFloorPlan(token: string): Promise<FloorPlan> {
  return apiRequest<FloorPlan>("/floor-plans/active", { token });
}

export async function getFloorPlans(token: string): Promise<FloorPlan[]> {
  return apiRequest<FloorPlan[]>("/floor-plans", { token });
}

export async function getFloorPlan(token: string, floorPlanId: number): Promise<FloorPlan> {
  return apiRequest<FloorPlan>(`/floor-plans/${floorPlanId}`, { token });
}

export async function createFloorPlan(
  token: string,
  body: { name: string; width?: number; height?: number; is_active?: boolean }
): Promise<FloorPlan> {
  return apiRequest<FloorPlan>("/floor-plans", {
    method: "POST",
    token,
    body,
  });
}

export async function updateFloorPlan(
  token: string,
  floorPlanId: number,
  body: { name?: string; width?: number; height?: number; is_active?: boolean }
): Promise<FloorPlan> {
  return apiRequest<FloorPlan>(`/floor-plans/${floorPlanId}`, {
    method: "PATCH",
    token,
    body,
  });
}

export async function deleteFloorPlan(token: string, floorPlanId: number): Promise<void> {
  await apiRequest(`/floor-plans/${floorPlanId}`, {
    method: "DELETE",
    token,
  });
}

export async function getFloorPlanTables(
  token: string,
  floorPlanId: number,
): Promise<FloorPlanTable[]> {
  return apiRequest<FloorPlanTable[]>(`/floor-plans/${floorPlanId}/tables`, {
    token,
  });
}

export async function getRestaurantTables(token: string): Promise<RestaurantTable[]> {
  return apiRequest<RestaurantTable[]>("/restaurant-tables", { token });
}

export async function getFloorPlanDecorations(
  token: string,
  floorPlanId: number,
): Promise<FloorPlanDecoration[]> {
  return apiRequest<FloorPlanDecoration[]>(
    `/floor-plans/${floorPlanId}/decorations`,
    { token },
  );
}

export async function createRestaurantTableOnFloorPlan(
  token: string,
  floorPlanId: number,
  body: {
    table_number: string;
    current_guests?: number | null;
    is_active?: boolean;
    position: FloorPlanTablePositionInput;
  },
): Promise<FloorPlanTable> {
  return apiRequest<FloorPlanTable>(
    `/floor-plans/${floorPlanId}/tables/create-restaurant-table`,
    {
      method: "POST",
      token,
      body,
    },
  );
}

export async function updateFloorPlanTablePosition(
  token: string,
  floorPlanId: number,
  floorPlanTableId: number,
  position: FloorPlanTablePositionInput,
): Promise<FloorPlanTable> {
  return apiRequest<FloorPlanTable>(
    `/floor-plans/${floorPlanId}/tables/${floorPlanTableId}/position`,
    {
      method: "PATCH",
      token,
      body: position,
    },
  );
}

export async function deleteFloorPlanTable(
  token: string,
  floorPlanId: number,
  floorPlanTableId: number,
): Promise<FloorPlanTable> {
  return apiRequest<FloorPlanTable>(
    `/floor-plans/${floorPlanId}/tables/${floorPlanTableId}`,
    {
      method: "DELETE",
      token,
    },
  );
}

export async function deleteRestaurantTable(
  token: string,
  tableId: number,
): Promise<RestaurantTable> {
  return apiRequest<RestaurantTable>(`/restaurant-tables/${tableId}`, {
    method: "DELETE",
    token,
  });
}

export async function updateRestaurantTable(
  token: string,
  tableId: number,
  body: Partial<{
    table_number: string;
    current_guests: number | null;
    status: RestaurantTableStatus;
    qr_code_url: string | null;
    qr_token: string | null;
    is_active: boolean;
  }>,
): Promise<RestaurantTable> {
  return apiRequest<RestaurantTable>(`/restaurant-tables/${tableId}`, {
    method: "PATCH",
    token,
    body,
  });
}

export async function createFloorPlanDecoration(
  token: string,
  floorPlanId: number,
  body: {
    floor_plan_id: number;
    x: number;
    y: number;
    width: number;
    height: number;
    rotation?: number;
    shape?: "RECTANGLE" | "CIRCLE";
    color?: string;
    label?: string | null;
  },
): Promise<FloorPlanDecoration> {
  return apiRequest<FloorPlanDecoration>(
    `/floor-plans/${floorPlanId}/decorations`,
    {
      method: "POST",
      token,
      body,
    },
  );
}

export async function updateFloorPlanDecoration(
  token: string,
  floorPlanId: number,
  decorationId: number,
  body: Partial<{
    x: number;
    y: number;
    width: number;
    height: number;
    rotation: number;
    shape: "RECTANGLE" | "CIRCLE";
    color: string;
    label: string | null;
  }>,
): Promise<FloorPlanDecoration> {
  return apiRequest<FloorPlanDecoration>(
    `/floor-plans/${floorPlanId}/decorations/${decorationId}`,
    {
      method: "PATCH",
      token,
      body,
    },
  );
}

export async function deleteFloorPlanDecoration(
  token: string,
  floorPlanId: number,
  decorationId: number,
): Promise<FloorPlanDecoration> {
  return apiRequest<FloorPlanDecoration>(
    `/floor-plans/${floorPlanId}/decorations/${decorationId}`,
    {
      method: "DELETE",
      token,
    },
  );
}

export async function getFloorPlanView(token: string, floorPlanId?: number): Promise<{
  floorPlan: FloorPlan;
  tables: FloorTableView[];
  decorations: FloorPlanDecoration[];
}> {
  const floorPlan = floorPlanId 
    ? await getFloorPlan(token, floorPlanId)
    : await getActiveFloorPlan(token);
    
  const [positions, restaurantTables, decorations] = await Promise.all([
    getFloorPlanTables(token, floorPlan.id),
    getRestaurantTables(token),
    getFloorPlanDecorations(token, floorPlan.id),
  ]);
  const tablesById = new Map(
    restaurantTables.map((table) => [table.id, table]),
  );

  return {
    floorPlan,
    decorations,
    tables: positions.map((position) => ({
      ...position,
      table: tablesById.get(position.table_id) ?? null,
    })),
  };
}
