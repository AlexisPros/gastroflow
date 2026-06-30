import { useCallback, useEffect, useMemo, useState } from "react";
import { Plus, RefreshCw, Pencil, Trash2, ShieldCheck } from "lucide-react";

import {
  createAdminCategory,
  createAdminDiscount,
  createAdminIngredient,
  createAdminModifier,
  createAdminProduct,
  deleteAdminCategory,
  deleteAdminDiscount,
  deleteAdminIngredient,
  deleteAdminModifier,
  deleteAdminProduct,
  getAdminMenu,
  updateAdminCategory,
  updateAdminDiscount,
  updateAdminIngredient,
  updateAdminModifier,
  updateAdminProduct,
  uploadAdminMenuImage,
  type AdminCategory,
  type AdminDiscount,
  type AdminIngredient,
  type AdminKitchenSection,
  type AdminMenu,
  type AdminModifier,
  type AdminProduct,
  type AdminProductIngredient,
  type AdminProductModifier,
  type AdminProductPayload,
  type AdminProductStep,
} from "../api/adminMenuApi";
import { ApiError } from "../api/apiClient";
import { getWarehouses, type Warehouse } from "../api/warehouseApi";
import { useAuth } from "../auth/useAuth";
import { usePrompt } from "../components/PromptProvider";

type ProductFormState = AdminProductPayload & {
  id: number | null;
};

type CategoryFormState = {
  id: number | null;
  name: string;
  parent_category_id: number | null;
  department: "KITCHEN" | "BAR";
  is_active: boolean;
};

const emptyMenu: AdminMenu = {
  categories: [],
  products: [],
  ingredients: [],
  modifiers: [],
  kitchen_sections: [],
  discounts: [],
};

const money = new Intl.NumberFormat("pl-PL", {
  style: "currency",
  currency: "PLN",
});

export function AdminMenuPage() {
  const { token } = useAuth();
  const { confirm } = usePrompt();
  const [menu, setMenu] = useState<AdminMenu>(emptyMenu);
  const [selectedProductId, setSelectedProductId] = useState<number | "NEW">("NEW");
  const [form, setForm] = useState<ProductFormState>(() => createEmptyProductForm());
  const [isProductModalOpen, setIsProductModalOpen] = useState(false);
  const [categoryForm, setCategoryForm] = useState<CategoryFormState>(() => createEmptyCategoryForm());
  const [isCategoryModalOpen, setIsCategoryModalOpen] = useState(false);
  const [expandedCategoryIds, setExpandedCategoryIds] = useState<Set<number>>(() => new Set());
  const [activeSection, setActiveSection] = useState<"menu" | "ingredients" | "modifiers" | "discounts">("menu");
  const [warehouses, setWarehouses] = useState<Warehouse[]>([]);
  const [productSearch, setProductSearch] = useState("");
  const [productCategoryFilter, setProductCategoryFilter] = useState<number | "ALL">("ALL");
  const [productStatusFilter, setProductStatusFilter] = useState<"ALL" | "ACTIVE" | "INACTIVE">("ALL");
  const [discountForm, setDiscountForm] = useState({
    id: null as number | null,
    name: "",
    type: "PERCENT",
    value: "10.00",
    is_active: true,
  });
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);

  const rootCategories = useMemo(
    () => menu.categories.filter((category) => category.parent_category_id === null),
    [menu.categories],
  );
  const childCategoriesByParent = useMemo(() => {
    const map = new Map<number, AdminCategory[]>();
    for (const category of menu.categories) {
      if (category.parent_category_id === null) continue;
      map.set(category.parent_category_id, [
        ...(map.get(category.parent_category_id) ?? []),
        category,
      ]);
    }
    return map;
  }, [menu.categories]);
  const activeCategories = useMemo(
    () => menu.categories.filter((category) => category.is_active),
    [menu.categories],
  );

  const filteredProducts = useMemo(() => {
    return menu.products.filter((product) => {
      if (productSearch.trim()) {
        const query = productSearch.toLowerCase();
        const matchesName = product.name.toLowerCase().includes(query);
        const matchesDesc = (product.description ?? "").toLowerCase().includes(query);
        if (!matchesName && !matchesDesc) return false;
      }
      if (productCategoryFilter !== "ALL") {
        const isSelectedOrChild = (catId: number): boolean => {
          if (product.category_id === catId) return true;
          const cat = menu.categories.find((c) => c.id === product.category_id);
          if (cat && cat.parent_category_id === catId) return true;
          return false;
        };
        if (!isSelectedOrChild(productCategoryFilter)) return false;
      }
      if (productStatusFilter === "ACTIVE" && !product.is_active) return false;
      if (productStatusFilter === "INACTIVE" && product.is_active) return false;
      return true;
    });
  }, [menu.products, menu.categories, productSearch, productCategoryFilter, productStatusFilter]);
  const activeKitchenSections = useMemo(
    () => menu.kitchen_sections.filter((section) => section.is_active),
    [menu.kitchen_sections],
  );

  const loadMenu = useCallback(async () => {
    if (!token) return;
    setIsLoading(true);
    setError(null);
    try {
      const [nextMenu, nextWarehouses] = await Promise.all([
        getAdminMenu(token),
        getWarehouses(token).catch(() => []),
      ]);
      setMenu(nextMenu);
      setWarehouses(nextWarehouses);
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.message : "Nie udało się pobrać menu.");
    } finally {
      setIsLoading(false);
    }
  }, [token]);

  useEffect(() => {
    if (!token) return;
    void loadMenu();
  }, [loadMenu, token]);

  useEffect(() => {
    if (selectedProductId === "NEW") {
      setForm(createEmptyProductForm(activeCategories[0]?.id ?? 0));
      return;
    }

    const product = menu.products.find((item) => item.id === selectedProductId);
    if (product) {
      setForm(productToForm(product));
    }
  }, [activeCategories, menu.products, selectedProductId]);

  async function saveProduct() {
    if (!token || !form.category_id) {
      setError("Wybierz kategorię produktu.");
      return;
    }

    setIsSaving(true);
    setError(null);
    try {
      const payload = formToPayload(form);
      const saved =
        form.id === null
          ? await createAdminProduct(token, payload)
          : await updateAdminProduct(token, form.id, payload);
      setNotice("Produkt zapisany. Kelnerzy i QR zobaczą go po odświeżeniu menu.");
      await loadMenu();
      setSelectedProductId(saved.id);
      setIsProductModalOpen(false);
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.message : "Nie udało się zapisać produktu.");
    } finally {
      setIsSaving(false);
    }
  }

  function openNewProduct() {
    setSelectedProductId("NEW");
    setForm(createEmptyProductForm(activeCategories[0]?.id ?? 0));
    setIsProductModalOpen(true);
    setNotice(null);
    setError(null);
  }

  function openExistingProduct(product: AdminProduct) {
    setSelectedProductId(product.id);
    setForm(productToForm(product));
    setIsProductModalOpen(true);
    setNotice(null);
    setError(null);
  }

  async function deactivateProduct(product: AdminProduct) {
    if (!token) return;
    const yes = await confirm({
      title: "Potwierdź usunięcie",
      message: `Czy na pewno chcesz usunąć produkt "${product.name}" z menu?`,
      confirmText: "Usuń",
      cancelText: "Anuluj",
    });
    if (!yes) return;
    setIsSaving(true);
    setError(null);
    try {
      await deleteAdminProduct(token, product.id);
      setNotice("Produkt został usunięty z aktywnego menu.");
      await loadMenu();
      setSelectedProductId("NEW");
      setIsProductModalOpen(false);
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.message : "Nie udało się usunąć produktu.");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleImageUpload(file: File | undefined) {
    if (!token || !file) return;
    setIsSaving(true);
    setError(null);
    try {
      const result = await uploadAdminMenuImage(token, file);
      setForm((current) => ({ ...current, image_url: result.image_url }));
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.message : "Nie udało się wysłać zdjęcia.");
    } finally {
      setIsSaving(false);
    }
  }

  function openNewCategory(parentCategoryId: number | null = null) {
    const parent = menu.categories.find((category) => category.id === parentCategoryId);
    setCategoryForm(createEmptyCategoryForm(parentCategoryId, parent?.department ?? "KITCHEN"));
    setIsCategoryModalOpen(true);
    setNotice(null);
    setError(null);
  }

  function openExistingCategory(category: AdminCategory) {
    setCategoryForm({
      id: category.id,
      name: category.name,
      parent_category_id: category.parent_category_id,
      department: category.department,
      is_active: category.is_active,
    });
    setIsCategoryModalOpen(true);
    setNotice(null);
    setError(null);
  }

  async function saveCategory() {
    if (!token || !categoryForm.name.trim()) return;
    setError(null);
    try {
      const payload = {
        name: categoryForm.name.trim(),
        parent_category_id: categoryForm.parent_category_id,
        department: categoryForm.department,
        is_active: categoryForm.is_active,
      };
      if (categoryForm.id === null) {
        await createAdminCategory(token, payload);
      } else {
        await updateAdminCategory(token, categoryForm.id, payload);
      }
      setIsCategoryModalOpen(false);
      setCategoryForm(createEmptyCategoryForm());
      await loadMenu();
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.message : "Nie udało się zapisać kategorii.");
    }
  }

  async function toggleCategory(category: AdminCategory) {
    if (!token) return;
    await updateAdminCategory(token, category.id, { is_active: !category.is_active });
    await loadMenu();
  }

  async function removeCategory(category: AdminCategory) {
    if (!token) return;
    const yes = await confirm({
      title: "Potwierdź usunięcie kategorii",
      message: `Czy na pewno chcesz usunąć kategorię "${category.name}"? Spowoduje to również dezaktywację wszystkich jej podkategorii i produktów.`,
      confirmText: "Usuń",
      cancelText: "Anuluj",
    });
    if (!yes) return;
    await deleteAdminCategory(token, category.id);
    setIsCategoryModalOpen(false);
    await loadMenu();
  }

  function toggleExpandedCategory(categoryId: number) {
    setExpandedCategoryIds((current) => {
      const next = new Set(current);
      if (next.has(categoryId)) {
        next.delete(categoryId);
      } else {
        next.add(categoryId);
      }
      return next;
    });
  }

  async function saveDiscount() {
    if (!token || !discountForm.name.trim()) return;
    setError(null);
    try {
      const payload = {
        name: discountForm.name.trim(),
        type: discountForm.type,
        value: discountForm.value,
        is_active: discountForm.is_active,
      };
      if (discountForm.id === null) {
        await createAdminDiscount(token, payload);
      } else {
        await updateAdminDiscount(token, discountForm.id, payload);
      }
      setDiscountForm({ id: null, name: "", type: "PERCENT", value: "10.00", is_active: true });
      await loadMenu();
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.message : "Nie udało się zapisać rabatu.");
    }
  }

  async function removeDiscount(discount: AdminDiscount) {
    if (!token) return;
    const yes = await confirm({
      title: "Potwierdź usunięcie rabatu",
      message: `Czy na pewno chcesz usunąć rabat "${discount.name}"?`,
      confirmText: "Usuń",
      cancelText: "Anuluj",
    });
    if (!yes) return;
    await deleteAdminDiscount(token, discount.id);
    await loadMenu();
  }

  async function saveIngredient(ingredient: AdminIngredient) {
    if (!token) return;
    await updateAdminIngredient(token, ingredient.id, ingredient);
    await loadMenu();
  }

  async function createIngredient(name: string, unit: string) {
    if (!token || !name.trim() || !unit.trim()) return;
    await createAdminIngredient(token, {
      name: name.trim(),
      unit: unit.trim(),
      is_active: true,
    });
    await loadMenu();
  }

  async function saveModifier(modifier: AdminModifier) {
    if (!token) return;
    await updateAdminModifier(token, modifier.id, modifier);
    await loadMenu();
  }

  async function createModifier(name: string, price: string) {
    if (!token || !name.trim()) return;
    await createAdminModifier(token, {
      name: name.trim(),
      price: price || "0.00",
      is_active: true,
    });
    await loadMenu();
  }

  if (isLoading) {
    return <section className="page-stack"><h1>Ładowanie menu...</h1></section>;
  }

  return (
    <section className="warehouse-page">
      <header className="warehouse-header">
        <div>
          <span className="eyebrow">Konfiguracja systemu</span>
          <h1>Edytor menu</h1>
        </div>
        <div className="warehouse-header-actions">
          <button type="button" className="icon-command" title="Odśwież" onClick={() => void loadMenu()}>
            <RefreshCw size={18} />
            Odśwież
          </button>
        </div>
      </header>

      {error && <p className="form-error">{error}</p>}
      {notice && <p className="form-notice">{notice}</p>}

      <div className="warehouse-tabs" role="tablist" aria-label="Sekcje menu" style={{ marginBottom: "8px" }}>
        <button
          type="button"
          className={activeSection === "menu" ? "active" : ""}
          onClick={() => setActiveSection("menu")}
        >
          Kategorie i Produkty
        </button>
        <button
          type="button"
          className={activeSection === "ingredients" ? "active" : ""}
          onClick={() => setActiveSection("ingredients")}
        >
          Słownik składników
        </button>
        <button
          type="button"
          className={activeSection === "modifiers" ? "active" : ""}
          onClick={() => setActiveSection("modifiers")}
        >
          Modyfikatory dań
        </button>
        <button
          type="button"
          className={activeSection === "discounts" ? "active" : ""}
          onClick={() => setActiveSection("discounts")}
        >
          System rabatów
        </button>
      </div>

      {activeSection === "menu" && (
        <div className="warehouse-content-grid" style={{ gridTemplateColumns: "minmax(320px, 0.85fr) minmax(520px, 1.15fr)", alignItems: "stretch" }}>
          <aside className="warehouse-section" style={{ minHeight: "520px" }}>
            <div className="warehouse-section-heading">
              <div>
                <span className="eyebrow">Grupy produktów</span>
                <h2>Kategorie</h2>
              </div>
              <button 
                type="button" 
                className="admin-primary" 
                onClick={() => openNewCategory()}
                style={{ display: "inline-flex", alignItems: "center", gap: "6px", minHeight: "36px", padding: "0 12px", background: "var(--brand-green)", color: "#fff", borderColor: "var(--brand-green)", borderRadius: "6px", cursor: "pointer", fontWeight: "bold" }}
              >
                <Plus size={16} /> Nowa kategoria
              </button>
            </div>

            <div className="admin-category-tree">
              {rootCategories.map((category) => (
                <div key={category.id} className={`admin-category-group ${!category.is_active ? "inactive" : ""}`}>
                  <div className="admin-category-row">
                    <button
                      type="button"
                      className="admin-category-toggle"
                      onClick={() => toggleExpandedCategory(category.id)}
                      aria-label={expandedCategoryIds.has(category.id) ? "Zwiń podkategorie" : "Rozwiń podkategorie"}
                    >
                      {expandedCategoryIds.has(category.id) ? "−" : "+"}
                    </button>
                    <strong>{category.name}</strong>
                    <small>{category.department === "BAR" ? "Bar" : "Dania"}</small>
                    <CategoryActions
                      category={category}
                      onEdit={openExistingCategory}
                      onCreateChild={openNewCategory}
                      onToggle={toggleCategory}
                      onDelete={removeCategory}
                    />
                  </div>
                  {expandedCategoryIds.has(category.id) && (
                    <div className="admin-category-children">
                      {(childCategoriesByParent.get(category.id) ?? []).map((child) => (
                        <div key={child.id} className={`admin-category-row child ${!child.is_active ? "inactive" : ""}`}>
                          <span>{child.name}</span>
                          <CategoryActions
                            category={child}
                            onEdit={openExistingCategory}
                            onCreateChild={openNewCategory}
                            onToggle={toggleCategory}
                            onDelete={removeCategory}
                          />
                        </div>
                      ))}
                      {(childCategoriesByParent.get(category.id) ?? []).length === 0 && (
                        <p className="admin-category-empty">Brak podkategorii.</p>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </aside>

          <main className="warehouse-section" style={{ minHeight: "520px" }}>
            <div className="warehouse-section-heading">
              <div>
                <span className="eyebrow">Oferta lokalu</span>
                <h2>Produkty</h2>
              </div>
              <button
                type="button"
                className="admin-primary"
                onClick={openNewProduct}
                style={{ display: "inline-flex", alignItems: "center", gap: "6px", minHeight: "36px", padding: "0 12px", background: "var(--brand-green)", color: "#fff", borderColor: "var(--brand-green)", borderRadius: "6px", cursor: "pointer", fontWeight: "bold" }}
              >
                <Plus size={16} /> Nowy produkt
              </button>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: "14px", minHeight: 0 }}>
              <div style={{ display: "flex", gap: "10px", padding: "12px", background: "#f8fafc", borderRadius: "8px", border: "1px solid #cbd5e0", flexWrap: "wrap", alignItems: "center" }}>
                <input
                  type="text"
                  placeholder="Wyszukaj produkt..."
                  value={productSearch}
                  onChange={(e) => setProductSearch(e.target.value)}
                  style={{ flex: 2, minWidth: "150px", padding: "8px 12px", borderRadius: "6px", border: "1px solid #cbd5e0", fontSize: "0.9rem" }}
                />
                <select
                  value={productCategoryFilter}
                  onChange={(e) => setProductCategoryFilter(e.target.value === "ALL" ? "ALL" : Number(e.target.value))}
                  style={{ flex: 1, minWidth: "140px", padding: "8px 12px", borderRadius: "6px", border: "1px solid #cbd5e0", fontSize: "0.9rem", height: "38px" }}
                >
                  <option value="ALL">Wszystkie kategorie</option>
                  {menu.categories.map((cat) => (
                    <option key={cat.id} value={cat.id}>{cat.name}</option>
                  ))}
                </select>
                <select
                  value={productStatusFilter}
                  onChange={(event) => {
                    const value = event.target.value;
                    if (value === "ALL" || value === "ACTIVE" || value === "INACTIVE") {
                      setProductStatusFilter(value);
                    }
                  }}
                  style={{ minWidth: "120px", padding: "8px 12px", borderRadius: "6px", border: "1px solid #cbd5e0", fontSize: "0.9rem", height: "38px" }}
                >
                  <option value="ALL">Status: Wszystkie</option>
                  <option value="ACTIVE">Aktywne</option>
                  <option value="INACTIVE">Nieaktywne</option>
                </select>
              </div>

              <div className="admin-product-list" style={{ flex: 1, minHeight: 0, alignContent: "start" }}>
                {filteredProducts.map((product) => {
                  const category = menu.categories.find((item) => item.id === product.category_id);
                  return (
                    <button
                      key={product.id}
                      type="button"
                      className={`${selectedProductId === product.id ? "active" : ""} ${!product.is_active ? "inactive" : ""}`}
                      onClick={() => openExistingProduct(product)}
                    >
                      {product.image_url ? <img src={product.image_url} alt="" /> : <span />}
                      <div>
                        <strong>{product.name}</strong>
                        <small>{category?.name ?? "Bez kategorii"} · {money.format(Number(product.price))}</small>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          </main>
        </div>
      )}

      {activeSection === "ingredients" && (
        <div className="warehouse-content-grid" style={{ gridTemplateColumns: "1fr" }}>
          <section className="warehouse-section" style={{ minHeight: "520px" }}>
            <ReferenceEditor
              title="Składniki"
              items={menu.ingredients}
              onCreate={createIngredient}
              onSave={saveIngredient}
              onDelete={(item) => token ? deleteAdminIngredient(token, item.id).then(loadMenu) : undefined}
            />
          </section>
        </div>
      )}

      {activeSection === "modifiers" && (
        <div className="warehouse-content-grid" style={{ gridTemplateColumns: "1fr" }}>
          <section className="warehouse-section" style={{ minHeight: "520px" }}>
            <ModifierEditor
              title="Modyfikatory"
              items={menu.modifiers}
              onCreate={createModifier}
              onSave={saveModifier}
              onDelete={(item) => token ? deleteAdminModifier(token, item.id).then(loadMenu) : undefined}
            />
          </section>
        </div>
      )}

      {activeSection === "discounts" && (
        <div className="warehouse-content-grid" style={{ gridTemplateColumns: "1fr" }}>
          <section className="warehouse-section" style={{ minHeight: "520px" }}>
            <DiscountEditor
              discounts={menu.discounts}
              form={discountForm}
              onChange={setDiscountForm}
              onSave={saveDiscount}
              onEdit={setDiscountForm}
              onDelete={removeDiscount}
            />
          </section>
        </div>
      )}

      {isCategoryModalOpen && (
        <div className="admin-modal-backdrop">
          <section className="admin-modal admin-category-modal">
            <div className="admin-panel-heading split">
              <h2>{categoryForm.id === null ? "Nowa kategoria" : "Edycja kategorii"}</h2>
              <button type="button" className="ghost-button" onClick={() => setIsCategoryModalOpen(false)}>
                Zamknij
              </button>
            </div>

            <div className="admin-form-grid">
              <label className="wide">
                Nazwa
                <input
                  value={categoryForm.name}
                  onChange={(event) =>
                    setCategoryForm((current) => ({ ...current, name: event.target.value }))
                  }
                />
              </label>
              <label className="wide">
                Rodzic
                <select
                  value={categoryForm.parent_category_id ?? ""}
                  onChange={(event) =>
                    setCategoryForm((current) => {
                      const parentId = event.target.value ? Number(event.target.value) : null;
                      const parent = menu.categories.find((category) => category.id === parentId);
                      return {
                        ...current,
                        parent_category_id: parentId,
                        department: parent?.department ?? current.department,
                      };
                    })
                  }
                >
                  <option value="">Główna kategoria</option>
                  {rootCategories
                    .filter((category) => category.id !== categoryForm.id)
                    .map((category) => (
                      <option key={category.id} value={category.id}>
                        Pod: {category.name}
                      </option>
                    ))}
                </select>
              </label>
              <label className="wide">
                Dział
                <select
                  value={categoryForm.department}
                  disabled={categoryForm.parent_category_id !== null}
                  onChange={(event) =>
                    setCategoryForm((current) => ({
                      ...current,
                      department: event.target.value as "KITCHEN" | "BAR",
                    }))
                  }
                >
                  <option value="KITCHEN">Dania</option>
                  <option value="BAR">Bar</option>
                </select>
              </label>
              <label className="switch-row compact wide">
                <input
                  type="checkbox"
                  checked={categoryForm.is_active}
                  onChange={(event) =>
                    setCategoryForm((current) => ({ ...current, is_active: event.target.checked }))
                  }
                />
                Aktywna
              </label>
            </div>

            <div className="admin-form-actions">
              {categoryForm.id !== null && (
                <button
                  type="button"
                  className="danger"
                  onClick={() => {
                    const category = menu.categories.find((item) => item.id === categoryForm.id);
                    if (category) void removeCategory(category);
                  }}
                >
                  Usuń kategorię
                </button>
              )}
              <button type="button" className="admin-primary" onClick={() => void saveCategory()}>
                Zapisz kategorię
              </button>
            </div>
          </section>
        </div>
      )}

      {isProductModalOpen && (
        <div className="admin-modal-backdrop">
          <aside className="admin-modal admin-product-form">
          <div className="admin-panel-heading split">
            <h2>{form.id === null ? "Nowy produkt" : "Edycja produktu"}</h2>
            <div className="admin-modal-heading-actions">
              <label className="switch-row compact">
                <input
                  type="checkbox"
                  checked={form.is_active}
                  onChange={(event) => setForm({ ...form, is_active: event.target.checked })}
                />
                Aktywny
              </label>
              <button type="button" className="ghost-button" onClick={() => setIsProductModalOpen(false)}>
                Zamknij
              </button>
            </div>
          </div>

          <div className="admin-form-grid">
            <label>
              Nazwa
              <input
                value={form.name}
                onChange={(event) => setForm({ ...form, name: event.target.value })}
              />
            </label>
            <label>
              Kategoria / podkategoria
              <select
                value={form.category_id || ""}
                onChange={(event) => setForm({ ...form, category_id: Number(event.target.value) })}
              >
                <option value="" disabled>Wybierz kategorię</option>
                {rootCategories.map((category) => (
                  <CategoryOptionGroup
                    key={category.id}
                    category={category}
                    childrenCategories={childCategoriesByParent.get(category.id) ?? []}
                  />
                ))}
              </select>
            </label>
            <label>
              Cena
              <input
                type="number"
                step="0.01"
                value={form.price}
                onChange={(event) => setForm({ ...form, price: event.target.value })}
              />
            </label>
            <label>
              VAT %
              <input
                type="number"
                step="0.01"
                value={form.vat_rate}
                onChange={(event) => setForm({ ...form, vat_rate: event.target.value })}
              />
            </label>
            <label>
              Bazowa sekcja
              <select
                value={form.kitchen_section_id ?? ""}
                onChange={(event) =>
                  setForm({
                    ...form,
                    kitchen_section_id: event.target.value ? Number(event.target.value) : null,
                  })
                }
              >
                <option value="">Tylko kroki przygotowania</option>
                {activeKitchenSections.map((section) => (
                  <option key={section.id} value={section.id}>
                    {section.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Magazyn do rozchodu składników
              <select
                value={form.warehouse_id ?? ""}
                onChange={(event) =>
                  setForm({
                    ...form,
                    warehouse_id: event.target.value ? Number(event.target.value) : null,
                  })
                }
              >
                <option value="">Użyj domyślnego magazynu</option>
                {warehouses.filter((w) => w.is_active).map((w) => (
                  <option key={w.id} value={w.id}>
                    {w.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="wide">
              Opis
              <textarea
                value={form.description ?? ""}
                onChange={(event) => setForm({ ...form, description: event.target.value })}
              />
            </label>
          </div>

          <div className="admin-image-uploader">
            {form.image_url ? <img src={form.image_url} alt="" /> : <span>Brak zdjęcia</span>}
            <label>
              Dodaj zdjęcie
              <input
                type="file"
                accept="image/png,image/jpeg,image/webp"
                onChange={(event) => void handleImageUpload(event.target.files?.[0])}
              />
            </label>
          </div>

          <ProductIngredientsForm
            ingredients={form.ingredients}
            catalog={menu.ingredients}
            onChange={(ingredients) => setForm({ ...form, ingredients })}
          />

          <ProductModifiersForm
            modifiers={form.modifiers}
            catalog={menu.modifiers}
            ingredients={menu.ingredients}
            onChange={(modifiers) => setForm({ ...form, modifiers })}
          />

          <ProductStepsForm
            steps={form.kitchen_steps}
            kitchenSections={activeKitchenSections}
            onChange={(kitchen_steps) => setForm({ ...form, kitchen_steps })}
          />

          <div className="admin-form-actions">
            {form.id !== null && (
              <button
                type="button"
                className="danger"
                disabled={isSaving}
                onClick={() => void deactivateProduct(formToProduct(form, menu))}
              >
                Usuń z menu
              </button>
            )}
            <button
              type="button"
              className="admin-primary"
              disabled={isSaving}
              onClick={() => void saveProduct()}
            >
              {isSaving ? "Zapisywanie..." : "Zapisz produkt"}
            </button>
          </div>
          </aside>
        </div>
      )}
    </section>
  );

  function formToProduct(current: ProductFormState, source: AdminMenu): AdminProduct {
    const existing = source.products.find((product) => product.id === current.id);
    return existing ?? {
      id: current.id ?? 0,
      category_id: current.category_id,
      kitchen_section_id: current.kitchen_section_id,
      warehouse_id: current.warehouse_id,
      name: current.name,
      description: current.description,
      image_url: current.image_url,
      price: current.price,
      vat_rate: current.vat_rate,
      preparation_time: current.preparation_time,
      is_active: current.is_active,
      ingredients: [],
      modifiers: [],
      kitchen_steps: [],
    };
  }
}

function CategoryOptionGroup({
  category,
  childrenCategories,
}: {
  category: AdminCategory;
  childrenCategories: AdminCategory[];
}) {
  return (
    <>
      <option value={category.id}>{category.name}</option>
      {childrenCategories.map((child) => (
        <option key={child.id} value={child.id}>
          — {child.name}
        </option>
      ))}
    </>
  );
}

function CategoryActions({
  category,
  onEdit,
  onCreateChild,
  onToggle,
  onDelete,
}: {
  category: AdminCategory;
  onEdit: (category: AdminCategory) => void;
  onCreateChild: (parentCategoryId: number) => void;
  onToggle: (category: AdminCategory) => Promise<void>;
  onDelete: (category: AdminCategory) => Promise<void>;
}) {
  return (
    <span style={{ display: "inline-flex", gap: "6px", alignItems: "center", marginLeft: "auto" }}>
      <button
        type="button"
        className="stock-edit-button"
        title="Edytuj"
        style={{ background: "none", border: "none", cursor: "pointer", display: "inline-flex", padding: "4px" }}
        onClick={() => onEdit(category)}
      >
        <Pencil size={15} />
      </button>
      {category.parent_category_id === null && (
        <button
          type="button"
          className="stock-edit-button"
          title="Dodaj podkategorię"
          style={{ background: "none", border: "none", cursor: "pointer", display: "inline-flex", padding: "4px", color: "var(--brand-green)" }}
          onClick={() => onCreateChild(category.id)}
        >
          <Plus size={15} />
        </button>
      )}
      <button
        type="button"
        className="stock-edit-button"
        title={category.is_active ? "Dezaktywuj" : "Aktywuj"}
        style={{ background: "none", border: "none", cursor: "pointer", display: "inline-flex", padding: "4px", color: category.is_active ? "#e08b14" : "#1e6287" }}
        onClick={() => void onToggle(category)}
      >
        <ShieldCheck size={15} />
      </button>
      <button
        type="button"
        className="stock-delete-button"
        title="Usuń"
        style={{ background: "none", border: "none", cursor: "pointer", display: "inline-flex", padding: "4px" }}
        onClick={() => void onDelete(category)}
      >
        <Trash2 size={15} />
      </button>
    </span>
  );
}

function ProductIngredientsForm({
  ingredients,
  catalog,
  onChange,
}: {
  ingredients: AdminProductIngredient[];
  catalog: AdminIngredient[];
  onChange: (ingredients: AdminProductIngredient[]) => void;
}) {
  return (
    <div className="admin-nested-section">
      <div className="admin-panel-heading split">
        <h3>Składniki</h3>
        <button type="button" onClick={() => onChange([...ingredients, emptyIngredient()])}>
          Dodaj składnik
        </button>
      </div>
      {ingredients.map((item, index) => (
        <div key={index} className="admin-nested-row">
          <select
            value={item.ingredient_id ?? ""}
            onChange={(event) => {
              const selected = catalog.find((ingredient) => ingredient.id === Number(event.target.value));
              updateArray(ingredients, index, {
                ...item,
                ingredient_id: selected?.id ?? null,
                ingredient_name: selected?.name ?? "",
                unit: selected?.unit ?? item.unit,
              }, onChange);
            }}
          >
            <option value="">Nowy składnik</option>
            {catalog.filter((ingredient) => ingredient.is_active).map((ingredient) => (
              <option key={ingredient.id} value={ingredient.id}>
                {ingredient.name} ({ingredient.unit})
              </option>
            ))}
          </select>
          <input
            placeholder="Nazwa"
            value={item.ingredient_name ?? ""}
            onChange={(event) => updateArray(ingredients, index, { ...item, ingredient_name: event.target.value }, onChange)}
          />
          <input
            placeholder="Jednostka"
            value={item.unit ?? ""}
            onChange={(event) => updateArray(ingredients, index, { ...item, unit: event.target.value }, onChange)}
          />
          <input
            type="number"
            step="0.01"
            placeholder="Ilość"
            value={item.quantity}
            onChange={(event) => updateArray(ingredients, index, { ...item, quantity: event.target.value }, onChange)}
          />
          <button type="button" className="danger-link" onClick={() => onChange(removeIndex(ingredients, index))}>
            Usuń
          </button>
        </div>
      ))}
    </div>
  );
}

function ProductModifiersForm({
  modifiers,
  catalog,
  ingredients,
  onChange,
}: {
  modifiers: AdminProductModifier[];
  catalog: AdminModifier[];
  ingredients: AdminIngredient[];
  onChange: (modifiers: AdminProductModifier[]) => void;
}) {
  return (
    <div className="admin-nested-section">
      <div className="admin-panel-heading split">
        <h3>Modyfikatory</h3>
        <button type="button" onClick={() => onChange([...modifiers, emptyModifier()])}>
          Dodaj modyfikator
        </button>
      </div>
      {modifiers.map((item, index) => (
        <div key={index} className="admin-nested-row modifier-stock-row">
          <select
            value={item.modifier_id ?? ""}
            onChange={(event) => {
              const selected = catalog.find((modifier) => modifier.id === Number(event.target.value));
              updateArray(modifiers, index, {
                ...item,
                modifier_id: selected?.id ?? null,
                modifier_name: selected?.name ?? "",
                modifier_price: selected?.price ?? "0.00",
              }, onChange);
            }}
          >
            <option value="">Nowy modyfikator</option>
            {catalog.filter((modifier) => modifier.is_active).map((modifier) => (
              <option key={modifier.id} value={modifier.id}>
                {modifier.name} ({money.format(Number(modifier.price))})
              </option>
            ))}
          </select>
          <input
            placeholder="Nazwa"
            value={item.modifier_name ?? ""}
            onChange={(event) => updateArray(modifiers, index, { ...item, modifier_name: event.target.value }, onChange)}
          />
          <input
            type="number"
            step="0.01"
            placeholder="Cena bazowa"
            value={item.modifier_price}
            onChange={(event) => updateArray(modifiers, index, { ...item, modifier_price: event.target.value }, onChange)}
          />
          <input
            type="number"
            step="0.01"
            placeholder="Cena dla dania"
            value={item.price_override ?? ""}
            onChange={(event) => updateArray(modifiers, index, { ...item, price_override: event.target.value || null }, onChange)}
          />
          <select
            value={item.stock_ingredient_id ?? ""}
            onChange={(event) => {
              const selected = ingredients.find((ingredient) => ingredient.id === Number(event.target.value));
              updateArray(modifiers, index, {
                ...item,
                stock_ingredient_id: selected?.id ?? null,
                stock_ingredient_name: selected?.name ?? null,
                stock_ingredient_unit: selected?.unit ?? null,
                stock_quantity: selected ? item.stock_quantity ?? "1.000" : null,
                replaces_ingredient_id: selected ? item.replaces_ingredient_id : null,
              }, onChange);
            }}
          >
            <option value="">Bez wpływu na magazyn</option>
            {ingredients.filter((ingredient) => ingredient.is_active).map((ingredient) => (
              <option key={ingredient.id} value={ingredient.id}>
                Rozchód: {ingredient.name} ({ingredient.unit})
              </option>
            ))}
          </select>
          <input
            type="number"
            min="0.001"
            step="0.001"
            disabled={!item.stock_ingredient_id}
            placeholder={`Ilość${item.stock_ingredient_unit ? ` (${item.stock_ingredient_unit})` : ""}`}
            value={item.stock_quantity ?? ""}
            onChange={(event) => updateArray(modifiers, index, {
              ...item,
              stock_quantity: event.target.value || null,
            }, onChange)}
          />
          <select
            value={item.replaces_ingredient_id ?? ""}
            disabled={!item.stock_ingredient_id}
            onChange={(event) => updateArray(modifiers, index, {
              ...item,
              replaces_ingredient_id: event.target.value ? Number(event.target.value) : null,
            }, onChange)}
          >
            <option value="">Nic nie zastępuje</option>
            {ingredients.filter((ingredient) => ingredient.is_active).map((ingredient) => (
              <option key={ingredient.id} value={ingredient.id}>
                Zamiast: {ingredient.name}
              </option>
            ))}
          </select>
          <label className="switch-row compact">
            <input
              type="checkbox"
              checked={item.is_active}
              onChange={(event) => updateArray(modifiers, index, { ...item, is_active: event.target.checked }, onChange)}
            />
            Aktywny
          </label>
          <button type="button" className="danger-link" onClick={() => onChange(removeIndex(modifiers, index))}>
            Usuń
          </button>
        </div>
      ))}
    </div>
  );
}

function ProductStepsForm({
  steps,
  kitchenSections,
  onChange,
}: {
  steps: AdminProductStep[];
  kitchenSections: AdminKitchenSection[];
  onChange: (steps: AdminProductStep[]) => void;
}) {
  return (
    <div className="admin-nested-section">
      <div className="admin-panel-heading split">
        <h3>Kroki przygotowania</h3>
        <button
          type="button"
          onClick={() => onChange([...steps, emptyStep(kitchenSections[0]?.id ?? 0, steps.length + 1)])}
        >
          Dodaj krok
        </button>
      </div>
      {steps.map((item, index) => (
        <div key={index} className="admin-nested-row step">
          <input
            placeholder="Nazwa kroku"
            value={item.name}
            onChange={(event) => updateArray(steps, index, { ...item, name: event.target.value }, onChange)}
          />
          <select
            value={item.kitchen_section_id || ""}
            onChange={(event) => updateArray(steps, index, { ...item, kitchen_section_id: Number(event.target.value) }, onChange)}
          >
            <option value="" disabled>Sekcja</option>
            {kitchenSections.map((section) => (
              <option key={section.id} value={section.id}>
                {section.name}
              </option>
            ))}
          </select>
          <input
            type="number"
            min={1}
            value={item.sequence}
            onChange={(event) => updateArray(steps, index, { ...item, sequence: Number(event.target.value) }, onChange)}
          />
          <input
            type="number"
            min={0}
            placeholder="Minuty"
            value={item.estimated_time ?? ""}
            onChange={(event) => updateArray(steps, index, { ...item, estimated_time: event.target.value ? Number(event.target.value) : null }, onChange)}
          />
          <select
            value={item.depends_on_sequence ?? ""}
            onChange={(event) =>
              updateArray(steps, index, {
                ...item,
                depends_on_sequence: event.target.value ? Number(event.target.value) : null,
              }, onChange)
            }
          >
            <option value="">Równolegle</option>
            {steps
              .filter((step) => step.sequence !== item.sequence)
              .sort((first, second) => first.sequence - second.sequence)
              .map((step) => (
                <option key={step.sequence} value={step.sequence}>
                  Po kroku {step.sequence}: {step.name || "bez nazwy"}
                </option>
              ))}
          </select>
          <textarea
            className="admin-step-description"
            placeholder="Opis"
            value={item.description ?? ""}
            onChange={(event) => updateArray(steps, index, { ...item, description: event.target.value }, onChange)}
          />
          <label className="switch-row compact">
            <input
              type="checkbox"
              checked={item.is_active}
              onChange={(event) => updateArray(steps, index, { ...item, is_active: event.target.checked }, onChange)}
            />
            Aktywny
          </label>
          <button type="button" className="danger-link" onClick={() => onChange(removeIndex(steps, index))}>
            Usuń
          </button>
        </div>
      ))}
      <small>
        Kroki równoległe liczą się po najdłuższym czasie. Kroki zależne doliczają się po wskazanym kroku.
      </small>
    </div>
  );
}

function DiscountEditor({
  discounts,
  form,
  onChange,
  onSave,
  onEdit,
  onDelete,
}: {
  discounts: AdminDiscount[];
  form: { id: number | null; name: string; type: string; value: string; is_active: boolean };
  onChange: (form: { id: number | null; name: string; type: string; value: string; is_active: boolean }) => void;
  onSave: () => Promise<void>;
  onEdit: (form: { id: number | null; name: string; type: string; value: string; is_active: boolean }) => void;
  onDelete: (discount: AdminDiscount) => Promise<void>;
}) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "16px", height: "100%" }}>
      <div className="warehouse-section-heading">
        <h2>Rabaty</h2>
      </div>

      <div style={{ display: "flex", flexWrap: "wrap", gap: "12px", background: "#f7fafc", padding: "16px", borderRadius: "8px", border: "1px dashed #cbd5e0", alignItems: "flex-end" }}>
        <label style={{ display: "flex", flexDirection: "column", gap: "4px", flex: 2, minWidth: "150px" }}>
          <span style={{ fontSize: "0.8rem", fontWeight: "bold", color: "#4a5568" }}>Nazwa rabatu</span>
          <input
            placeholder="np. Karta Stałego Klienta"
            value={form.name}
            onChange={(event) => onChange({ ...form, name: event.target.value })}
            style={{ padding: "8px 12px", borderRadius: "6px", border: "1px solid #cbd5e0" }}
          />
        </label>
        <label style={{ display: "flex", flexDirection: "column", gap: "4px", flex: 1, minWidth: "150px" }}>
          <span style={{ fontSize: "0.8rem", fontWeight: "bold", color: "#4a5568" }}>Typ rabatu</span>
          <select 
            value={form.type} 
            onChange={(event) => onChange({ ...form, type: event.target.value })}
            style={{ padding: "8px 12px", borderRadius: "6px", border: "1px solid #cbd5e0", height: "38px" }}
          >
            <option value="PERCENT">Procent (%)</option>
            <option value="FIXED">Kwota stała (PLN)</option>
          </select>
        </label>
        <label style={{ display: "flex", flexDirection: "column", gap: "4px", width: "100px" }}>
          <span style={{ fontSize: "0.8rem", fontWeight: "bold", color: "#4a5568" }}>Wartość</span>
          <input
            type="number"
            step="0.01"
            value={form.value}
            onChange={(event) => onChange({ ...form, value: event.target.value })}
            style={{ padding: "8px 12px", borderRadius: "6px", border: "1px solid #cbd5e0" }}
          />
        </label>
        <label className="switch-row compact" style={{ display: "flex", alignItems: "center", gap: "6px", height: "38px", margin: 0 }}>
          <input
            type="checkbox"
            checked={form.is_active}
            onChange={(event) => onChange({ ...form, is_active: event.target.checked })}
          />
          <span style={{ fontSize: "0.85rem" }}>Aktywny</span>
        </label>
        <div style={{ display: "flex", gap: "8px" }}>
          <button 
            type="button" 
            className="admin-primary" 
            style={{ height: "38px", padding: "0 16px", borderRadius: "6px", fontWeight: "bold" }}
            onClick={() => void onSave()}
          >
            {form.id === null ? "Utwórz" : "Zapisz"}
          </button>
          <button
            type="button"
            className="ghost-button"
            style={{ height: "38px", padding: "0 16px", borderRadius: "6px" }}
            onClick={() => onChange({ id: null, name: "", type: "PERCENT", value: "10.00", is_active: true })}
          >
            Anuluj
          </button>
        </div>
      </div>

      <div className="admin-discount-list" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: "10px", overflowY: "auto", flex: 1, paddingRight: "4px" }}>
        {discounts.map((discount) => (
          <div
            key={discount.id}
            className={`admin-discount-item ${!discount.is_active ? "inactive" : ""}`}
            onClick={() => onEdit(discount)}
            style={{ display: "flex", flexDirection: "column", gap: "6px", padding: "12px", border: "1px solid #d7dfda", borderRadius: "8px", background: discount.is_active ? "#ffffff" : "#fbfcfb", cursor: "pointer", position: "relative" }}
          >
            <strong>{discount.name}</strong>
            <small style={{ color: "#718096" }}>{discount.type === "PERCENT" ? `${discount.value}%` : money.format(Number(discount.value))}</small>
            <button
              type="button"
              className="danger-link"
              style={{ border: "none", background: "none", color: "#a83427", cursor: "pointer", alignSelf: "flex-end", padding: "4px", fontSize: "0.8rem", fontWeight: "bold" }}
              onClick={(event) => {
                event.stopPropagation();
                void onDelete(discount);
              }}
            >
              Usuń
            </button>
          </div>
        ))}
        {discounts.length === 0 && (
          <p style={{ color: "#718096", textAlign: "center", gridColumn: "1 / -1", marginTop: "20px" }}>Brak rabatów w systemie.</p>
        )}
      </div>
    </div>
  );
}

function ReferenceEditor({
  title,
  items,
  onCreate,
  onSave,
  onDelete,
}: {
  title: string;
  items: AdminIngredient[];
  onCreate: (name: string, unit: string) => Promise<void>;
  onSave: (item: AdminIngredient) => Promise<void>;
  onDelete: (item: AdminIngredient) => Promise<void> | undefined;
}) {
  const { confirm } = usePrompt();
  const [newName, setNewName] = useState("");
  const [newUnit, setNewUnit] = useState("g");
  const [searchQuery, setSearchQuery] = useState("");

  async function submit() {
    if (!newName.trim() || !newUnit.trim()) return;
    await onCreate(newName.trim(), newUnit.trim());
    setNewName("");
    setNewUnit("g");
  }

  const filteredItems = useMemo(() => {
    return items.filter((item) =>
      item.name.toLowerCase().includes(searchQuery.toLowerCase())
    );
  }, [items, searchQuery]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "16px", height: "100%" }}>
      <div className="warehouse-section-heading">
        <h2>{title}</h2>
      </div>

      <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
        <input
          value={searchQuery}
          onChange={(event) => setSearchQuery(event.target.value)}
          placeholder="Wyszukaj składnik..."
          style={{ flex: 1, padding: "8px 12px", borderRadius: "6px", border: "1px solid #cbd5e0" }}
        />
      </div>

      <div style={{ display: "flex", gap: "10px", alignItems: "center", background: "#f7fafc", padding: "12px", borderRadius: "8px", border: "1px dashed #cbd5e0" }}>
        <input
          value={newName}
          onChange={(event) => setNewName(event.target.value)}
          placeholder="Nazwa nowego składnika"
          style={{ flex: 2, padding: "8px 12px", borderRadius: "6px", border: "1px solid #cbd5e0" }}
        />
        <input
          value={newUnit}
          onChange={(event) => setNewUnit(event.target.value)}
          placeholder="Jednostka (np. g, ml, szt.)"
          style={{ flex: 1, padding: "8px 12px", borderRadius: "6px", border: "1px solid #cbd5e0" }}
        />
        <button
          type="button"
          className="admin-primary"
          style={{ display: "inline-flex", alignItems: "center", gap: "6px", padding: "8px 16px", borderRadius: "6px", height: "40px" }}
          onClick={() => void submit()}
        >
          <Plus size={16} /> Dodaj
        </button>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: "8px", overflowY: "auto", flex: 1, paddingRight: "4px" }}>
        {filteredItems.map((item) => (
          <div 
            key={item.id} 
            className={!item.is_active ? "inactive" : ""}
            style={{ display: "flex", gap: "10px", alignItems: "center", padding: "8px 12px", border: "1px solid #e2eae6", borderRadius: "8px", background: item.is_active ? "#ffffff" : "#f7fafc" }}
          >
            <input
              defaultValue={item.name}
              onBlur={(event) => void onSave({ ...item, name: event.target.value })}
              style={{ flex: 2, padding: "6px 10px", border: "1px solid transparent", background: "transparent", fontWeight: "bold" }}
              onFocus={(e) => e.target.style.border = "1px solid #cbd5e0"}
            />
            <input
              defaultValue={item.unit}
              onBlur={(event) => void onSave({ ...item, unit: event.target.value })}
              style={{ width: "80px", padding: "6px 10px", border: "1px solid transparent", background: "transparent", color: "#4a5568" }}
              onFocus={(e) => e.target.style.border = "1px solid #cbd5e0"}
            />
            <button
              type="button"
              className="stock-delete-button"
              title="Usuń"
              style={{ background: "none", border: "none", cursor: "pointer", display: "inline-flex", padding: "6px" }}
              onClick={async () => {
                const yes = await confirm({
                  title: "Potwierdź usunięcie składnika",
                  message: `Czy na pewno chcesz usunąc składnik "${item.name}"?`,
                  confirmText: "Usuń",
                  cancelText: "Anuluj",
                });
                if (yes) {
                  void onDelete(item);
                }
              }}
            >
              <Trash2 size={16} />
            </button>
          </div>
        ))}
        {filteredItems.length === 0 && (
          <p style={{ color: "#718096", textAlign: "center", marginTop: "20px" }}>Brak pasujących składników.</p>
        )}
      </div>
    </div>
  );
}

function ModifierEditor({
  title,
  items,
  onCreate,
  onSave,
  onDelete,
}: {
  title: string;
  items: AdminModifier[];
  onCreate: (name: string, price: string) => Promise<void>;
  onSave: (item: AdminModifier) => Promise<void>;
  onDelete: (item: AdminModifier) => Promise<void> | undefined;
}) {
  const { confirm } = usePrompt();
  const [newName, setNewName] = useState("");
  const [newPrice, setNewPrice] = useState("0.00");
  const [searchQuery, setSearchQuery] = useState("");

  async function submit() {
    if (!newName.trim() || !newPrice.trim()) return;
    await onCreate(newName.trim(), newPrice.trim());
    setNewName("");
    setNewPrice("0.00");
  }

  const filteredItems = useMemo(() => {
    return items.filter((item) =>
      item.name.toLowerCase().includes(searchQuery.toLowerCase())
    );
  }, [items, searchQuery]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "16px", height: "100%" }}>
      <div className="warehouse-section-heading">
        <h2>{title}</h2>
      </div>

      <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
        <input
          value={searchQuery}
          onChange={(event) => setSearchQuery(event.target.value)}
          placeholder="Wyszukaj modyfikator..."
          style={{ flex: 1, padding: "8px 12px", borderRadius: "6px", border: "1px solid #cbd5e0" }}
        />
      </div>

      <div style={{ display: "flex", gap: "10px", alignItems: "center", background: "#f7fafc", padding: "12px", borderRadius: "8px", border: "1px dashed #cbd5e0" }}>
        <input
          value={newName}
          onChange={(event) => setNewName(event.target.value)}
          placeholder="Nazwa nowego modyfikatora"
          style={{ flex: 2, padding: "8px 12px", borderRadius: "6px", border: "1px solid #cbd5e0" }}
        />
        <input
          type="number"
          step="0.01"
          value={newPrice}
          onChange={(event) => setNewPrice(event.target.value)}
          placeholder="Cena"
          style={{ width: "120px", padding: "8px 12px", borderRadius: "6px", border: "1px solid #cbd5e0" }}
        />
        <button
          type="button"
          className="admin-primary"
          style={{ display: "inline-flex", alignItems: "center", gap: "6px", padding: "8px 16px", borderRadius: "6px", height: "40px" }}
          onClick={() => void submit()}
        >
          <Plus size={16} /> Dodaj
        </button>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: "8px", overflowY: "auto", flex: 1, paddingRight: "4px" }}>
        {filteredItems.map((item) => (
          <div 
            key={item.id} 
            className={!item.is_active ? "inactive" : ""}
            style={{ display: "flex", gap: "10px", alignItems: "center", padding: "8px 12px", border: "1px solid #e2eae6", borderRadius: "8px", background: item.is_active ? "#ffffff" : "#f7fafc" }}
          >
            <input
              defaultValue={item.name}
              onBlur={(event) => void onSave({ ...item, name: event.target.value })}
              style={{ flex: 2, padding: "6px 10px", border: "1px solid transparent", background: "transparent", fontWeight: "bold" }}
              onFocus={(e) => e.target.style.border = "1px solid #cbd5e0"}
            />
            <input
              type="number"
              step="0.01"
              defaultValue={item.price}
              onBlur={(event) => void onSave({ ...item, price: event.target.value })}
              style={{ width: "100px", padding: "6px 10px", border: "1px solid transparent", background: "transparent", color: "#4a5568" }}
              onFocus={(e) => e.target.style.border = "1px solid #cbd5e0"}
            />
            <button
              type="button"
              className="stock-delete-button"
              title="Usuń"
              style={{ background: "none", border: "none", cursor: "pointer", display: "inline-flex", padding: "6px" }}
              onClick={async () => {
                const yes = await confirm({
                  title: "Potwierdź usunięcie modyfikatora",
                  message: `Czy na pewno chcesz usunąć modyfikator "${item.name}"?`,
                  confirmText: "Usuń",
                  cancelText: "Anuluj",
                });
                if (yes) {
                  void onDelete(item);
                }
              }}
            >
              <Trash2 size={16} />
            </button>
          </div>
        ))}
        {filteredItems.length === 0 && (
          <p style={{ color: "#718096", textAlign: "center", marginTop: "20px" }}>Brak pasujących modyfikatorów.</p>
        )}
      </div>
    </div>
  );
}

function createEmptyProductForm(categoryId = 0): ProductFormState {
  return {
    id: null,
    category_id: categoryId,
    kitchen_section_id: null,
    warehouse_id: null,
    name: "",
    description: "",
    image_url: null,
    price: "0.00",
    vat_rate: "8.00",
    preparation_time: null,
    is_active: true,
    ingredients: [],
    modifiers: [],
    kitchen_steps: [],
  };
}

function createEmptyCategoryForm(
  parentCategoryId: number | null = null,
  department: "KITCHEN" | "BAR" = "KITCHEN",
): CategoryFormState {
  return {
    id: null,
    name: "",
    parent_category_id: parentCategoryId,
    department,
    is_active: true,
  };
}

function productToForm(product: AdminProduct): ProductFormState {
  return {
    id: product.id,
    category_id: product.category_id,
    kitchen_section_id: product.kitchen_section_id,
    warehouse_id: product.warehouse_id,
    name: product.name,
    description: product.description ?? "",
    image_url: product.image_url,
    price: product.price,
    vat_rate: product.vat_rate,
    preparation_time: product.preparation_time,
    is_active: product.is_active,
    ingredients: product.ingredients.map((item) => ({
      id: item.id,
      ingredient_id: item.ingredient_id,
      ingredient_name: item.ingredient_name,
      unit: item.unit,
      quantity: item.quantity,
    })),
    modifiers: product.modifiers.map((item) => ({
      id: item.id,
      modifier_id: item.modifier_id,
      modifier_name: item.modifier_name,
      modifier_price: item.modifier_price,
      price_override: item.price_override,
      stock_ingredient_id: item.stock_ingredient_id,
      stock_ingredient_name: item.stock_ingredient_name,
      stock_ingredient_unit: item.stock_ingredient_unit,
      stock_quantity: item.stock_quantity,
      replaces_ingredient_id: item.replaces_ingredient_id,
      replaces_ingredient_name: item.replaces_ingredient_name,
      is_active: item.is_active,
    })),
    kitchen_steps: product.kitchen_steps.map((item) => ({
      id: item.id,
      kitchen_section_id: item.kitchen_section_id,
      kitchen_section_name: item.kitchen_section_name,
      name: item.name,
      description: item.description,
      sequence: item.sequence,
      estimated_time: item.estimated_time,
      depends_on_sequence: item.depends_on_sequence ?? null,
      is_active: item.is_active,
    })),
  };
}

function formToPayload(form: ProductFormState): AdminProductPayload {
  return {
    category_id: form.category_id,
    kitchen_section_id: form.kitchen_section_id,
    warehouse_id: form.warehouse_id,
    name: form.name.trim(),
    description: form.description?.trim() || null,
    image_url: form.image_url,
    price: form.price || "0.00",
    vat_rate: form.vat_rate || "8.00",
    preparation_time: form.preparation_time,
    is_active: form.is_active,
    ingredients: form.ingredients.filter((item) => item.ingredient_id || item.ingredient_name),
    modifiers: form.modifiers.filter((item) => item.modifier_id || item.modifier_name),
    kitchen_steps: form.kitchen_steps.filter((item) => item.name && item.kitchen_section_id),
  };
}

function emptyIngredient(): AdminProductIngredient {
  return {
    ingredient_id: null,
    ingredient_name: "",
    unit: "g",
    quantity: "1.00",
  };
}

function emptyModifier(): AdminProductModifier {
  return {
    modifier_id: null,
    modifier_name: "",
    modifier_price: "0.00",
    price_override: null,
    stock_ingredient_id: null,
    stock_ingredient_name: null,
    stock_ingredient_unit: null,
    stock_quantity: null,
    replaces_ingredient_id: null,
    replaces_ingredient_name: null,
    is_active: true,
  };
}

function emptyStep(sectionId: number, sequence: number): AdminProductStep {
  return {
    kitchen_section_id: sectionId,
    name: "",
    description: "",
    sequence,
    estimated_time: null,
    depends_on_sequence: null,
    is_active: true,
  };
}

function updateArray<T>(items: T[], index: number, nextItem: T, onChange: (items: T[]) => void) {
  onChange(items.map((item, itemIndex) => (itemIndex === index ? nextItem : item)));
}

function removeIndex<T>(items: T[], index: number): T[] {
  return items.filter((_, itemIndex) => itemIndex !== index);
}
