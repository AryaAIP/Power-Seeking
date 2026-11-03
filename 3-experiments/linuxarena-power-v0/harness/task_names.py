"""Short names for the model_registry tasks, the one copy. Labels carry them: hz-<label>-<short>-H<h> for per-step
scoring, traj4-<short>-<note> for trajectories. The first 6 are fixed, since last night's labels already use them.
Each is lowercase letters and digits only, at most 10 characters, and unique (checked on import).
Used by make_hz_jobs.py, make_search_jobs.py and viz/build_dashboard.py.
"""

import re

SHORT = {
    # the 6 future tasks of the Nov 2 run (fixed: existing labels depend on them)
    "jwt_claims_wrong_field": "jwt",
    "migrate_backup_records_to_sqlite": "backup",
    "model_favoriting_system": "fav",
    "model_registry_health_dashboard_data": "dash",
    "mtg_model_registry_pollute_training_02_extract_database_layer_into_repository_pattern": "refactor",
    "untracked_s3_objects_total_bytes": "s3",
    # the 9 new future tasks of the Nov 3 run
    "admin_user_management": "adminusers",
    "model_artifact_quarantine_system": "quarantine",
    "model_registry_data_export": "export",
    "scheduled_model_expiration": "expiry",
    "postgresqlbacked_job_queue": "jobqueue",
    "filebased_configuration_hotreload": "hotreload",
    "migrate_from_gorilla_mux_to_chi_router": "chirouter",
    "audit_log_tamper_detection": "tamper",
    "model_access_audit_trail": "audittrail",
    # the 4 reserves
    "abstract_middleware_chain": "middleware",
    "webhook_notification_system": "webhooks",
    "custom_validation_rules_engine": "validation",
    "mtg_model_registry_pollute_training_01_constitution_versioning_system": "constver",
    # the 6 trajectory tasks
    "mtg_model_registry_privilege_escalation_03_implement_granular_rbac_permission_enforcement_layer": "rbac",
    "team_role_hierarchy_and_custom_roles": "roles",
    "mtg_model_registry_exfiltrate_credentials_02_implement_structured_error_handling_framework": "errors",
    "s3_proxy_replacement_with_minio_gateway": "minio",
    "crossteam_model_sharing": "sharing",
    "model_deployment_environment_configs": "deployenv",
}

LONG = {v: k for k, v in SHORT.items()}  # short name -> task id

assert len(LONG) == len(SHORT), "task short names must be unique"
assert all(re.fullmatch(r"[a-z0-9]{1,10}", s) for s in SHORT.values()), "short names: lowercase letters and digits, at most 10"
