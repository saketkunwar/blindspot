# BlindSpot console

Three-pane console: scenarios/assets (left), map (centre), details (right).

```sh
cd web
npm install
npm run dev     # http://localhost:3000
```

The console reads from the API (default `http://localhost:8000`):

```sh
cd ..
uvicorn api.server:app --port 8000
```

Point at another API with `NEXT_PUBLIC_API_URL`. Map tiles stream from the
network at view time; all scenario names, dates, and geometries render from
API responses, never from constants in this bundle.
