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

All seeded users use the same password:

```text
password: demo1234
```

Seeded users use different PINs so QR order confirmation can identify exactly which worker accepted the order:

```text
admin@gastroflow.dev    PIN: 1001
manager@gastroflow.dev  PIN: 1002
waiter@gastroflow.dev   PIN: 1234
kitchen@gastroflow.dev  PIN: 2001
bar@gastroflow.dev      PIN: 3001
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
  "pin": "1001"
}
```

Employee shifts are started manually, not automatically at login:

```text
POST /api/v1/shifts/start
GET /api/v1/shifts/current
POST /api/v1/shifts/current/close
GET /api/v1/shift-reports
```

When a shift is closed, the backend saves a shift report with sales, tips, discounts, payment methods, and sold item breakdown.
The backend rejects shift closing while the shift still has orders with `OPEN` or `PENDING_CONFIRMATION` status.

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

5. Start an employee shift before creating waiter orders:

```text
POST /api/v1/shifts/start
```

Example body:

```json
{
  "opening_note": "Morning shift"
}
```

6. Create an order:

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

7. Check created kitchen tasks:

```text
GET /api/v1/kitchen-tasks
```

Save the task `id`.

8. Start the kitchen task:

```text
POST /api/v1/kitchen-tasks/{task_id}/start
```

9. Complete the kitchen task:

```text
POST /api/v1/kitchen-tasks/{task_id}/complete
```

10. Register payment for the order:

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

11. Generate mock receipt PDF:

```text
POST /api/v1/orders/{order_id}/receipt/pdf
```

This returns a PDF that simulates thermal printer output.

12. Close the employee shift and generate a report:

```text
POST /api/v1/shifts/current/close
```

11. Optional invoice flow:

```text
POST /api/v1/orders/{order_id}/invoice
POST /api/v1/invoices/{invoice_id}/pdf
POST /api/v1/invoices/{invoice_id}/send-ksef-mock
```

The KSeF endpoint is a mock and only simulates sending the invoice.

## Seed Data Strategy

The development seed keeps reference data ready, but leaves operational data empty for realistic testing. Every seed run clears operational data before recreating/updating reference data.

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
employee_shifts
employee_shift_reports
stock_movements
```

Restaurant tables are created by the floor plan editor through:

```text
POST /api/v1/floor-plans/{floor_plan_id}/tables/create-restaurant-table
```

When a restaurant table is created, the backend generates permanent QR data:

```text
qr_token
qr_code_url
```

The token is stable and should not be regenerated during normal table updates. By default, QR URLs use:

```text
http://localhost:3000/qr/{qr_token}
```

For another frontend domain, set:

```text
PUBLIC_MENU_BASE_URL=https://menu.example.com/qr
```

The public QR flow starts with these endpoints and does not require JWT authorization:

```text
GET /api/v1/qr/{qr_token}/table
POST /api/v1/qr/{qr_token}/orders
```

The QR order endpoint creates an order with:

```text
source: QR
status: PENDING_CONFIRMATION
waiter_id: null
```

The backend accepts a new QR order only when the table is active, has status `FREE`, and has no active order with status `PENDING_CONFIRMATION` or `OPEN`.

QR order flow updates table status:

```text
QR order created   -> table.status = PENDING_ORDER
QR order confirmed -> table.status = OCCUPIED
QR order rejected  -> table.status = FREE
Order closed       -> table.status = FREE
```

When an order is closed, the backend releases the table only if there is no other active order for the same table. It also clears `current_guests`.

Kitchen tasks are not created yet. They should be created only after a waiter confirms the QR order.

Waiters, managers, and admins can list QR orders waiting for confirmation:

```text
GET /api/v1/qr/orders/pending
```

Any waiter can accept a pending QR order by entering a PIN:

```text
POST /api/v1/qr/orders/{order_id}/confirm
```

Body:

```json
{
  "pin": "1234"
}
```

After confirmation, the backend assigns the waiter, attaches the order to the waiter's open shift, changes the order status to `OPEN`, calculates estimated time, and creates kitchen tasks. If the waiter has no open shift, the backend returns `Start shift first.`
The confirmation step also records an `QR_ORDER_CONFIRMED` action log and avoids creating duplicate kitchen tasks if tasks already exist for the order items.

Any waiter can reject a pending QR order by entering a PIN:

```text
POST /api/v1/qr/orders/{order_id}/reject
```

Body:

```json
{
  "pin": "1234",
  "reason": "Guest left the table"
}
```

After rejection, the backend assigns the rejecting waiter, changes the order status to `REJECTED`, and records a `QR_ORDER_REJECTED` action log.

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
