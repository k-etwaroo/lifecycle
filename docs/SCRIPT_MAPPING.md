# Codes/ → oha-lifecycle mapping

| Old script | New location | Notes |
|---|---|---|
| OHA Onboarding/New-OHAUser.ps1 | `workflows/onboard.py` → `ad.create_user`, `ad.add_groups` | office table → `mappings.yaml:offices`; random password replaces `OHAWelcome1!` |
| OHA Onboarding/NewUser-Exchange.ps1 | `exo.mailbox_settings` via Windows agent | wait/archive/retention/17a-4 FullAccess |
| OHA Onboarding/Create-WorkSpaces-Combined.ps1 | `aws.create_workspace` | 4 targets in `mappings.yaml:workspaces.targets`; boto3 replaces CLI |
| OHA Onboarding/New Signature.ps1 | `docs.email_signature` | python-docx, no Word COM |
| OHA Onboarding/Capture User's groups.ps1 | `GET /utilities/users/{sam}/groups`; also `ad.snapshot` in offboarding | |
| OHA Onboarding/Groups to send Owners.ps1 | `GET /utilities/groups/ownership-report` | reads AD directly, no Excel input |
| OHA Onboarding/Launch-NewOHA-AsTech.ps1 + .bat | removed | Entra SSO + service account |
| Adobe/Adobe-Acrobat-Provisioning.ps1 | `adobe.add_user`, `adobe.remove_user`, `GET /utilities/adobe/seats` | profiles in `mappings.yaml:adobe` |
| Offboarding/ImmediateActionTasks.ps1 | `ad.block_dl_send`, `ad.set_expiration` | office DL DNs in `mappings.yaml:offices.*.dl` |
| Offboarding/Account Access Tasks for AD.ps1 | `ad.disable_user`, `ad.strip_groups`, `ad.move_to_disabled` | excluded groups in `mappings.yaml:offboarding` |
| Offboarding/Capture Managed By field for Single User.ps1 | `GET /utilities/users/{sam}/owned-groups` | |
| Offboarding/Update Managed by field to new owner.ps1 | `ad.reassign_group_ownership`; `POST /utilities/groups/reassign-owner` | INC number required |
| Calendar Permissioning/Grant-Calendar*.ps1 | `POST /utilities/calendar-access` | Editor / Reviewer, bulk owners |
| Adobe/.env | Key Vault `UMAPI_*` | **rotate the secret** |
