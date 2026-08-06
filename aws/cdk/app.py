#!/usr/bin/env python3
"""CDK app entrypoint for the CAT_RENTALS Hybrid Edge-Cloud Telemetry & Rental
Tracking Platform stack."""
import os

import aws_cdk as cdk

from cat_rentals_stack import CatRentalsStack

app = cdk.App()

env = cdk.Environment(
    account=os.getenv("AWS_ACCOUNT_ID") or os.getenv("CDK_DEFAULT_ACCOUNT"),
    region=os.getenv("AWS_REGION") or os.getenv("CDK_DEFAULT_REGION", "us-east-1"),
)

CatRentalsStack(
    app,
    "CatRentalsStack",
    env=env,
    description="CAT_RENTALS Hybrid Edge-Cloud Telemetry & Rental Tracking Platform",
)

app.synth()
