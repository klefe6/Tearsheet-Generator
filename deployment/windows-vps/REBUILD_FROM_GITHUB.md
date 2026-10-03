# Rebuild tearsheet apps on a fresh Windows VPS from GitHub

This is the **code** contract only. Data restore, secrets, DNS, Cloudflare, and public cutover are separate steps.

## Prerequisites

- Windows Server with RDP
- Outbound HTTPS for `git clone` and `pip install`
- **No** inbound exposure required for ports 8301–8304 during private bring-up

## 1. Install Git

Install Git for Windows and verify `git --version`.

## 2. Clone repository

```powershell
mkdir C:\src
cd C:\src
git clone https://github.com/klefebvre6/Tearsheet-Generator.git
cd Tearsheet-Generator
git checkout <release-branch>   # e.g. live-main after merge
```

## 3. Install Python 3.10

Install Python 3.10.x (64-bit) and ensure `py -3.10` works.

## 4. Create shared virtual environment

```powershell
py -3.10 -m venv C:\H&C\apps\shared\.venv310
C:\H&C\apps\shared\.venv310\Scripts\pip install -r C:\src\Tearsheet-Generator\requirements.txt
```

## 5. Create empty HC layout

From the clone:

```powershell
.\deployment\windows-vps\scripts\Initialize-HCServerLayout.ps1 -Root C:\H&C
.\deployment\windows-vps\scripts\Test-HCServerLayout.ps1 -Root C:\H&C
```

## 6. Deploy application source (dry run first)

```powershell
.\deployment\windows-vps\scripts\deploy-all.ps1 -TargetRoot C:\H&C
.\deployment\windows-vps\scripts\deploy-all.ps1 -TargetRoot C:\H&C -ConfirmDeploy
```

This copies **source only**. It does not copy financial JSON, CSV, XLSX, or secrets.

## 7. Restore production data (separate operation)

Copy authoritative files into `C:\H&C\data\...` per `deployment\windows-vps\manifests\persistent-data-map.json`.
Use encrypted transfer; verify SHA-256 after copy.

## 8. Install secrets (separate operation)

Create populated files under `C:\H&C\secrets\` and `C:\H&C\config\` from
`deployment\windows-vps\config-templates\hc-vps.env.example` — **never commit populated values**.

## 9. Create Windows services (separate operation)

Use NSSM (or equivalent) per `deployment\windows-vps\manifests\windows-services.json`.
Set `HC_APP_ENV=vps-production` and per-app env files.

## 10. Private health checks

From an RDP session on the VPS:

```powershell
Invoke-WebRequest http://127.0.0.1:8302/healthz   # TCP pilot
```

Compare JSON fields to laptop baseline documented in `docs\migration\OVH_TKP_TCP_AGM_CURRENT_STATE.md`.

## 11. Public cutover (out of scope here)

Cloudflare tunnel / DNS changes happen only after private validation.
Do not merge migration PRs or switch live hostnames in the same change set as code deploy.

## Inventory command

```powershell
.\deployment\windows-vps\scripts\show-deployment-inventory.ps1
```
