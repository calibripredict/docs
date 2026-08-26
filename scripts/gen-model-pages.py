#!/usr/bin/env python3
"""Generate the Models section of the API reference from the joined spec.

    ./scripts/gen-model-pages.py api-reference/openapi/calibri.yaml

WHY THIS EXISTS. The reference documented every endpoint and none of the shapes
those endpoints return. A caller reading "returns an OrderEntity" had nowhere to
go and had to open the raw YAML. `components.schemas` already describes every
one of them, generated in the service repo from the same entities the API
actually serialises — so the models section is derivable, and anything derivable
should not be typed by hand and left to rot.

WHAT IT WRITES. One MDX page per schema under api-reference/models/, each a
`openapi-schema` frontmatter reference that Mintlify renders from the spec, plus
the Models navigation group in docs.json. Pages for schemas that have since
disappeared upstream are DELETED, which is the half a generator usually forgets:
a stale model page outlives the field it documents and nothing points at it.

Grouping is by the service prefix of the operations that reference the schema —
the same split the base-URL table in the API overview shows a caller. A schema
nothing references lands in Shared rather than being dropped, because an
unreferenced schema is more likely a spec bug worth seeing than dead weight.

Run through scripts/join-specs.sh, never on its own: it needs the JOINED spec
(the one Mintlify renders), and the join is what produces it.
"""

import json
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS_DIR = os.path.join(ROOT, "api-reference", "models")
DOCS_JSON = os.path.join(ROOT, "docs.json")
SPEC_REF = "/api-reference/openapi/calibri.yaml"

# Service prefix -> section title. Order is precedence: a schema reachable from
# more than one service is filed under the first that reaches it.
SECTIONS = [
    ("/api/v2/pythia", "Market data & trading"),
    ("/api/v2/atlas", "Account & wallet"),
    ("/api/v2/persona", "Identity"),
]
UNREFERENCED = "Shared"


def bundle(spec_path):
    """Resolve the YAML spec to JSON with the same tool the join already uses."""
    out = os.path.join(tempfile.mkdtemp(), "spec.json")
    subprocess.run(
        ["npx", "--yes", "@redocly/cli@latest", "bundle", spec_path, "-o", out],
        check=True,
        stdout=subprocess.DEVNULL,
    )
    with open(out) as fh:
        return json.load(fh)


def refs_in(node, found):
    """Every schema name reachable from a node, following nested $refs later."""
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/components/schemas/"):
            found.add(ref.rsplit("/", 1)[1])
        for value in node.values():
            refs_in(value, found)
    elif isinstance(node, list):
        for value in node:
            refs_in(value, found)
    return found


def assign_sections(spec):
    """schema name -> section title, by which service's operations reach it."""
    schemas = spec.get("components", {}).get("schemas", {})
    direct = {}
    for path, item in spec.get("paths", {}).items():
        section = next((t for p, t in SECTIONS if path.startswith(p)), None)
        if section is None:
            continue
        for name in refs_in(item, set()):
            # First prefix in SECTIONS order wins, so the mapping is stable
            # whatever order the paths happen to be in.
            rank = [t for _, t in SECTIONS]
            if name not in direct or rank.index(section) < rank.index(direct[name]):
                direct[name] = section

    # A schema referenced only by another schema inherits its section.
    for _ in range(len(schemas)):
        changed = False
        for name, schema in schemas.items():
            if name not in direct:
                continue
            for child in refs_in(schema, set()):
                if child not in direct:
                    direct[child] = direct[name]
                    changed = True
        if not changed:
            break

    return {name: direct.get(name, UNREFERENCED) for name in schemas}


def slug(name):
    """CtfWalletEntity -> ctf-wallet-entity. Distinct names stay distinct."""
    s = re.sub(r"(.)([A-Z][a-z]+)", r"\1-\2", name)
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", s)
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def summary(schema):
    """First sentence of the schema description, for the page subtitle."""
    text = (schema.get("description") or "").strip()
    if not text:
        return None
    text = " ".join(text.split())
    cut = re.search(r"(?<=[.!?])\s", text)
    if cut:
        text = text[: cut.start()]
    return text if len(text) <= 200 else text[:197].rstrip() + "…"


def write_pages(schemas, sections):
    os.makedirs(MODELS_DIR, exist_ok=True)
    written, by_section = {}, {}

    for name in sorted(schemas):
        page = slug(name)
        if page in written:
            sys.exit(f"slug collision: {name} and {written[page]} both -> {page}")
        written[page] = name

        lines = ["---\n", f'title: "{name}"\n']
        note = summary(schemas[name])
        if note:
            lines.append(f'description: "{note}"\n')
        # Explicit spec path: unambiguous whatever else the project configures.
        lines.append(f'openapi-schema: "{SPEC_REF} {name}"\n')
        lines.append("---\n")

        target = os.path.join(MODELS_DIR, page + ".mdx")
        body = "".join(lines)
        if not os.path.exists(target) or open(target).read() != body:
            open(target, "w").write(body)

        by_section.setdefault(sections[name], []).append(f"api-reference/models/{page}")

    # A schema deleted upstream must not leave a page behind.
    keep = {p + ".mdx" for p in written} | {"overview.mdx"}
    for existing in sorted(os.listdir(MODELS_DIR)):
        if existing.endswith(".mdx") and existing not in keep:
            os.remove(os.path.join(MODELS_DIR, existing))
            print(f"  removed stale model page: {existing}")

    return by_section


def write_overview(by_section, schemas):
    """An index page, so the section has a front door to link at from prose."""
    lines = [
        "---\n",
        'title: "Models"\n',
        'description: "Every response and request shape the API serves, generated from the OpenAPI specification."\n',
        "---\n\n",
        "Each page below is generated from `components.schemas` in the API\n",
        "specification, so it is the shape the service actually serialises — not a\n",
        "hand-written copy of it. Fields, types and enums update when the API does.\n",
    ]

    order = [t for _, t in SECTIONS] + [UNREFERENCED]
    for title in order:
        pages = by_section.get(title)
        if not pages:
            continue
        lines.append(f"\n## {title}\n\n")
        rows = []
        for page in pages:
            name = page.rsplit("/", 1)[1]
            model = next(n for n in schemas if slug(n) == name)
            rows.append((model, page, summary(schemas[model]) or ""))

        # A description column that is blank for most rows is worse than no
        # column: today only a handful of schemas carry a description, so the
        # table earns its place only once most of them do.
        if sum(1 for _, _, note in rows if note) * 2 >= len(rows):
            lines.append("| Model | |\n|---|---|\n")
            lines += [f"| [`{m}`](/{p}) | {n} |\n" for m, p, n in rows]
        else:
            lines += [f"- [`{m}`](/{p})\n" for m, p, _ in rows]

    target = os.path.join(MODELS_DIR, "overview.mdx")
    body = "".join(lines)
    if not os.path.exists(target) or open(target).read() != body:
        open(target, "w").write(body)


def update_nav(by_section):
    with open(DOCS_JSON) as fh:
        docs = json.load(fh)

    order = [t for _, t in SECTIONS] + [UNREFERENCED]
    group = {
        "group": "Models",
        "pages": ["api-reference/models/overview"]
        + [
            {"group": title, "pages": by_section[title]}
            for title in order
            if by_section.get(title)
        ],
    }

    for tab in docs.get("navigation", {}).get("tabs", []):
        if tab.get("tab") != "API Reference":
            continue
        groups = tab.setdefault("groups", [])
        for i, existing in enumerate(groups):
            if existing.get("group") == "Models":
                groups[i] = group
                break
        else:
            groups.append(group)
        break
    else:
        sys.exit('docs.json has no "API Reference" tab to add the Models group to')

    with open(DOCS_JSON, "w") as fh:
        json.dump(docs, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    spec = bundle(sys.argv[1])
    schemas = spec.get("components", {}).get("schemas", {})
    if not schemas:
        sys.exit("the joined spec has no components.schemas — refusing to empty the Models section")

    sections = assign_sections(spec)
    by_section = write_pages(schemas, sections)
    write_overview(by_section, schemas)
    update_nav(by_section)

    counts = ", ".join(f"{t}: {len(p)}" for t, p in by_section.items())
    print(f"wrote {len(schemas)} model pages ({counts})")


if __name__ == "__main__":
    main()
