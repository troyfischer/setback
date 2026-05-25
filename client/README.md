# Setback Client

Expo + TypeScript client for the FastAPI setback server in [`../python`](../python).

## Run it

```bash
cd python
make dev-up

cd ../client
npm run web
```

## Notes

- The app defaults to `http://localhost` on web.
- For Android emulators, use `http://10.0.2.2` as the API base URL.
- Use **Sign In With Google** on web to open the server's `/api/auth/google/login` OpenID Connect flow. The client reads the callback token from the popup response and stores it as the bearer token for API requests.
- The server must allow the Expo web origin in `cors_origins`, and its Google OAuth redirect URI must remain `${BASE_URL}/api/auth/google/callback`.
- **Refresh Google Token** calls `/api/auth/refresh` with cookies included, so the server needs to set a usable `refresh_token` cookie for the client origin. For local HTTP testing, the cookie cannot be `secure=True`.
- `/api/auth/dev-token` is still exposed in the UI as a local developer fallback only; disable that endpoint in production server deployments.
- Live updates use the server's short-lived SSE subscribe token flow.
