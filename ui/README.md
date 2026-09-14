# Campus Errands UI

React, Vite, and TypeScript scaffold based on the
[Job Tracker frontend](https://github.com/WeiHungLoh/job-tracker/tree/main/client).

```text
ui/
├── public/
├── src/
│   ├── api/
│   │   ├── api.ts
│   │   ├── endpointConfig.ts
│   │   ├── models.ts
│   │   └── useCampusErrandsAPI.ts
│   ├── components/
│   │   ├── authLayout/
│   │   ├── protectedRoutes/
│   │   └── toast/
│   ├── helper/
│   ├── hooks/
│   ├── pages/
│   │   ├── authentication/
│   │   │   ├── signIn/
│   │   │   ├── signUp/
│   │   │   └── models.ts
│   │   └── home/
│   ├── App.tsx
│   ├── index.css
│   ├── main.tsx
│   ├── routes.ts
│   └── vite-env.d.ts
├── .env.example
├── .gitignore
└── vite.config.ts
```

Empty helper and hook directories contain only `.gitkeep` so Git preserves the structure.

## Development

Run from `ui/`:

```sh
npm ci
cp .env.example .env.local
npm run dev
```

`VITE_API_URL` defaults to `/api`. Vite forwards `/api/*` to
`VITE_API_PROXY_TARGET` (default `http://127.0.0.1:5005`) and removes `/api`.
The proxy removes an explicit backend cookie Domain so the browser can use the
development host. Use backend cookies with `Path=/`. Set the proxy target to
your backend or gateway; no backend is implemented here.

The proxy runs only during development. Production hosting must forward
`/api/*` to the backend and serve `index.html` for frontend routes, or set
`VITE_API_URL` to the API's absolute base URL at build time.
`VITE_*` variables are public browser configuration; never put secrets in them.

## Authentication and cross-origin cookies

Authentication uses only an access token in a backend-issued HttpOnly cookie.
All API requests use `credentials: 'include'`, including sign-in and sign-out.
There is no refresh flow, browser token storage, or Authorization header.

The endpoint format and initial paths follow Job Tracker:

| Hook method | Method | Path |
| --- | --- | --- |
| `user.authentication.signIn({ email, password })` | POST | `/authentication/sessions` |
| `user.authentication.signUp({ username, email, password })` | POST | `/authentication/users` |
| `user.authentication.verify()` | GET | `/authentication/sessions/current` |
| `user.authentication.signOut()` | DELETE | `/authentication/sessions/current` |

Sign-in returns a message and sets the cookie through `Set-Cookie`.
Sign-out must expire that same cookie with matching Path and Domain.
The frontend cannot read or delete an HttpOnly cookie. The user-service handlers
match these contracts; sign-in rejects credentials until its SQL user lookup is implemented.

For a frontend and API on different origins, the backend must:

- Return `Access-Control-Allow-Origin` with the exact trusted frontend origin
  (not `*`) and `Access-Control-Allow-Credentials: true`, including error responses.
- Handle OPTIONS preflight without requiring authentication; allow the methods
  used by the API and the `Content-Type` header.
- Set the access-token cookie as HttpOnly, with an appropriate expiry and
  `Path=/`. For cross-site deployment, use `SameSite=None; Secure` over HTTPS.
- Expire the cookie on sign-out using the same cookie name, Path, and Domain.
- Enforce authentication and CSRF protection server-side, including validation of
  trusted origins for state-changing requests.

Different ports are different origins but can still be same-site. For local
HTTP development through the proxy, the backend can use a development-only
`SameSite=Lax` cookie without Secure. Keep production cookies Secure.
Cross-site cookies may still be blocked by browser third-party-cookie policies;
a same-site API domain or same-origin gateway avoids that dependency.

See [MDN CORS](https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/CORS)
and [Set-Cookie](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Set-Cookie).

## Adding features

Add endpoint groups to `src/api/endpointConfig.ts` with `url`, `verb`, and optional
`fieldMap` entries (`path`, `query`, or `formData`). Unmapped fields become JSON
body fields, or query fields for GET. Add typed feature methods to
`useCampusErrandsAPI`; generic `request` and `authenticatedRequest` are also available.
The transport sends one request and returns the parsed response. Retry, timeout,
and request-cancellation behavior can be added later if the application needs it.

`App.tsx` owns `RouterProvider`. `/` renders Sign In and `/sign-up` renders Sign Up
outside the authentication guard. `/home` renders Home inside `ProtectedRoutes`.
Home calls `user.authentication.signOut()` directly; sign-out is an action rather than a route.
`ToastProvider` wraps the router and exposes error, success, and neutral notifications.
Toasts use the Campus Errands light theme, dismiss automatically where appropriate,
and do not display a countdown line.
`ProtectedRoutes` verifies each protected navigation and waits for completion,
redirects HTTP 401 to `/` with `location.state.returnTo`, and shows a retry action
for service errors. Expired tokens require a new sign-in. Future sign-in pages
must validate `returnTo` as a local route before navigating.

Add pages under `src/pages`, reusable components under `src/components`, and
route paths in `src/routes.ts`.

## Verification

```sh
npm run lint
npm run build
```
