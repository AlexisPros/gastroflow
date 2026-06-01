# GastroFlow Frontend

React + TypeScript + Vite frontend for the GastroFlow POS system.

## Run Locally

```bash
npm install
npm run dev
```

Default URLs:

```text
Frontend: http://127.0.0.1:5173
Backend API: http://127.0.0.1:8000/api/v1
Backend WS: ws://127.0.0.1:8000/api/v1
```

If the backend runs somewhere else, copy `.env.example` to `.env` and change:

```text
VITE_API_BASE_URL
VITE_WS_BASE_URL
```

## Structure

```text
src/api       HTTP clients
src/auth      auth context and local storage
src/layouts   app shell
src/pages     route pages
src/routes    router and guards
src/shared    config and shared types
src/ws        WebSocket client
```
