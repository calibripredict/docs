# Calibri Knowledge Base

Customer-facing documentation for Calibri, published with
[Mintlify](https://mintlify.com) at **https://docs.calibri.io**.

One site, two tabs:

| Tab | Content | Path |
|---|---|---|
| **Documentation** | The knowledge base — concepts, self-custody, resolution, legal | repo root |
| **API Reference** | Base URLs, auth, errors, WebSocket, and (in progress) generated endpoint pages | `api-reference/` |

`calibripredict/api` is the outgoing **Slate** site. It stays live until the API
Reference tab carries the full endpoint surface — see `OPENAPI_MIGRATION.md` in
that repo.

<!-- If the account moves to Enterprise, `api-reference/` lifts out into its own
repo and is re-attached with a `sourceRef` entry in the navigation below.
Multi-repository deployments are Enterprise-only, which is why both tabs live
here for now. -->

## Layout

| Path | Purpose |
|---|---|
| `docs.json` | Mintlify config — theme, brand colours, navigation. A page not listed here is unreachable |
| `*.mdx` | Content, one page per file |
| `logo/`, `favicon.svg` | Brand assets |

The homepage is `introduction.mdx` — the first page of the first group.

## Editing

Every page opens with frontmatter, and the `title` there is the page heading —
do **not** add an `# H1` in the body:

```mdx
---
title: "Fees"
description: "One sentence that appears under the title and in search results."
---
```

Internal links are root-absolute and **omit the extension**:

```mdx
See [Fees](/concepts/fees).
```

### Components

Callouts:

```mdx
<Note>
  A tip or aside.
</Note>

<Warning>
  Something the reader must not get wrong.
</Warning>
```

Sequences:

```mdx
<Steps>
  <Step title="Create the passkey">
    Body text.
  </Step>
</Steps>
```

Link grids, used for the "Related" / "Next steps" block at the foot of a page:

```mdx
<CardGroup cols={2}>
  <Card title="Fees" href="/concepts/fees">
    What trading costs.
  </Card>
</CardGroup>
```

MDX parses `{` and `}` as expressions and `<` as JSX. Keep braces and angle
brackets inside code fences or inline code, or the build fails.

## Preview locally

```bash
npm i -g mint
mint dev
```

`mint broken-links` checks internal links before you push.

## Publishing

Published at **https://docs.calibri.io**. Mintlify's GitHub App watches `master`
and deploys on push — there is no build step in this repo and no workflow file,
so merging is the whole publish process.

The repo is **private**; the published site is **public**. Those are independent:
making the repo private does not gate the site, and nothing here should be
written on the assumption that it does.

Branch is `master`, not `main` — check that in Mintlify's Git Settings if a push
does not deploy.

## Adding a page

1. Create the `.mdx` file with `title` and `description` frontmatter.
2. Add its path (no extension) to the right group in `docs.json`.
3. Link it from a related page's `<CardGroup>` so it is reachable by reading, not just by nav.
