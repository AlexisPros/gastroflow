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

export async function getFloorPlanView(token: string): Promise<{
  floorPlan: FloorPlan;
  tables: FloorTableView[];
}> {
  const floorPlan = await getActiveFloorPlan(token);
  const [positions, restaurantTables] = await Promise.all([
    getFloorPlanTables(token, floorPlan.id),
    getRestaurantTables(token),
  ]);
  const tablesById = new Map(
    restaurantTables.map((table) => [table.id, table]),
  );

  return {
    floorPlan,
    tables: positions.map((position) => ({
      ...position,
      table: tablesById.get(position.table_id) ?? null,
    })),
  };
}
