# GastroFlow

GastroFlow is a restaurant POS prototype with a FastAPI backend, PostgreSQL database, SQLAlchemy ORM, JWT authorization, CRUD endpoints, business services, floor plan support, and mock fiscal/invoice generation.

## Backend Quick Start

Run commands from the project root:

```bash
cd backend
```

Create demo data:

```bash
./.venv/bin/python scripts/seed_dev_data.py
```

Start the backend:

```bash
./.venv/bin/uvicorn app.main:app --reload
```

Open Swagger:

```text
http://127.0.0.1:8000/docs
```

## Demo Users

All seeded users use the same password and PIN:

```text
password: demo1234
PIN: 1234
```

Available demo accounts:

```text
admin@gastroflow.dev
manager@gastroflow.dev
waiter@gastroflow.dev
kitchen@gastroflow.dev
bar@gastroflow.dev
```

## Swagger Authorization

In Swagger, click `Authorize` and enter:

```text
username: admin@gastroflow.dev
password: demo1234
```

Leave `client_id` and `client_secret` empty.

The JSON login endpoint is also available for the future frontend:

```text
POST /api/v1/auth/login
```

Body:

```json
{
  "email": "admin@gastroflow.dev",
  "password": "demo1234"
}
```

Fast PIN login for an already selected shift user:

```text
POST /api/v1/auth/pin-login
```

Body:

```json
{
  "user_id": 1,
  "pin": "1234"
}
```

## Manual API Smoke Test

Use this flow in Swagger to check the main POS scenario.

1. Check the active floor plan:

```text
GET /api/v1/floor-plans/active
```

Save the returned floor plan `id`.

2. Create a restaurant table from the floor plan editor flow:

```text
POST /api/v1/floor-plans/{floor_plan_id}/tables/create-restaurant-table
```

Example body:

```json
{
  "table_number": "A1",
  "current_guests": null,
  "qr_code_url": null,
  "is_active": true,
  "position": {
    "x": "80.00",
    "y": "80.00",
    "width": "120.00",
    "height": "80.00",
    "rotation": "0.00",
    "shape": "RECTANGLE"
  }
}
```

The backend creates both records:

```text
restaurant_tables
floor_plan_tables
```

Save the returned `table_id`.

3. Check created tables:

```text
GET /api/v1/restaurant-tables
```

4. Check seeded products:

```text
GET /api/v1/products
```

Save one `id`, for example `1`.

5. Create an order:

```text
POST /api/v1/orders/with-items
```

Example body:

```json
{
  "table_id": 1,
  "source": "WAITER",
  "items": [
    {
      "product_id": 1,
      "quantity": 2,
      "notes": "bez cebuli",
      "product_modifier_ids": []
    }
  ]
}
```

Save the returned order `id`.

6. Check created kitchen tasks:

```text
GET /api/v1/kitchen-tasks
```

Save the task `id`.

7. Start the kitchen task:

```text
POST /api/v1/kitchen-tasks/{task_id}/start
```

8. Complete the kitchen task:

```text
POST /api/v1/kitchen-tasks/{task_id}/complete
```

9. Register payment for the order:

```text
POST /api/v1/orders/{order_id}/payments
```

Use the order `total_amount` as `amount`.

Example body:

```json
{
  "method": "CARD",
  "amount": 42.5,
  "close_order": true
}
```

10. Generate mock receipt PDF:

```text
POST /api/v1/orders/{order_id}/receipt/pdf
```

This returns a PDF that simulates thermal printer output.

11. Optional invoice flow:

```text
POST /api/v1/orders/{order_id}/invoice
POST /api/v1/invoices/{invoice_id}/pdf
POST /api/v1/invoices/{invoice_id}/send-ksef-mock
```

The KSeF endpoint is a mock and only simulates sending the invoice.

## Seed Data Strategy

The development seed keeps reference data ready, but leaves operational data empty for realistic testing.

Seeded data:

```text
users
restaurant_config
system_modules
kitchen_sections
product_categories
products
modifiers
product_modifiers
product_kitchen_steps
ingredients
warehouses
stock_items
product_ingredients
discounts
floor_plans
```

Intentionally empty data:

```text
restaurant_tables
floor_plan_tables
orders
order_items
kitchen_tasks
payments
reservations
reservation_tables
invoices
order_action_logs
order_transfer_logs
stock_movements
```

Restaurant tables are created by the floor plan editor through:

```text
POST /api/v1/floor-plans/{floor_plan_id}/tables/create-restaurant-table
```

## Kitchen Preparation Steps

Products are not assigned to only one kitchen section. A menu product can have multiple kitchen preparation steps.

Example:

```text
Salatka cezar
- Kuchnia zimna: prepare salad base
- Stanowisko miesne: prepare chicken or shrimp
```

When an order item is created, the backend creates one kitchen task for each active product kitchen step.

Kitchen steps for one product are treated as parallel work. The product estimated time is the longest active step, not the sum of all steps. The whole order estimated time is the longest product in the order.

Example:

```text
Salatka cezar
- Kuchnia zimna: 7 min
- Stanowisko miesne: 10 min
Product estimated time: 10 min

Order:
- Salatka cezar: 10 min
- Steak: 20 min
Order estimated time: 20 min
```

Preparation steps are managed through:

```text
GET /api/v1/product-kitchen-steps
POST /api/v1/product-kitchen-steps
PATCH /api/v1/product-kitchen-steps/{item_id}
DELETE /api/v1/product-kitchen-steps/{item_id}
```

`product_ingredients` describe stock/recipe usage. `product_kitchen_steps` describe who prepares which part of the dish.

## Tests

Run the backend tests:

```bash
cd backend
./.venv/bin/pytest
```
