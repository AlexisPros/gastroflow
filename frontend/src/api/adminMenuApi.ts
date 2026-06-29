import { apiRequest } from "./apiClient";

export type AdminCategory = {
  id: number;
  name: string;
  parent_category_id: number | null;
  department: "KITCHEN" | "BAR";
  is_active: boolean;
};

export type AdminIngredient = {
  id: number;
  name: string;
  unit: string;
  is_active: boolean;
};

export type AdminModifier = {
  id: number;
  name: string;
  price: string;
  is_active: boolean;
};

export type AdminKitchenSection = {
  id: number;
  name: string;
  is_active: boolean;
};

export type AdminProductIngredient = {
  id?: number | null;
  ingredient_id?: number | null;
  ingredient_name?: string | null;
  unit?: string | null;
  quantity: string;
};

export type AdminProductIngredientRead = Required<
  Pick<AdminProductIngredient, "id" | "ingredient_id" | "ingredient_name" | "unit" | "quantity">
>;

export type AdminProductModifier = {
  id?: number | null;
  modifier_id?: number | null;
  modifier_name?: string | null;
  modifier_price: string;
  price_override?: string | null;
  stock_ingredient_id?: number | null;
  stock_ingredient_name?: string | null;
  stock_ingredient_unit?: string | null;
  stock_quantity?: string | null;
  replaces_ingredient_id?: number | null;
  replaces_ingredient_name?: string | null;
  is_active: boolean;
};

export type AdminProductModifierRead = Required<Pick<
  AdminProductModifier,
  | "id"
  | "modifier_id"
  | "modifier_name"
  | "modifier_price"
  | "price_override"
  | "stock_ingredient_id"
  | "stock_ingredient_name"
  | "stock_ingredient_unit"
  | "stock_quantity"
  | "replaces_ingredient_id"
  | "replaces_ingredient_name"
  | "is_active"
>>;

export type AdminProductStep = {
  id?: number | null;
  kitchen_section_id: number;
  kitchen_section_name?: string;
  name: string;
  description?: string | null;
  sequence: number;
  estimated_time?: number | null;
  depends_on_sequence?: number | null;
  is_active: boolean;
};

export type AdminProduct = {
  id: number;
  category_id: number;
  kitchen_section_id: number | null;
  warehouse_id: number | null;
  name: string;
  description: string | null;
  image_url: string | null;
  price: string;
  vat_rate: string;
  preparation_time: number | null;
  is_active: boolean;
  ingredients: AdminProductIngredientRead[];
  modifiers: AdminProductModifierRead[];
  kitchen_steps: AdminProductStep[];
};

export type AdminProductPayload = {
  category_id: number;
  kitchen_section_id: number | null;
  warehouse_id: number | null;
  name: string;
  description: string | null;
  image_url: string | null;
  price: string;
  vat_rate: string;
  preparation_time: number | null;
  is_active: boolean;
  ingredients: AdminProductIngredient[];
  modifiers: AdminProductModifier[];
  kitchen_steps: AdminProductStep[];
};

export type AdminDiscount = {
  id: number;
  name: string;
  type: string;
  value: string;
  is_active: boolean;
};

export type AdminMenu = {
  categories: AdminCategory[];
  products: AdminProduct[];
  ingredients: AdminIngredient[];
  modifiers: AdminModifier[];
  kitchen_sections: AdminKitchenSection[];
  discounts: AdminDiscount[];
};

export async function getAdminMenu(token: string): Promise<AdminMenu> {
  return apiRequest<AdminMenu>("/admin/menu", { token });
}

export async function uploadAdminMenuImage(token: string, file: File): Promise<{ image_url: string }> {
  const body = new FormData();
  body.append("file", file);
  return apiRequest<{ image_url: string }>("/admin/menu/uploads/images", {
    method: "POST",
    token,
    body,
    timeoutMs: 30000,
  });
}

export async function createAdminCategory(
  token: string,
  body: Omit<AdminCategory, "id">,
): Promise<AdminCategory> {
  return apiRequest<AdminCategory>("/admin/menu/categories", { method: "POST", token, body });
}

export async function updateAdminCategory(
  token: string,
  id: number,
  body: Partial<Omit<AdminCategory, "id">>,
): Promise<AdminCategory> {
  return apiRequest<AdminCategory>(`/admin/menu/categories/${id}`, { method: "PATCH", token, body });
}

export async function deleteAdminCategory(token: string, id: number): Promise<AdminCategory> {
  return apiRequest<AdminCategory>(`/admin/menu/categories/${id}`, { method: "DELETE", token });
}

export async function createAdminProduct(
  token: string,
  body: AdminProductPayload,
): Promise<AdminProduct> {
  return apiRequest<AdminProduct>("/admin/menu/products", { method: "POST", token, body });
}

export async function updateAdminProduct(
  token: string,
  id: number,
  body: Partial<AdminProductPayload>,
): Promise<AdminProduct> {
  return apiRequest<AdminProduct>(`/admin/menu/products/${id}`, { method: "PATCH", token, body });
}

export async function deleteAdminProduct(token: string, id: number): Promise<AdminProduct> {
  return apiRequest<AdminProduct>(`/admin/menu/products/${id}`, { method: "DELETE", token });
}

export async function createAdminIngredient(
  token: string,
  body: Omit<AdminIngredient, "id">,
): Promise<AdminIngredient> {
  return apiRequest<AdminIngredient>("/admin/menu/ingredients", { method: "POST", token, body });
}

export async function updateAdminIngredient(
  token: string,
  id: number,
  body: Partial<Omit<AdminIngredient, "id">>,
): Promise<AdminIngredient> {
  return apiRequest<AdminIngredient>(`/admin/menu/ingredients/${id}`, { method: "PATCH", token, body });
}

export async function deleteAdminIngredient(token: string, id: number): Promise<AdminIngredient> {
  return apiRequest<AdminIngredient>(`/admin/menu/ingredients/${id}`, { method: "DELETE", token });
}

export async function createAdminModifier(
  token: string,
  body: Omit<AdminModifier, "id">,
): Promise<AdminModifier> {
  return apiRequest<AdminModifier>("/admin/menu/modifiers", { method: "POST", token, body });
}

export async function updateAdminModifier(
  token: string,
  id: number,
  body: Partial<Omit<AdminModifier, "id">>,
): Promise<AdminModifier> {
  return apiRequest<AdminModifier>(`/admin/menu/modifiers/${id}`, { method: "PATCH", token, body });
}

export async function deleteAdminModifier(token: string, id: number): Promise<AdminModifier> {
  return apiRequest<AdminModifier>(`/admin/menu/modifiers/${id}`, { method: "DELETE", token });
}

export async function createAdminDiscount(
  token: string,
  body: Omit<AdminDiscount, "id">,
): Promise<AdminDiscount> {
  return apiRequest<AdminDiscount>("/admin/menu/discounts", { method: "POST", token, body });
}

export async function updateAdminDiscount(
  token: string,
  id: number,
  body: Partial<Omit<AdminDiscount, "id">>,
): Promise<AdminDiscount> {
  return apiRequest<AdminDiscount>(`/admin/menu/discounts/${id}`, { method: "PATCH", token, body });
}

export async function deleteAdminDiscount(token: string, id: number): Promise<AdminDiscount> {
  return apiRequest<AdminDiscount>(`/admin/menu/discounts/${id}`, { method: "DELETE", token });
}
