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

1. Check seeded tables:

```text
GET /api/v1/restaurant-tables
```

Save one `id`, for example `1`.

2. Check seeded products:

```text
GET /api/v1/products
```

Save one `id`, for example `1`.

3. Create an order:

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

4. Check created kitchen tasks:

```text
GET /api/v1/kitchen-tasks
```

Save the task `id`.

5. Start the kitchen task:

```text
POST /api/v1/kitchen-tasks/{task_id}/start
```

6. Complete the kitchen task:

```text
POST /api/v1/kitchen-tasks/{task_id}/complete
```

7. Register payment for the order:

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

8. Generate mock receipt PDF:

```text
POST /api/v1/orders/{order_id}/receipt/pdf
```

This returns a PDF that simulates thermal printer output.

9. Optional invoice flow:

```text
POST /api/v1/orders/{order_id}/invoice
POST /api/v1/invoices/{invoice_id}/pdf
POST /api/v1/invoices/{invoice_id}/send-ksef-mock
```

The KSeF endpoint is a mock and only simulates sending the invoice.

## Tests

Run the backend tests:

```bash
cd backend
./.venv/bin/pytest
```
