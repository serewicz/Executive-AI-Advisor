# AcquisitionTargetCo Security Assessment

Synthetic demo document for Executive AI Advisor. Not based on any real company.

## Executive Summary

AcquisitionTargetCo has basic security controls but lacks a formal security program. The company has avoided known major security incidents, but its current posture reflects a small founder-led SaaS business rather than an acquisition-ready enterprise software asset.

Security ownership is informal. MFA is enabled for most systems but not all administrative tools. There is no formal vulnerability management process. Customer data is duplicated into staging with weak masking. These findings should be addressed immediately after close, and some should be remediated before close if customer or regulatory exposure is material.

## Identity and Access

Core systems use individual accounts, and MFA is enabled for Google Workspace, GitHub, AWS console access, and the primary support tool. However, not all administrative tools are covered. Several legacy admin portals and database utility tools rely on strong passwords but do not enforce MFA.

Access reviews are informal. The founder and operations manager review access during onboarding and offboarding, but there is no quarterly attestation process or complete evidence package. This creates audit and integration risk for the acquirer.

## Application Security

The Django application uses role-based permissions for common workflows. Customer data is separated logically by account. There is no evidence of known tenant data leakage, but automated authorization testing is limited.

The application has several older administrative views that rely on staff permissions and manual operating discipline. These views should be reviewed for least privilege and audit logging before integration.

## Vulnerability Management

There is no formal vulnerability management process. Dependency updates occur when engineers notice alerts or when a release requires package updates. Security patches are prioritized when obvious, but there is no documented SLA by severity.

The company should complete dependency scanning, container or server baseline review, and a third-party penetration test as part of acquisition remediation.

## Staging Data Risk

Customer data is duplicated into staging with weak masking. This is a material concern. Staging is useful for reproducing customer issues, but production data should not be broadly available in non-production environments without strong masking, access controls, and retention rules.

The acquirer should treat staging data remediation as a day-one priority.

## Backup and Recovery

Backups exist through RDS automated backups and S3 versioning for selected buckets. Restore testing is not recent. The team believes recovery would work, but cannot provide current evidence.

This is an operational and security risk. The buyer should require a restore test before or immediately after close.

## Recommendations

- Enforce MFA across all administrative tools.
- Complete access review before close.
- Create formal vulnerability management with severity SLAs.
- Mask customer data in staging.
- Review older administrative views for least privilege.
- Run a backup restore test.
- Create security owner matrix for post-close operations.
- Conduct penetration testing within the first 100 days.

## Overall Assessment

Security risk is moderate to high due to informal ownership and weak non-production data controls. The issues are fixable, but they should be explicitly included in acquisition planning and purchase agreement risk discussions.

## Immediate Remediation Plan

The first remediation wave should focus on basic controls rather than advanced tooling. All administrative systems should enforce MFA. All users with production, database, support, and vendor access should be reviewed. Staging data should be masked or replaced with synthetic data. Dependency and server vulnerability scanning should be enabled with severity-based remediation targets.

The second wave should formalize ownership. The acquirer should name a security owner, create a vulnerability management calendar, review administrative views, define logging expectations, and document incident response. These changes should be lightweight enough for a small product team but clear enough for enterprise governance.

The buyer should also consider whether any customer contracts require notification of data handling changes during integration. Staging data remediation may be both a security issue and a customer trust issue.
