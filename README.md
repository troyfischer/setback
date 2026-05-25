# Setback

Setback is a multiplayer card game app for running a shared family-style game table online. The repository contains a FastAPI backend for auth and game state, plus a React/Expo web client for lobby and in-game play.

## Notes
This is a personal project to appreciate the nuance of deploying a web app from scratch.

This project covers a few concepts I wanted more hands on experience with:
1. Client SSE subscriptions backed by server side redis pub/sub
2. Database management and ORM backed persistence in python
3. OIDC with common identity providers like Google
4. JWT issuance and refresh-token management
5. Infra management with pulumi
