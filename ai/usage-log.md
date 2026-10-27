13-09-2026 22:19 | Usage Scenario: Used ChatGPT to generate boiler react vite typescript template
Prompt:
In the root, create a folder called UI and install react vite in typescript. Please generate the template

Key responses:
Created [UI](/Users/weihungloh/FoC-Template/UI) with the standard Vite React TypeScript template and installed dependencies.

Build and lint both pass. All changes are uncommitted.

Start development:
cd UI
npm run dev

----
13-09-2026 22:47 | Usage Scenario: Generate boilet template for fastAPI for user service
Prompt:
Now in user-service folder, i want to use fastAPI python. Set up a boiler template for me please

Key responses:
Set up [user-service](/Users/weihungloh/FoC-Template/user-service) with FastAPI, CORS, PostgreSQL connection helper, and Dockerfile.
- Connection string saved in ignored .env.
- Database verified using SELECT 1.
- Frontend proxy and cross-origin connection verified.
- No health endpoint, schema, tables, or code comments added.
- Two tests pass. Docker build wasn’t tested because its daemon is stopped.
Start it:
cd user-service
source .venv/bin/activate
uvicorn app.main:app --reload --port 5005

----
14-09-2026 20:48 | Usage scenario: Rename reusable endpoints in frontend
Prompt: The endpointconfig and useCampusErrandsAPI If possible can make it e.g. api.user.authentication. ... Create an empty object for supplier, order, credit too so it calls api.<service>. .

Key responses:
Updated the API structure:

```ts
api.user.authentication.signIn(...)
api.user.authentication.signUp(...)
api.user.authentication.verify(...)
api.user.authentication.signOut(...)

api.supplier
api.order
api.credit
```

The empty service objects are present in both [endpointConfig.ts](/Users/weihungloh/FoC-Template/ui/src/api/endpointConfig.ts) and [useCampusErrandsAPI.ts](/Users/weihungloh/FoC-Template/ui/src/api/useCampusErrandsAPI.ts).

All callers now use `api.user.authentication`, including `ProtectedRoutes`.

----
16-09-2026 21:30 | Usage scenario: Make user service environment consistent with supplier service

Prompt:
look at the commit by loyaltypollution. For supplier service they used UV and python 3.14? user-service must match the same version please

Key responses:
Aligned user-service with supplier-service:
- Migrated dependencies from requirements.txt to [pyproject.toml](/Users/weihungloh/FoC-Template/user-service/pyproject.toml) and generated [uv.lock](/Users/weihungloh/FoC-Template/user-service/uv.lock).
- Set Python requirement to >=3.14.
- Updated [Dockerfile](/Users/weihungloh/FoC-Template/user-service/Dockerfile) to python:3.14-slim and uv 0.12.13.
- Added matching devcontainer configuration.
- Updated [README.md](/Users/weihungloh/FoC-Template/user-service/README.md) with uv commands.
- Removed requirements.txt.
Verification:
- uv lock --check passed with 28 resolved packages.
- Dependencies installed successfully under Python 3.14.
- Uvicorn started and /openapi.json returned HTTP 200.
- Configuration and diff checks passed.
- Docker image build was not run because the local Docker daemon is stopped.
All changes remain uncommitted.