# `C:\H&C` vs `C:\HC` reference report (PR #65 reconciliation)

**Canonical current contract:** `C:\HC\` only.

## Classification rules

- **Historical (A):** Explains superseded `C:\H&C` or `E:\H&C` drafts, company name "H&C", or user profile `H&CDanHughes`.
- **Current wrong (B):** Any live deploy path, manifest default, test assertion, or template still pointing at `C:\H&C\`.
- **Unknown (C):** None expected after reconciliation.

Regenerate counts with:

```powershell
rg 'C:\\H&C|C:\\\\H&C' --glob '!**/.worktrees/**' --glob '!**/node_modules/**'
```
