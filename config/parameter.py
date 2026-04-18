import os
import boto3

def load_ssm_parameters():
    ssm = boto3.client("ssm", region_name="ap-south-1")

    parameter_names = [
        "/test-suite/OPENAI_API_KEY",
        "/test-suite/ANTHROPIC_API_KEY",
        "/test-suite/AWS_ACCESS_KEY_ID",
        "/test-suite/AWS_SECRET_ACCESS_KEY",
        "/test-suite/DATABASE_URL",
    ]

    response = ssm.get_parameters(
        Names=parameter_names,
        WithDecryption=True
    )

    for param in response["Parameters"]:
        key = param["Name"].split("/")[-1]
        # Do not override values already set in environment (e.g., local DB tunnel)
        if not os.getenv(key):
            os.environ[key] = param["Value"]

try:
    load_ssm_parameters()
except Exception:
    # Allow local/dev startup even if SSM is unavailable
    pass

