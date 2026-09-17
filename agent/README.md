# Windows agent (Exchange Online + optional AD)

A small PowerShell 7 HTTP listener on a domain-joined Windows host. The FastAPI backend
calls it for the cmdlets Graph cannot do. Each endpoint wraps one function from the
original scripts:

| Endpoint | Source script |
|---|---|
| POST /mailbox/onboard | NewUser-Exchange.ps1 (wait, archive, retention, 17a-4 FullAccess) |
| POST /mailbox/offboard | convert to shared, forwarding, auto-reply |
| POST /calendar/permission | Grant-CalendarPermissions / Reviewer |

Auth: app-only EXO cert (`Connect-ExchangeOnline -CertificateThumbprint -AppId -Organization`),
plus a shared key header from the backend (`X-Agent-Key`). See docs/REQUIREMENTS.md § Exchange.
Implementation: to be written — Pode (https://badgerati.github.io/Pode) is the simplest
PowerShell web framework for this.
