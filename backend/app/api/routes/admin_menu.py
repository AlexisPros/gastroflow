from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload

from app.api.deps import ADMIN, DbSession, require_roles
from app.core.config import settings
from app.models.discount import Discount
from app.models.ingredient import Ingredient
from app.models.kitchen_section import KitchenSection
from app.models.modifier import Modifier
from app.models.product import Product
from app.models.product_category import ProductCategory
from app.models.product_ingredient import ProductIngredient
from app.models.product_kitchen_step import ProductKitchenStep
from app.models.product_modifier import ProductModifier

router = APIRouter(
    prefix="/admin/menu",
    tags=["Admin menu"],
    dependencies=[Depends(require_roles({ADMIN}))],
)

IMAGE_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


class MenuImageUploadRead(BaseModel):
    image_url: str


class AdminCategoryBase(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    parent_category_id: int | None = None
    department: str = "KITCHEN"
    is_active: bool = True


class AdminCategoryCreate(AdminCategoryBase):
    pass


class AdminCategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    parent_category_id: int | None = None
    department: str | None = None
    is_active: bool | None = None


class AdminCategoryRead(AdminCategoryBase):
    id: int


class AdminIngredientBase(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    unit: str = Field(min_length=1, max_length=50)
    is_active: bool = True


class AdminIngredientCreate(AdminIngredientBase):
    pass


class AdminIngredientUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    unit: str | None = Field(default=None, min_length=1, max_length=50)
    is_active: bool | None = None


class AdminIngredientRead(AdminIngredientBase):
    id: int


class AdminModifierBase(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    price: Decimal = Decimal("0.00")
    is_active: bool = True


class AdminModifierCreate(AdminModifierBase):
    pass


class AdminModifierUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    price: Decimal | None = None
    is_active: bool | None = None


class AdminModifierRead(AdminModifierBase):
    id: int


class AdminProductIngredientInput(BaseModel):
    id: int | None = None
    ingredient_id: int | None = None
    ingredient_name: str | None = Field(default=None, max_length=150)
    unit: str | None = Field(default=None, max_length=50)
    quantity: Decimal = Field(gt=Decimal("0"))


class AdminProductIngredientRead(BaseModel):
    id: int
    ingredient_id: int
    ingredient_name: str
    unit: str
    quantity: Decimal


class AdminProductModifierInput(BaseModel):
    id: int | None = None
    modifier_id: int | None = None
    modifier_name: str | None = Field(default=None, max_length=150)
    modifier_price: Decimal = Decimal("0.00")
    price_override: Decimal | None = None
    is_active: bool = True


class AdminProductModifierRead(BaseModel):
    id: int
    modifier_id: int
    modifier_name: str
    modifier_price: Decimal
    price_override: Decimal | None
    is_active: bool


class AdminProductStepInput(BaseModel):
    id: int | None = None
    kitchen_section_id: int
    name: str = Field(min_length=1, max_length=150)
    description: str | None = None
    sequence: int = Field(default=1, ge=1)
    estimated_time: int | None = Field(default=None, ge=0)
    depends_on_sequence: int | None = Field(default=None, ge=1)
    is_active: bool = True


class AdminProductStepRead(BaseModel):
    id: int
    kitchen_section_id: int
    kitchen_section_name: str
    name: str
    description: str | None
    sequence: int
    estimated_time: int | None
    depends_on_sequence: int | None
    is_active: bool


class AdminProductBase(BaseModel):
    category_id: int
    kitchen_section_id: int | None = None
    name: str = Field(min_length=1, max_length=150)
    description: str | None = None
    image_url: str | None = None
    price: Decimal = Field(ge=Decimal("0"))
    vat_rate: Decimal = Decimal("8.00")
    preparation_time: int | None = Field(default=None, ge=0)
    is_active: bool = True
    ingredients: list[AdminProductIngredientInput] = Field(default_factory=list)
    modifiers: list[AdminProductModifierInput] = Field(default_factory=list)
    kitchen_steps: list[AdminProductStepInput] = Field(default_factory=list)


class AdminProductCreate(AdminProductBase):
    pass


class AdminProductUpdate(BaseModel):
    category_id: int | None = None
    kitchen_section_id: int | None = None
    name: str | None = Field(default=None, min_length=1, max_length=150)
    description: str | None = None
    image_url: str | None = None
    price: Decimal | None = Field(default=None, ge=Decimal("0"))
    vat_rate: Decimal | None = None
    preparation_time: int | None = Field(default=None, ge=0)
    is_active: bool | None = None
    ingredients: list[AdminProductIngredientInput] | None = None
    modifiers: list[AdminProductModifierInput] | None = None
    kitchen_steps: list[AdminProductStepInput] | None = None


class AdminProductRead(BaseModel):
    id: int
    category_id: int
    kitchen_section_id: int | None
    name: str
    description: str | None
    image_url: str | None
    price: Decimal
    vat_rate: Decimal
    preparation_time: int | None
    is_active: bool
    ingredients: list[AdminProductIngredientRead]
    modifiers: list[AdminProductModifierRead]
    kitchen_steps: list[AdminProductStepRead]


class AdminKitchenSectionRead(BaseModel):
    id: int
    name: str
    is_active: bool


class AdminDiscountBase(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    type: str = Field(pattern="^(PERCENT|FIXED|AMOUNT|PERCENTAGE)$")
    value: Decimal = Field(ge=Decimal("0"))
    is_active: bool = True


class AdminDiscountCreate(AdminDiscountBase):
    pass


class AdminDiscountUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    type: str | None = Field(default=None, pattern="^(PERCENT|FIXED|AMOUNT|PERCENTAGE)$")
    value: Decimal | None = Field(default=None, ge=Decimal("0"))
    is_active: bool | None = None


class AdminDiscountRead(AdminDiscountBase):
    id: int


class AdminMenuRead(BaseModel):
    categories: list[AdminCategoryRead]
    products: list[AdminProductRead]
    ingredients: list[AdminIngredientRead]
    modifiers: list[AdminModifierRead]
    kitchen_sections: list[AdminKitchenSectionRead]
    discounts: list[AdminDiscountRead]


@router.get("", response_model=AdminMenuRead)
async def get_admin_menu(db: DbSession) -> AdminMenuRead:
    categories = await _list_categories(db)
    ingredients = await _list_ingredients(db)
    modifiers = await _list_modifiers(db)
    kitchen_sections = await _list_kitchen_sections(db)
    discounts = await _list_discounts(db)
    products = await _list_products(db)

    return AdminMenuRead(
        categories=[_category_read(item) for item in categories],
        products=[_product_read(item) for item in products],
        ingredients=[_ingredient_read(item) for item in ingredients],
        modifiers=[_modifier_read(item) for item in modifiers],
        kitchen_sections=[_kitchen_section_read(item) for item in kitchen_sections],
        discounts=[_discount_read(item) for item in discounts],
    )


@router.post("/uploads/images", response_model=MenuImageUploadRead)
async def upload_menu_image(file: UploadFile = File(...)) -> MenuImageUploadRead:
    extension = IMAGE_EXTENSIONS.get(file.content_type or "")
    if extension is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only JPG, PNG and WEBP images are supported.",
        )

    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Image is too large. Maximum size is 5 MB.",
        )

    target_dir = _menu_images_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid4().hex}{extension}"
    target_path = target_dir / filename
    target_path.write_bytes(content)

    return MenuImageUploadRead(
        image_url=f"{settings.MENU_IMAGES_PUBLIC_PATH.rstrip('/')}/{filename}",
    )


@router.post("/categories", response_model=AdminCategoryRead, status_code=status.HTTP_201_CREATED)
async def create_category(body: AdminCategoryCreate, db: DbSession) -> AdminCategoryRead:
    parent = await _get_parent_category(db, body.parent_category_id)
    category = ProductCategory(
        name=body.name.strip(),
        parent_category_id=body.parent_category_id,
        department=parent.department if parent is not None else _normalize_category_department(body.department),
        is_active=body.is_active,
    )
    db.add(category)
    await db.commit()
    await db.refresh(category)
    return _category_read(category)


@router.patch("/categories/{category_id}", response_model=AdminCategoryRead)
async def update_category(
    category_id: int,
    body: AdminCategoryUpdate,
    db: DbSession,
) -> AdminCategoryRead:
    category = await _get_category_or_404(db, category_id)
    data = body.model_dump(exclude_unset=True)
    if "parent_category_id" in data:
        if data["parent_category_id"] == category_id:
            raise HTTPException(status_code=400, detail="Category cannot be its own parent.")
        await _get_parent_category(db, data["parent_category_id"])
        if data["parent_category_id"] is not None and await _is_descendant_category(
            db,
            category_id=category_id,
            possible_child_id=data["parent_category_id"],
        ):
            raise HTTPException(status_code=400, detail="Category cannot use its child as parent.")

    for field, value in data.items():
        if field == "department" and value is not None:
            value = _normalize_category_department(value)
        setattr(category, field, value.strip() if isinstance(value, str) else value)

    if category.parent_category_id is not None:
        parent = await _get_category_or_404(db, category.parent_category_id)
        category.department = parent.department

    await _sync_child_category_departments(db, category)

    db.add(category)
    await db.commit()
    await db.refresh(category)
    return _category_read(category)


@router.delete("/categories/{category_id}", response_model=AdminCategoryRead)
async def delete_category(category_id: int, db: DbSession) -> AdminCategoryRead:
    category = await _get_category_or_404(db, category_id)
    category_ids = await _collect_category_tree_ids(db, category_id)

    products = (
        await db.execute(select(Product).where(Product.category_id.in_(category_ids)))
    ).scalars().all()
    for product in products:
        product.is_active = False
        db.add(product)

    categories = (
        await db.execute(select(ProductCategory).where(ProductCategory.id.in_(category_ids)))
    ).scalars().all()
    for item in categories:
        item.is_active = False
        db.add(item)

    await db.commit()
    await db.refresh(category)
    return _category_read(category)


@router.post("/ingredients", response_model=AdminIngredientRead, status_code=status.HTTP_201_CREATED)
async def create_ingredient(body: AdminIngredientCreate, db: DbSession) -> AdminIngredientRead:
    ingredient = Ingredient(
        name=body.name.strip(),
        unit=body.unit.strip(),
        is_active=body.is_active,
    )
    db.add(ingredient)
    await db.commit()
    await db.refresh(ingredient)
    return _ingredient_read(ingredient)


@router.patch("/ingredients/{ingredient_id}", response_model=AdminIngredientRead)
async def update_ingredient(
    ingredient_id: int,
    body: AdminIngredientUpdate,
    db: DbSession,
) -> AdminIngredientRead:
    ingredient = await _get_ingredient_or_404(db, ingredient_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(ingredient, field, value.strip() if isinstance(value, str) else value)
    db.add(ingredient)
    await db.commit()
    await db.refresh(ingredient)
    return _ingredient_read(ingredient)


@router.delete("/ingredients/{ingredient_id}", response_model=AdminIngredientRead)
async def delete_ingredient(ingredient_id: int, db: DbSession) -> AdminIngredientRead:
    ingredient = await _get_ingredient_or_404(db, ingredient_id)
    ingredient.is_active = False
    db.add(ingredient)
    await db.commit()
    await db.refresh(ingredient)
    return _ingredient_read(ingredient)


@router.post("/modifiers", response_model=AdminModifierRead, status_code=status.HTTP_201_CREATED)
async def create_modifier(body: AdminModifierCreate, db: DbSession) -> AdminModifierRead:
    modifier = Modifier(
        name=body.name.strip(),
        price=body.price,
        is_active=body.is_active,
    )
    db.add(modifier)
    await db.commit()
    await db.refresh(modifier)
    return _modifier_read(modifier)


@router.patch("/modifiers/{modifier_id}", response_model=AdminModifierRead)
async def update_modifier(
    modifier_id: int,
    body: AdminModifierUpdate,
    db: DbSession,
) -> AdminModifierRead:
    modifier = await _get_modifier_or_404(db, modifier_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(modifier, field, value.strip() if isinstance(value, str) else value)
    db.add(modifier)
    await db.commit()
    await db.refresh(modifier)
    return _modifier_read(modifier)


@router.delete("/modifiers/{modifier_id}", response_model=AdminModifierRead)
async def delete_modifier(modifier_id: int, db: DbSession) -> AdminModifierRead:
    modifier = await _get_modifier_or_404(db, modifier_id)
    modifier.is_active = False
    for link in modifier.product_modifiers:
        link.is_active = False
        db.add(link)
    db.add(modifier)
    await db.commit()
    await db.refresh(modifier)
    return _modifier_read(modifier)


@router.post("/products", response_model=AdminProductRead, status_code=status.HTTP_201_CREATED)
async def create_product(body: AdminProductCreate, db: DbSession) -> AdminProductRead:
    await _ensure_category(db, body.category_id)
    await _ensure_kitchen_section(db, body.kitchen_section_id)
    product = Product(
        category_id=body.category_id,
        kitchen_section_id=body.kitchen_section_id,
        name=body.name.strip(),
        description=body.description,
        image_url=body.image_url,
        price=body.price,
        vat_rate=body.vat_rate,
        preparation_time=body.preparation_time,
        is_active=body.is_active,
    )
    db.add(product)
    await db.flush()
    await _sync_product_children(db, product=product, body=body)
    await db.commit()
    return await _reload_product_read(db, product.id)


@router.patch("/products/{product_id}", response_model=AdminProductRead)
async def update_product(
    product_id: int,
    body: AdminProductUpdate,
    db: DbSession,
) -> AdminProductRead:
    product = await _get_product_or_404(db, product_id)
    data = body.model_dump(exclude_unset=True)

    if "category_id" in data:
        await _ensure_category(db, data["category_id"])
    if "kitchen_section_id" in data:
        await _ensure_kitchen_section(db, data["kitchen_section_id"])

    for field in [
        "category_id",
        "kitchen_section_id",
        "name",
        "description",
        "image_url",
        "price",
        "vat_rate",
        "preparation_time",
        "is_active",
    ]:
        if field in data:
            value = data[field]
            setattr(product, field, value.strip() if isinstance(value, str) else value)

    db.add(product)
    await _sync_product_children(db, product=product, body=body)
    await db.commit()
    return await _reload_product_read(db, product.id)


@router.delete("/products/{product_id}", response_model=AdminProductRead)
async def delete_product(product_id: int, db: DbSession) -> AdminProductRead:
    product = await _get_product_or_404(db, product_id)
    product.is_active = False
    for link in product.product_modifiers:
        link.is_active = False
        db.add(link)
    for step in product.kitchen_steps:
        step.is_active = False
        db.add(step)
    db.add(product)
    await db.commit()
    return await _reload_product_read(db, product.id)


@router.post("/discounts", response_model=AdminDiscountRead, status_code=status.HTTP_201_CREATED)
async def create_discount(body: AdminDiscountCreate, db: DbSession) -> AdminDiscountRead:
    discount = Discount(
        name=body.name.strip(),
        type=_normalize_discount_type(body.type),
        value=body.value,
        is_active=body.is_active,
    )
    db.add(discount)
    await db.commit()
    await db.refresh(discount)
    return _discount_read(discount)


@router.patch("/discounts/{discount_id}", response_model=AdminDiscountRead)
async def update_discount(
    discount_id: int,
    body: AdminDiscountUpdate,
    db: DbSession,
) -> AdminDiscountRead:
    discount = await _get_discount_or_404(db, discount_id)
    data = body.model_dump(exclude_unset=True)
    if "type" in data and data["type"] is not None:
        data["type"] = _normalize_discount_type(data["type"])
    for field, value in data.items():
        setattr(discount, field, value.strip() if isinstance(value, str) else value)
    db.add(discount)
    await db.commit()
    await db.refresh(discount)
    return _discount_read(discount)


@router.delete("/discounts/{discount_id}", response_model=AdminDiscountRead)
async def delete_discount(discount_id: int, db: DbSession) -> AdminDiscountRead:
    discount = await _get_discount_or_404(db, discount_id)
    discount.is_active = False
    db.add(discount)
    await db.commit()
    await db.refresh(discount)
    return _discount_read(discount)


async def _sync_product_children(
    db: DbSession,
    *,
    product: Product,
    body: AdminProductCreate | AdminProductUpdate,
) -> None:
    if body.kitchen_steps is not None:
        step_sequences = [step.sequence for step in body.kitchen_steps]
        if len(step_sequences) != len(set(step_sequences)):
            raise HTTPException(status_code=400, detail="Kitchen step sequences must be unique.")
        valid_sequences = set(step_sequences)
        for step in body.kitchen_steps:
            if step.depends_on_sequence is None:
                continue
            if step.depends_on_sequence == step.sequence:
                raise HTTPException(status_code=400, detail="Kitchen step cannot depend on itself.")
            if step.depends_on_sequence not in valid_sequences:
                raise HTTPException(status_code=400, detail="Kitchen step dependency must reference another step.")

    if body.ingredients is not None:
        await db.execute(
            delete(ProductIngredient).where(ProductIngredient.product_id == product.id),
        )
        await db.flush()
        for item in body.ingredients:
            ingredient = await _resolve_ingredient(db, item)
            db.add(
                ProductIngredient(
                    product_id=product.id,
                    ingredient_id=ingredient.id,
                    quantity=item.quantity,
                ),
            )

    if body.modifiers is not None:
        existing_links = list(
            (
                await db.execute(
                    select(ProductModifier).where(ProductModifier.product_id == product.id),
                )
            ).scalars().all(),
        )
        existing = {item.id: item for item in existing_links}
        seen_ids: set[int] = set()
        for item in body.modifiers:
            modifier = await _resolve_modifier(db, item)
            link = existing.get(item.id) if item.id is not None else None
            if link is None:
                link = ProductModifier(product_id=product.id, modifier_id=modifier.id)
            link.modifier_id = modifier.id
            link.price_override = item.price_override
            link.is_active = item.is_active
            db.add(link)
            await db.flush()
            seen_ids.add(link.id)
        for link in existing_links:
            if link.id not in seen_ids:
                link.is_active = False
                db.add(link)

    if body.kitchen_steps is not None:
        existing_steps = list(
            (
                await db.execute(
                    select(ProductKitchenStep).where(
                        ProductKitchenStep.product_id == product.id,
                    ),
                )
            ).scalars().all(),
        )
        existing_by_id = {item.id: item for item in existing_steps}
        existing_by_sequence = {item.sequence: item for item in existing_steps}
        for step in existing_steps:
            step.sequence = -step.id
            db.add(step)
        await db.flush()
        seen_ids: set[int] = set()
        for item in sorted(body.kitchen_steps, key=lambda step: step.sequence):
            await _ensure_kitchen_section(db, item.kitchen_section_id)
            step = existing_by_id.get(item.id) if item.id is not None else None
            if step is None:
                step = existing_by_sequence.get(item.sequence)
            if step is None:
                step = ProductKitchenStep(product_id=product.id, sequence=item.sequence)
            step.product_id = product.id
            step.kitchen_section_id = item.kitchen_section_id
            step.name = item.name.strip()
            step.description = item.description
            step.sequence = item.sequence
            step.estimated_time = item.estimated_time
            step.depends_on_sequence = item.depends_on_sequence
            step.is_active = item.is_active
            db.add(step)
            await db.flush()
            seen_ids.add(step.id)
        for step in existing_steps:
            if step.id not in seen_ids:
                step.is_active = False
                db.add(step)

    await db.flush()


async def _resolve_ingredient(
    db: DbSession,
    item: AdminProductIngredientInput,
) -> Ingredient:
    if item.ingredient_id is not None:
        ingredient = await _get_ingredient_or_404(db, item.ingredient_id)
        if item.ingredient_name:
            ingredient.name = item.ingredient_name.strip()
        if item.unit:
            ingredient.unit = item.unit.strip()
        ingredient.is_active = True
        db.add(ingredient)
        await db.flush()
        return ingredient

    if not item.ingredient_name or not item.unit:
        raise HTTPException(status_code=400, detail="Ingredient name and unit are required.")

    result = await db.execute(
        select(Ingredient).where(
            Ingredient.name == item.ingredient_name.strip(),
            Ingredient.unit == item.unit.strip(),
        ),
    )
    ingredient = result.scalar_one_or_none()
    if ingredient is None:
        ingredient = Ingredient(
            name=item.ingredient_name.strip(),
            unit=item.unit.strip(),
            is_active=True,
        )
    else:
        ingredient.is_active = True
    db.add(ingredient)
    await db.flush()
    return ingredient


async def _resolve_modifier(
    db: DbSession,
    item: AdminProductModifierInput,
) -> Modifier:
    if item.modifier_id is not None:
        modifier = await _get_modifier_or_404(db, item.modifier_id)
        if item.modifier_name:
            modifier.name = item.modifier_name.strip()
        modifier.price = item.modifier_price
        modifier.is_active = True
        db.add(modifier)
        await db.flush()
        return modifier

    if not item.modifier_name:
        raise HTTPException(status_code=400, detail="Modifier name is required.")

    result = await db.execute(select(Modifier).where(Modifier.name == item.modifier_name.strip()))
    modifier = result.scalar_one_or_none()
    if modifier is None:
        modifier = Modifier(
            name=item.modifier_name.strip(),
            price=item.modifier_price,
            is_active=True,
        )
    else:
        modifier.price = item.modifier_price
        modifier.is_active = True
    db.add(modifier)
    await db.flush()
    return modifier


async def _reload_product_read(db: DbSession, product_id: int) -> AdminProductRead:
    result = await db.execute(
        select(Product)
        .where(Product.id == product_id)
        .options(
            selectinload(Product.product_ingredients).selectinload(ProductIngredient.ingredient),
            selectinload(Product.product_modifiers).selectinload(ProductModifier.modifier),
            selectinload(Product.kitchen_steps).selectinload(ProductKitchenStep.kitchen_section),
        )
        .execution_options(populate_existing=True),
    )
    product = result.scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found.")
    return _product_read(product)


async def _list_categories(db: DbSession) -> list[ProductCategory]:
    result = await db.execute(select(ProductCategory).order_by(ProductCategory.name))
    return list(result.scalars().all())


async def _list_ingredients(db: DbSession) -> list[Ingredient]:
    result = await db.execute(select(Ingredient).order_by(Ingredient.name))
    return list(result.scalars().all())


async def _list_modifiers(db: DbSession) -> list[Modifier]:
    result = await db.execute(
        select(Modifier)
        .options(selectinload(Modifier.product_modifiers))
        .order_by(Modifier.name),
    )
    return list(result.scalars().all())


async def _list_kitchen_sections(db: DbSession) -> list[KitchenSection]:
    result = await db.execute(select(KitchenSection).order_by(KitchenSection.name))
    return list(result.scalars().all())


async def _list_discounts(db: DbSession) -> list[Discount]:
    result = await db.execute(select(Discount).order_by(Discount.name))
    return list(result.scalars().all())


async def _list_products(db: DbSession) -> list[Product]:
    result = await db.execute(
        select(Product)
        .options(
            selectinload(Product.product_ingredients).selectinload(ProductIngredient.ingredient),
            selectinload(Product.product_modifiers).selectinload(ProductModifier.modifier),
            selectinload(Product.kitchen_steps).selectinload(ProductKitchenStep.kitchen_section),
        )
        .order_by(Product.name),
    )
    return list(result.scalars().all())


async def _get_category_or_404(db: DbSession, category_id: int) -> ProductCategory:
    category = await db.get(ProductCategory, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found.")
    return category


async def _get_product_or_404(db: DbSession, product_id: int) -> Product:
    product = await db.get(
        Product,
        product_id,
        options=[
            selectinload(Product.product_ingredients).selectinload(ProductIngredient.ingredient),
            selectinload(Product.product_modifiers).selectinload(ProductModifier.modifier),
            selectinload(Product.kitchen_steps).selectinload(ProductKitchenStep.kitchen_section),
        ],
    )
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found.")
    return product


async def _get_ingredient_or_404(db: DbSession, ingredient_id: int) -> Ingredient:
    ingredient = await db.get(Ingredient, ingredient_id)
    if ingredient is None:
        raise HTTPException(status_code=404, detail="Ingredient not found.")
    return ingredient


async def _get_modifier_or_404(db: DbSession, modifier_id: int) -> Modifier:
    modifier = await db.get(
        Modifier,
        modifier_id,
        options=[selectinload(Modifier.product_modifiers)],
    )
    if modifier is None:
        raise HTTPException(status_code=404, detail="Modifier not found.")
    return modifier


async def _get_discount_or_404(db: DbSession, discount_id: int) -> Discount:
    discount = await db.get(Discount, discount_id)
    if discount is None:
        raise HTTPException(status_code=404, detail="Discount not found.")
    return discount


async def _get_parent_category(db: DbSession, category_id: int | None) -> ProductCategory | None:
    if category_id is None:
        return None
    return await _get_category_or_404(db, category_id)


async def _ensure_category(db: DbSession, category_id: int) -> None:
    await _get_category_or_404(db, category_id)


def _normalize_category_department(department: str) -> str:
    normalized = department.upper()
    if normalized not in {"KITCHEN", "BAR"}:
        raise HTTPException(status_code=400, detail="Category department must be KITCHEN or BAR.")
    return normalized


async def _sync_child_category_departments(db: DbSession, root_category: ProductCategory) -> None:
    result = await db.execute(select(ProductCategory))
    categories = list(result.scalars().all())
    parent_ids = {root_category.id}
    changed = True
    while changed:
        changed = False
        for category in categories:
            if category.parent_category_id in parent_ids and category.department != root_category.department:
                category.department = root_category.department
                db.add(category)
                parent_ids.add(category.id)
                changed = True
            elif category.parent_category_id in parent_ids and category.id not in parent_ids:
                parent_ids.add(category.id)
                changed = True


async def _ensure_kitchen_section(db: DbSession, section_id: int | None) -> None:
    if section_id is None:
        return
    section = await db.get(KitchenSection, section_id)
    if section is None:
        raise HTTPException(status_code=404, detail="Kitchen section not found.")


async def _collect_category_tree_ids(db: DbSession, category_id: int) -> set[int]:
    result = await db.execute(select(ProductCategory))
    categories = list(result.scalars().all())
    ids = {category_id}
    changed = True
    while changed:
        changed = False
        for category in categories:
            if category.parent_category_id in ids and category.id not in ids:
                ids.add(category.id)
                changed = True
    return ids


async def _is_descendant_category(
    db: DbSession,
    *,
    category_id: int,
    possible_child_id: int,
) -> bool:
    category_ids = await _collect_category_tree_ids(db, category_id)
    return possible_child_id in category_ids


def _category_read(category: ProductCategory) -> AdminCategoryRead:
    return AdminCategoryRead(
        id=category.id,
        name=category.name,
        parent_category_id=category.parent_category_id,
        department=category.department,
        is_active=category.is_active,
    )


def _ingredient_read(ingredient: Ingredient) -> AdminIngredientRead:
    return AdminIngredientRead(
        id=ingredient.id,
        name=ingredient.name,
        unit=ingredient.unit,
        is_active=ingredient.is_active,
    )


def _modifier_read(modifier: Modifier) -> AdminModifierRead:
    return AdminModifierRead(
        id=modifier.id,
        name=modifier.name,
        price=modifier.price,
        is_active=modifier.is_active,
    )


def _kitchen_section_read(section: KitchenSection) -> AdminKitchenSectionRead:
    return AdminKitchenSectionRead(
        id=section.id,
        name=section.name,
        is_active=section.is_active,
    )


def _discount_read(discount: Discount) -> AdminDiscountRead:
    return AdminDiscountRead(
        id=discount.id,
        name=discount.name,
        type=discount.type,
        value=discount.value,
        is_active=discount.is_active,
    )


def _product_read(product: Product) -> AdminProductRead:
    return AdminProductRead(
        id=product.id,
        category_id=product.category_id,
        kitchen_section_id=product.kitchen_section_id,
        name=product.name,
        description=product.description,
        image_url=product.image_url,
        price=product.price,
        vat_rate=product.vat_rate,
        preparation_time=product.preparation_time,
        is_active=product.is_active,
        ingredients=[
            AdminProductIngredientRead(
                id=item.id,
                ingredient_id=item.ingredient_id,
                ingredient_name=item.ingredient.name,
                unit=item.ingredient.unit,
                quantity=item.quantity,
            )
            for item in product.product_ingredients
        ],
        modifiers=[
            AdminProductModifierRead(
                id=item.id,
                modifier_id=item.modifier_id,
                modifier_name=item.modifier.name,
                modifier_price=item.modifier.price,
                price_override=item.price_override,
                is_active=item.is_active,
            )
            for item in product.product_modifiers
        ],
        kitchen_steps=[
            AdminProductStepRead(
                id=item.id,
                kitchen_section_id=item.kitchen_section_id,
                kitchen_section_name=item.kitchen_section.name,
                name=item.name,
                description=item.description,
                sequence=item.sequence,
                estimated_time=item.estimated_time,
                depends_on_sequence=item.depends_on_sequence,
                is_active=item.is_active,
            )
            for item in sorted(product.kitchen_steps, key=lambda step: step.sequence)
        ],
    )


def _normalize_discount_type(discount_type: str) -> str:
    normalized = discount_type.upper()
    if normalized == "PERCENTAGE":
        return "PERCENT"
    if normalized == "AMOUNT":
        return "FIXED"
    return normalized


def _menu_images_dir() -> Path:
    target_dir = Path(settings.MENU_IMAGES_DIR)
    if target_dir.is_absolute():
        return target_dir
    project_root = Path(__file__).resolve().parents[4]
    return project_root / target_dir
