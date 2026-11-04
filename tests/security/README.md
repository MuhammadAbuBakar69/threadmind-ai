# Security tests

The acceptance criterion is concrete: **zero cross-tenant data access**. Planned checks:

- A user in org A requesting an org B resource receives `404`, never data.
- A forged `organization_id` in a request body is ignored in favour of the resolved membership.
- RLS blocks a raw query that omits a `WHERE organization_id` clause.
- Uploaded files are validated by type and size before storage.
- Agent tool calls cannot escape the resolved tenant scope.
- Prompt injection inside an uploaded document cannot trigger a tool call.
