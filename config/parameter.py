import os
import boto3

def load_ssm_parameters():
    ssm = boto3.client("ssm", region_name="ap-south-1")

    parameter_names = [
        "/test-suite/OPENAI_API_KEY",
        "/test-suite/ANTHROPIC_API_KEY",
        "/test-suite/AWS_ACCESS_KEY_ID",
        "/test-suite/AWS_SECRET_ACCESS_KEY",
    ]

    response = ssm.get_parameters(
        Names=parameter_names,
        WithDecryption=True
    )

    for param in response["Parameters"]:
        key = param["Name"].split("/")[-1]
        os.environ[key] = param["Value"]

load_ssm_parameters()

