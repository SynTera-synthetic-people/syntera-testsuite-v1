# Integrating Test Studio with synthetic-people.ai

This document describes how to link from [synthetic-people.ai](https://synthetic-people.ai/) to the SynTera Test Suite (Dashboard & Reports and Test Results).

## Explore Test Studio button

On your main website (synthetic-people.ai), add a button or link labeled **"Explore Test Studio"** that sends users to the Test Suite app.

### Recommended URLs

Use one of these as the `href` for the button (replace the host with your deployed Test Suite base URL):

| Use case | URL | Notes |
|----------|-----|--------|
| Same domain (e.g. app on subdomain) | `https://app.synthetic-people.ai/studio` | Redirects to Dashboard & Reports |
| Path on same site | `https://synthetic-people.ai/studio` | If the Test Suite is served under the same host (e.g. reverse proxy) |
| Hash-based | `https://<your-test-suite-host>/#reports` | Opens directly to Dashboard & Reports |

### Redirect routes (Test Suite app)

The Test Suite backend exposes these routes so the main site can use short, memorable URLs:

- **`/studio`** – redirects to `/#reports` (Dashboard & Reports)
- **`/test-studio`** – same as `/studio`
- **`/explore`** – same as `/studio`

Example for the main site:

```html
<a href="https://app.synthetic-people.ai/studio" class="btn-primary">Explore Test Studio</a>
```

Or, if the Test Suite is served from the same origin (e.g. `https://synthetic-people.ai` with path `/studio` handled by the same app or reverse proxy):

```html
<a href="/studio" class="btn-primary">Explore Test Studio</a>
```

After redirect, users land on **Dashboard & Reports** and can open **Test Results** via “View Details” on any report. No login is required to view the dashboard and reports; login is required for running new validations and other privileged actions.

## Data storage

Reports, dashboard data, and test studio results are stored in the backend database (PostgreSQL or SQLite). See `.env.example` and the main README for configuring `DATABASE_URL` (e.g. PostgreSQL for production).

## New user registration

The Test Suite supports self-service registration via the **New User** button next to Login. New users are stored in the user management table and can log in immediately after registration.
