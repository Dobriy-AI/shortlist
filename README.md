# Shortlist

A web application to help people find and shortlist potential funding opportunities for their projects and organisations.

Public landing page: [fundings.wiki](https://fundings.wiki/).

[![CI and deployment](https://github.com/Dobriy-AI/shortlist/actions/workflows/ci-cd.yml/badge.svg)](https://github.com/Dobriy-AI/shortlist/actions/workflows/ci-cd.yml)

## Current release

The first release is a responsive landing page with a searchable directory of six official European and Austrian funding sources, an introduction to the planned application, FAQs and a contact link to the Dobriy AI team. Source links work without JavaScript. Personal shortlists, accounts, matching and application tracking are planned features.

The page uses the company's pinned `@dobriy/interface-style` v0.1.4 landing profile and local Poppins fonts. The private shared stylesheet remains a dependency, with its built assets copied into the deployment output. See [NOTICE.md](NOTICE.md).

## Local development

Node 22 or newer and GitLab SSH access to `git.dobriy.ai/semantic/interface-style` are required.

```sh
npm ci
npm run check
npm run dev
```

Open `http://127.0.0.1:5419`. Re-run `npm run build` after editing source files.

On `dobriy-ai-k8s`, run `workspace-run --check` before installing, then prefix npm commands with `workspace-run`. Keep dependencies and output on the workspace volume.

```sh
# Uses a temporary local server on port 5420.
npm run test:browser
```

Browser checks require Playwright Chromium. Install it once with `npx playwright install chromium` if it is not already available. The suite checks five screen widths, accessibility, filtering, empty states, mobile navigation, font loading and the no-JavaScript fallback. Screenshots and results are written to ignored `artifacts/`.

## Files

- `public/` contains the landing-page HTML, product layout CSS, browser behaviour and static assets.
- `data/sources.json` contains source descriptions, official URLs, categories and review dates. These are portals, not a database of live calls.
- `scripts/build.mjs` renders the source directory and copies shared styles and fonts into `dist/`.
- `deploy/` contains the server configuration and [deployment instructions](deploy/README.md).

The site has no backend, signup form, tracking scripts or cookies. The contact action opens the user's email application. Funding applications happen on providers' websites.

## CI/CD

GitHub Actions checks pull requests and pushes to `main`. Repository branches get a locked dependency install, production build, responsive browser tests and accessibility checks. All pull requests also run source checks and deployment tests. Fork pull requests cannot access the private stylesheet credential, so their full build and browser checks require a maintainer-owned branch. Every merge receives the full checks before deployment.

Passing `main` commits deploy automatically to [fundings.wiki](https://fundings.wiki/), using the exact tested artifact. The production environment only accepts `main`. Deployment verifies the checksum and commit, switches releases atomically and restores the previous version if the server's live verification fails or is interrupted. GitHub then checks the public HTTPS site from its runner.

Screenshots are retained in Actions for seven days, deployable artifacts for fourteen. The workflow can also be run manually from the Actions tab on `main`. See [deployment operations](deploy/README.md) for credentials, rollback and receiver maintenance.

## Vision

Bring funding opportunities into one place so users can discover relevant options, understand eligibility, and decide where to apply. Potential sources include grants, funding calls, accelerators, and other funding programs.

## Proposed initial scope

- **Discover opportunities:** Browse and search by keyword, sector, geography, funding type, and application deadline.
- **Assess fit:** Review eligibility, available funding, deadlines, and application requirements, with links to the original source.
- **Build a shortlist:** Save promising opportunities and add notes about their relevance.
- **Track progress:** Organize saved opportunities by status, such as considering, preparing, applied, and closed.

## Opportunity information

Each opportunity should include its title, funding organization, description, eligibility criteria, geographic scope, funding amount and currency when available, deadline, and official application link. Source and last-checked dates should help users judge how current the information is.

## Next steps

1. Define the first target users and funding categories.
2. Choose initial data sources and how opportunities will be added and kept current.
3. Design the discovery and shortlist workflows.
4. Select the technology stack and build the first working version.
