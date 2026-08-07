# Generated OpenAPI specs

**Do not edit these by hand.** They are copies; the source of truth lives beside
the code, where a contract test can hold it to the real responses.

| File | Source | Kept honest by |
|---|---|---|
| `public.yaml` | `pythia:api/openapi/public.yaml` | `pythia:test/contract` |

## Refreshing

```bash
cp ../../../../pythia/pythia/api/openapi/public.yaml public.yaml
```

Adjust the path for your checkout. The spec is committed here rather than
fetched at build time because `pythia` is private and Mintlify cannot read it.

## Why hand-authored, not generated

Several pythia handlers build their response as `map[string]any` — `marketPayload`
merges a marshalled `MarketMeta` with engine trading config, and the asset
handlers build theirs inline. No annotation tool can infer a schema from a map,
so the spec is written and then **tested against real responses** rather than
derived from types that do not exist.

Run the contract test against a live instance:

```bash
CONTRACT_BASE_URL=http://localhost:8078 go test -tags=contract ./test/contract/...
```

It fails on two things: a documented field whose type has changed, and a public
route added to the server but not to the spec.
