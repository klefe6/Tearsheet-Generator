# Windows VPS Deployment Layout

Provider-neutral deployment package for the Hughes & Company tearsheet system
on a conventional Windows Server VPS.

## What this is

- A **visual filesystem preview** you can browse in Windows Explorer
- **Scripts** to create and validate the `C:\HC\` layout on a real VPS
- **Manifests** describing apps, data, services, ports, and hostnames
- **Configuration templates** (no secret values)

## What this is NOT

- Not a production deployment
- Not a copy of production data
- Not NSSM/IIS/Cloudflare/DNS configuration

## Quick start (browse the layout)

Open in Windows Explorer:

```text
deployment\windows-vps\filesystem-preview\HC\
```

Read the server map:

```text
deployment\windows-vps\SERVER_MAP.md
```

## Folder guide

| Path | Purpose |
|------|---------|
| `filesystem-preview\HC\` | Visual mirror of future `C:\HC\` (README placeholders only) |
| `scripts\` | `Initialize-HCServerLayout.ps1`, `Test-HCServerLayout.ps1` |
| `config-templates\` | `hc-vps.env.example` (copy on VPS; never commit populated) |
| `manifests\` | JSON maps for apps, data, services, network |
| `SERVER_MAP.md` | Human-readable server layout |
| `DEPLOYMENT_CHECKLIST.md` | Step-by-step deployment checklist |

## Future VPS commands

```powershell
# Create empty layout (on VPS only — not on laptop)
.\deployment\windows-vps\scripts\Initialize-HCServerLayout.ps1 -Root "C:\HC"

# Validate layout
.\deployment\windows-vps\scripts\Test-HCServerLayout.ps1 -Root "C:\HC"
```

## Related documentation

Phase P3 portability docs (repo root):

- `docs\migration\VPS_FILESYSTEM_LAYOUT.md`
- `docs\migration\VPS_ENVIRONMENT_VARIABLES.md`
- `docs\migration\VPS_DEPLOYMENT_MANIFEST.json`
- `docs\migration\VPS_PATH_PORTABILITY_FINAL_REPORT.md`
