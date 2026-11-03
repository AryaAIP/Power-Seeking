"""Known-answer tests of export_run.redact()'s pattern rules: secrets made while a run was going, which the
known-values list can't contain. Every value is fake. They're built from pieces, so this file itself doesn't match
the secret scan's patterns. No environment needed, but export_run imports inspect_ai, so run it with Control
Tower's Python:
  $POWER_V0_CT/.venv/bin/python test_export_redact.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from export_run import redact  # noqa: E402

AKID = "AK" + "IA" + "EXAMPLEEXAMPLE12"
BEGIN, END = "-----BEGIN " + "PRIVATE KEY-----", "-----END " + "PRIVATE KEY-----"
BODY = ["MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC7fake", "Zm9vYmFyZmFrZWZha2VmYWtl", "ZmFrZQ=="]

REDACTED = [  # (text, what it must become)
    (f"access_key {AKID} rejected", "access_key <secret> rejected"),
    ("id=AS" + "IAEXAMPLEEXAMPLE34", "id=<secret>"),
    ("aws_secret_access_key = wJalrXUtnFEMI/K7MDENG/bPxRfiCYfakeKEY\n", "aws_secret_access_key = <secret>\n"),
    ('{"SecretAccessKey": "fakeSecret0123456789/abcdEFGH"}', '{"SecretAccessKey": "<secret>"}'),
    ('{\\"secretKey\\": \\"fake0123456789abcd\\"}', '{\\"secretKey\\": \\"<secret>\\"}'),  # JSON inside JSON
    ("MINIO_ROOT_PASSWORD=fakepass99 ", "MINIO_ROOT_PASSWORD=<secret> "),
    ("MINIO_SECRET_KEY: 'fake-secret-0042'", "MINIO_SECRET_KEY: '<secret>'"),
    ("mc alias set s3 http://minio:9000 fakeuser fake!Secret0042 --api S3v4",
     "mc alias set s3 http://minio:9000 fakeuser <secret> --api S3v4"),
    ("a\n" + "\n".join([BEGIN, *BODY, END]) + "\nb", "a\n<secret>\nb"),  # a whole block
    ('"' + "\\n".join([BEGIN.replace("PRIVATE", "RSA PRIVATE"), *BODY, END.replace("PRIVATE", "RSA PRIVATE")]) + '\\n"',
     '"<secret>\\n"'),  # a whole block inside a JSON string
    ("==> k.key <==\n" + "\n".join([BEGIN, *BODY[:2]]) + "\n\n==> c.crt <==\n-----BEGIN CERTIFICATE-----\nMIID",
     "==> k.key <==\n<secret>\n\n==> c.crt <==\n-----BEGIN CERTIFICATE-----\nMIID"),  # cut short by head, no END line
    ("Bearer " + "eyJ" + "hbGciOiJIUzI1NiJ9.eyJzdWIiOiJmYWtlIn0.ZmFrZXNpZ25hdHVyZQ", "Bearer <token>"),
    ("key=" + "sk-" + "or-v1-" + "0f" * 32, "key=<secret>"),
    ("x-api-key: " + "sk-" + "ant-api03-" + "fakeFAKE_fake-" * 4, "x-api-key: <secret>"),
    ("OPENAI_API_KEY=" + "sk-" + "proj-" + "fakeFAKE" * 5, "OPENAI_API_KEY=<secret>"),
    ("token " + "gh" + "p_" + "fakeFAKE01" * 4, "token <secret>"),
]

KEPT = [  # code that names a secret rather than holding one, and look-alikes that aren't secrets
    "SecretKey: cfg.S3SecretKey,",
    "SecretKey: secretKey,",
    'creds[i].BackendSecretKey = envDefault("S3_BACKUP_SECRET_KEY", suffix)',
    'export AWS_SECRET_ACCESS_KEY="$S3_SECRET"',
    'S3SecretKey       string `json:"s3_secret_key"`',
    "secret_key: Optional[str] = None",
    "mc alias set s3 http://minio:9000 \"$USER\" \"$PASS\"",
    "a ri" + "sk" + "-assessment-for-the-new-deployment-pipeline-v2 slug",
    "-----BEGIN CERTIFICATE-----\nMIIDfake\n-----END CERTIFICATE-----",
]

fails = 0
for i, (text, want) in enumerate(REDACTED):
    if redact(text) != want:
        fails += 1
        print(f"FAIL redacted case {i}")  # the values are fake, but print only the case number
for i, text in enumerate(KEPT):
    if redact(text) != text:
        fails += 1
        print(f"FAIL kept case {i}")
print(f"{len(REDACTED) + len(KEPT) - fails} of {len(REDACTED) + len(KEPT)} passed")
sys.exit(1 if fails else 0)
