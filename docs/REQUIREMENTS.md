# OHA Lifecycle App — What You Need to Provide

2026-09-16

## Overview

The app cannot run a single onboarding until every item below exists. Each section is one external system; the checklist at the end rolls it all up.

How to use it: work top to bottom, put every secret in Azure Key Vault (never in the repo), and keep the non-secret values (IDs, OU paths, SKU names) in a `config/` file that goes into the Azure DevOps repo. The app reads Key Vault at startup and the config file for everything else.

Owners you will likely need besides yourself: whoever holds Global Admin in Entra, the AWS account owner for the WorkSpaces accounts, and the Adobe admin console system admin.

## Active Directory (on-prem)

The app talks to a domain controller over LDAPS with a dedicated service account. If the app is hosted in Azure, it also needs a network path to that DC.

| Item | What to provide | Notes |
| --- | --- | --- |
| Service account | `svc-lifecycle` UPN + password → Key Vault | Not a personal account. Delegate rights, do not add to Domain Admins. |
| Delegated rights | Create/delete user objects, reset password, modify group membership on the target OUs | Delegate on the OU, not the domain root. |
| DC endpoints | 2+ DC hostnames, LDAPS on 636 | Verify the LDAPS cert chain is trusted by the app host. |
| Network path | VPN/ExpressRoute or Appgate route from the app's subnet to the DCs | If none exists, the AD steps run on the Windows agent instead (see Exchange section). |
| Base DN | e.g. `DC=oha,DC=com` | Goes in config, not Key Vault. |
| Target OUs | Full DN of each OU new users land in, per department/office | The wizard's `ou` field must match one of these. |
| Disabled-users OU | DN where offboarded accounts move | Used by the offboarding workflow. |
| Group list | Baseline groups every user gets, plus per-department groups | Distinguished names. |
| Naming rules | How `sAMAccountName` and UPN are built from first/last name, and the collision rule (`jsmith`, `jsmith2`) | Written down, so the app and the humans agree. |
| Password policy | Initial password pattern and whether "must change at next logon" is set |  |
| Attribute map | Which AD attributes the wizard fills (title, department, manager, office, phone) | These drive Entra Connect sync. |

## Microsoft Graph / Entra ID

Two app registrations: one for the backend to call Graph (application permissions), one for the front end so techs sign in with Entra SSO. Both need a Global Admin to grant consent.

**Backend app registration (`oha-lifecycle-api`)**

| Item | What to provide | Notes |
| --- | --- | --- |
| Tenant ID, Client ID | GUIDs → config |  |
| Client secret or certificate | → Key Vault | Certificate preferred; secrets expire and break the pipeline. |
| Graph application permissions | `User.ReadWrite.All`, `Group.ReadWrite.All`, `Directory.ReadWrite.All`, `Organization.Read.All` (license read), `User.EnableDisableAccount.All` | Admin consent granted. |
| License SKU IDs | SKU GUID for each license the wizard can assign (E3/E5, Teams Phone, Visio, etc.) | Pull once with `Get-MgSubscribedSku`; names change, GUIDs don't. |
| Usage location default | Country code (`US`) | Required before a license can be assigned. |
| Entra Connect sync interval | Current cycle time (default 30 min) | Sets the `graph.wait_for_sync` timeout. |
| Group policy for licensing | Are licenses assigned directly or via group? | If group-based, the app adds to the group instead of calling `assignLicense`. |

**Front-end app registration (`oha-lifecycle-web`)**

| Item | What to provide | Notes |
| --- | --- | --- |
| Client ID | GUID → front-end config | Public client, no secret. |
| Redirect URIs | Dev (`http://localhost:3000`) and prod URL |  |
| App roles | `Lifecycle.Operator` (run onboard/offboard), `Lifecycle.Admin` (retry, config), `Lifecycle.Viewer` (dashboard only) | The API checks these claims. |
| Role assignment | Which Entra groups map to which app role | e.g. IT Helpdesk → Operator. |

## Exchange Online (Windows agent)

Graph covers mailbox creation (it follows the license) but not shared-mailbox conversion, mailbox permissions, or retention. Those run as PowerShell on a small Windows worker the API calls over HTTPS. The same worker can run the AD steps if Azure has no route to your DCs.

| Item | What to provide | Notes |
| --- | --- | --- |
| Windows host | A domain-joined VM (on-prem or Azure) with PowerShell 7 and the `ExchangeOnlineManagement` module | Can be the box that already runs your WPF console. |
| EXO app-only auth | App registration with `Exchange.ManageAsApp` permission, a certificate installed on the worker, and the app assigned the **Exchange Administrator** role | This is the only non-MFA way to run EXO cmdlets unattended. |
| Agent API secret | Shared key or client certificate the FastAPI backend presents to the agent → Key Vault | Agent should reject anything else. |
| Network rule | Backend subnet → agent host on 443 |  |
| Mailbox defaults | What `Set-OHAMailboxDefaults` actually sets: retention policy name, address book policy, litigation hold yes/no, default calendar sharing | Exact policy names as they appear in EXO. |
| Offboarding rules | Convert to shared? Forward to manager for how many days? Auto-reply text? Litigation hold before removal? | Compliance may own these answers. |
| Distribution lists | Baseline DLs every user joins, per department if any |  |

## AWS WorkSpaces

The backend uses `boto3`. Best fit is an IAM role the app assumes, with no long-lived access keys. If the app lives in Azure, use IAM OIDC federation from the Azure managed identity, or fall back to an IAM user whose keys sit in Key Vault and rotate.

| Item | What to provide | Notes |
| --- | --- | --- |
| AWS accounts | Account IDs for every account that hosts WorkSpaces | You have several; list them all with a label. |
| IAM role per account | `OHALifecycleRole` with a trust policy for the app's identity | One role name across accounts keeps config simple. |
| IAM policy | `workspaces:CreateWorkspaces`, `DescribeWorkspaces`, `TerminateWorkspaces`, `RebootWorkspaces`, `ModifyWorkspaceProperties`, `CreateTags`, `ds:DescribeDirectories` | Least privilege; no `*`. |
| Region(s) | Region per account |  |
| Directory IDs | The AD Connector / Managed AD directory ID per account | Determines which AD the WorkSpace joins. |
| Bundle IDs | Bundle ID per role or department (Standard, Performance, Power, GPU) | Custom bundles change when you rebuild images; keep a lookup. |
| Running mode default | AutoStop vs AlwaysOn, and the AutoStop timeout | Cost driver. |
| Tag standard | Required tags (Department, CostCenter, Owner, JobId) | Feeds your existing cost dashboard. |
| Offboarding rule | Terminate immediately, or stop + hold N days first? | Termination is irreversible. |

## Adobe

Adobe's User Management API (UMAPI) uses a server-to-server OAuth credential created in the Adobe Developer Console. Someone with **System Administrator** in the Adobe Admin Console must create it.

| Item | What to provide | Notes |
| --- | --- | --- |
| Developer Console project | Project with the **User Management API** added, OAuth Server-to-Server credential |  |
| Client ID, Client secret | → Key Vault |  |
| Organization ID | Ends in `@AdobeOrg` → config |  |
| Identity type | Federated ID (SSO via Entra/Okta) or Enterprise ID? | Federated is standard if you have SSO; the API call differs. |
| Product profiles | Exact names of profiles the wizard can assign (e.g. `Acrobat Pro - All Users`, `Creative Cloud - Design`) | These are what `adobe_groups` maps to. |
| User groups | Any Adobe user groups you assign instead of profiles |  |
| Offboarding rule | Remove from profiles only, or delete the user from the org? | Deleting frees the license; removing keeps their asset history. |

## Azure hosting & Azure DevOps

The pipeline in the repo assumes Azure Container Registry, Azure Container Apps, Key Vault, and a Postgres database, all in one resource group. Terraform in `infra/` can build them once the inputs below exist.

| Item | What to provide | Notes |
| --- | --- | --- |
| Azure subscription + resource group | Subscription ID, `rg-oha-lifecycle` |  |
| Azure DevOps project | Project name, repo `oha-lifecycle` |  |
| Service connection: Azure | ARM connection (workload identity federation) to the subscription | Named `oha-azure` in the YAML. |
| Service connection: ACR | Docker registry connection to `ohaacr.azurecr.io` | Named `oha-acr` in the YAML. |
| Variable group | `oha-lifecycle-secrets` linked to Key Vault | Pipeline reads secrets by name at run time. |
| Key Vault | `kv-oha-lifecycle`, with the app's managed identity granted **Key Vault Secrets User** | Holds every secret listed in this doc. |
| Container Apps env | Environment with VNet integration so the app can reach DCs / the Windows agent | Needed for the AD and EXO routes. |
| Postgres | Azure Database for PostgreSQL Flexible Server, DB name, admin login → Key Vault | SQLite is fine for local dev only. |
| Environment approvals | Who approves `prod` deployments in Azure DevOps Environments | At least one person other than the author. |
| Branch policy | Require PR + passing build on `main`, minimum 1 reviewer |  |
| Custom domain + cert | e.g. `lifecycle.oha.internal` | Optional for phase 1. |

## Business inputs (the mapping tables)

The wizard should ask a tech for a name, a department, and a start date, and derive everything else. That only works if these lookups are written down once. Put them in a `config/mappings.yaml` in the repo so changes go through a PR.

| Mapping | Shape | Source of truth today |
| --- | --- | --- |
| Department → AD OU | dept name → OU DN |  |
| Department → AD groups | dept name → list of group DNs |  |
| Department → license SKUs | dept name → list of SKU GUIDs |  |
| Role → WorkSpace | job role → needs WorkSpace yes/no, directory ID, bundle ID |  |
| Department → Adobe profiles | dept name → list of profile names |  |
| Department → distribution lists | dept name → DL addresses |  |
| Office → address/phone attributes | office code → AD attribute values, usage location |  |

Also needed, in plain text:

- Approval rule: does anyone approve an onboarding before it runs, or is submitting enough?
- Offboarding trigger: HR ticket, manager request, or a scheduled last-day date?
- Notification targets: who gets emailed when a job succeeds or fails (a ServiceNow address, a Teams channel)?
- Retention: how long to keep job history and audit rows.

## Checklist

Tick these off as they land. Secrets go to Key Vault; everything else to `config/`.

**Secrets (Key Vault)**

- [ ] AD service account password
- [ ] Graph backend client secret or certificate
- [ ] EXO app-only certificate on the Windows agent
- [ ] Agent API shared key / cert
- [ ] AWS role trust configured (or IAM user keys)
- [ ] Adobe client ID + secret
- [ ] Postgres admin password

**Config (repo)**

- [ ] AD base DN, DC hostnames, target OUs, disabled OU, group DNs
- [ ] Naming and password rules written down
- [ ] Tenant ID, both client IDs, license SKU GUIDs, usage location
- [ ] App roles and Entra group → role mapping
- [ ] EXO policy names and offboarding rules
- [ ] AWS account IDs, regions, directory IDs, bundle IDs, tag standard
- [ ] Adobe org ID, identity type, product profile names
- [ ] `mappings.yaml` for every department/role

**Access & platform**

- [ ] Global Admin consent on both app registrations
- [ ] Exchange Administrator role on the EXO app
- [ ] Adobe System Admin created the UMAPI credential
- [ ] IAM role deployed in every WorkSpaces account
- [ ] Network route from Container Apps VNet to DCs and agent
- [ ] Azure DevOps project, both service connections, variable group, `prod` approvers
- [ ] Decisions on approvals, offboarding trigger, notifications, retention
