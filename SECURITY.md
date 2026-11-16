# Security Policy

## Reporting a vulnerability

Please report security issues privately, not in a public issue.

Use GitHub's private reporting form:
[Report a vulnerability](https://github.com/asg5704/rocket-league-predictor/security/advisories/new).

Include what you found, how to reproduce it, and the impact you expect. This is a
side project maintained by one person, so I can't promise a fixed timeline, but I
aim to acknowledge reports within a few days and to fix confirmed issues promptly.

## Supported versions

Only the latest commit on `main` and the live deployment at
<https://rlcs-roster-optimizer.alexandergarcia.xyz/> are supported.

## Scope

In scope: the FastAPI backend (`src/api`), the React frontend (`frontend/`), the
Docker image, and the CI workflows.

Out of scope: the Ballchasing service and its data, Railway and Cloudflare
infrastructure, and denial-of-service testing against the live site.

## Notes for researchers

The app serves public, read-only professional match data and has no user accounts.
The Ballchasing API key is only used by the offline data-collection scripts and is
never committed or shipped in the Docker image.
