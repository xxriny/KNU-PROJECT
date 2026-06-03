# GCP Web Deployment

This deployment serves NAVIGATOR as a web app from the `main` branch.
The React frontend and FastAPI backend run in one Cloud Run service:
`navigator-webapp`.

Existing services such as `haesolok` and `navigator-server` are not stopped or
modified by this deployment.

## Target

- Project: `kun-kgp-xxrin01299`
- Region: `asia-northeast3`
- Service: `navigator-webapp`
- URL: `https://navigator-webapp-dnusrqiz5q-du.a.run.app`
- Cloud SQL: `kun-kgp-xxrin01299:asia-northeast3:navigator-db`

## Runtime

Cloud Run receives:

- `DATABASE_URL`
- `GEMINI_API_KEY`
- `NAVIGATOR_GITHUB_CLIENT_ID`
- `GITHUB_OAUTH_CLIENT_ID`
- `NAVIGATOR_JWT_SECRET` from Secret Manager

The backend also supports `NAVIGATOR_SHARED_DATABASE_URL`,
`NAVIGATOR_LOCAL_DATABASE_URL`, or Cloud SQL socket parts
(`INSTANCE_UNIX_SOCKET`, `NAVIGATOR_DB_USER`, `NAVIGATOR_DB_NAME`,
`NAVIGATOR_DB_PASSWORD`).

## Verify

```powershell
Invoke-WebRequest https://navigator-webapp-dnusrqiz5q-du.a.run.app/health
Invoke-WebRequest https://navigator-webapp-dnusrqiz5q-du.a.run.app/auth/status
```
