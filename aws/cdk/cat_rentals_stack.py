"""CAT_RENTALS Hybrid Edge-Cloud Telemetry & Rental Tracking Platform.

Defines:
  - DynamoDB: RentalContracts, EquipmentLiveState
  - S3 data lake for Parquet telemetry (via Firehose conversion)
  - AWS IoT Core topic rule (fleet/telemetry/v1) -> Kinesis Firehose + Lambda
  - Kinesis Data Firehose delivery stream with JSON->Parquet conversion
  - Lambda: AnomalyDetectionLambda (live), OverdueCheckLambda (nightly cron)
  - SNS alert topic
  - Minimal-privilege IAM roles, generated per-resource via CDK grants
"""
import os

from aws_cdk import (
    Duration,
    RemovalPolicy,
    Stack,
)
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_events as events
from aws_cdk import aws_events_targets as targets
from aws_cdk import aws_glue as glue
from aws_cdk import aws_iam as iam
from aws_cdk import aws_iot as iot
from aws_cdk import aws_kinesisfirehose as firehose
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_sns as sns
from aws_cdk import aws_sns_subscriptions as sns_subs
from constructs import Construct


class CatRentalsStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ------------------------------------------------------------------
        # DynamoDB
        # ------------------------------------------------------------------
        self.contracts_table = dynamodb.Table(
            self,
            "RentalContractsTable",
            table_name="RentalContracts",
            partition_key=dynamodb.Attribute(
                name="contract_id", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            point_in_time_recovery_specification=dynamodb.PointInTimeRecoverySpecification(
                point_in_time_recovery_enabled=True
            ),
            removal_policy=RemovalPolicy.RETAIN,
        )
        # Look up the active contract for a piece of equipment.
        self.contracts_table.add_global_secondary_index(
            index_name="equipment-index",
            partition_key=dynamodb.Attribute(
                name="equipment_id", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="status", type=dynamodb.AttributeType.STRING
            ),
        )
        # Nightly scan of active contracts ordered by expected return date.
        self.contracts_table.add_global_secondary_index(
            index_name="status-index",
            partition_key=dynamodb.Attribute(
                name="status", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="expected_return_date", type=dynamodb.AttributeType.STRING
            ),
        )

        self.live_state_table = dynamodb.Table(
            self,
            "EquipmentLiveStateTable",
            table_name="EquipmentLiveState",
            partition_key=dynamodb.Attribute(
                name="equipment_id", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            point_in_time_recovery_specification=dynamodb.PointInTimeRecoverySpecification(
                point_in_time_recovery_enabled=True
            ),
            removal_policy=RemovalPolicy.RETAIN,
        )
        # Fleet-management view: all equipment currently on a given site.
        self.live_state_table.add_global_secondary_index(
            index_name="site-index",
            partition_key=dynamodb.Attribute(
                name="site_id", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="last_seen", type=dynamodb.AttributeType.STRING
            ),
        )

        # ------------------------------------------------------------------
        # S3 data lake
        # ------------------------------------------------------------------
        # Bucket names are globally unique, so the requested
        # "cat-rentals-telemetry-lake" name is suffixed with account/region.
        self.telemetry_lake = s3.Bucket(
            self,
            "TelemetryLakeBucket",
            bucket_name=f"cat-rentals-telemetry-lake-{self.account}-{self.region}",
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.RETAIN,
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="telemetry-tiering",
                    enabled=True,
                    prefix="telemetry/",
                    transitions=[
                        s3.Transition(
                            storage_class=s3.StorageClass.INFREQUENT_ACCESS,
                            transition_after=Duration.days(30),
                        ),
                        s3.Transition(
                            storage_class=s3.StorageClass.GLACIER,
                            transition_after=Duration.days(180),
                        ),
                    ],
                    expiration=Duration.days(2555),  # ~7 years
                ),
            ],
        )

        # ------------------------------------------------------------------
        # Glue catalog table describing the telemetry schema, used by
        # Firehose to convert incoming JSON records to Parquet.
        # ------------------------------------------------------------------
        glue_db = glue.CfnDatabase(
            self,
            "TelemetryGlueDatabase",
            catalog_id=self.account,
            database_input=glue.CfnDatabase.DatabaseInputProperty(
                name="cat_rentals_telemetry_db"
            ),
        )

        telemetry_columns = [
            glue.CfnTable.ColumnProperty(name="equipment_id", type="string"),
            glue.CfnTable.ColumnProperty(name="site_id", type="string"),
            glue.CfnTable.ColumnProperty(name="timestamp", type="string"),
            glue.CfnTable.ColumnProperty(name="engine_hours_today", type="double"),
            glue.CfnTable.ColumnProperty(name="idle_hours_today", type="double"),
            glue.CfnTable.ColumnProperty(name="fuel_level_pct", type="double"),
            glue.CfnTable.ColumnProperty(name="operator_rfid", type="string"),
            glue.CfnTable.ColumnProperty(name="lat", type="double"),
            glue.CfnTable.ColumnProperty(name="lon", type="double"),
            glue.CfnTable.ColumnProperty(name="status", type="string"),
        ]

        glue_table = glue.CfnTable(
            self,
            "TelemetryGlueTable",
            catalog_id=self.account,
            database_name=glue_db.ref,
            table_input=glue.CfnTable.TableInputProperty(
                name="fleet_telemetry",
                table_type="EXTERNAL_TABLE",
                storage_descriptor=glue.CfnTable.StorageDescriptorProperty(
                    columns=telemetry_columns,
                    location=f"s3://{self.telemetry_lake.bucket_name}/telemetry/",
                    input_format="org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat",
                    output_format="org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat",
                    serde_info=glue.CfnTable.SerdeInfoProperty(
                        serialization_library="org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"
                    ),
                ),
            ),
        )
        glue_table.add_resource_dependency(glue_db)

        # ------------------------------------------------------------------
        # SNS alert topic
        # ------------------------------------------------------------------
        self.alert_topic = sns.Topic(
            self,
            "AlertTopic",
            topic_name="cat-rentals-alerts",
            display_name="CAT_RENTALS Fleet Alerts",
        )
        alert_email = os.getenv("ALERT_EMAIL")
        if alert_email:
            self.alert_topic.add_subscription(sns_subs.EmailSubscription(alert_email))

        # ------------------------------------------------------------------
        # Lambda: AnomalyDetectionLambda (invoked live by the IoT rule)
        # ------------------------------------------------------------------
        common_lambda_env = {
            "CONTRACTS_TABLE": self.contracts_table.table_name,
            "STATE_TABLE": self.live_state_table.table_name,
            "ALERT_TOPIC_ARN": self.alert_topic.topic_arn,
        }

        self.anomaly_lambda = lambda_.Function(
            self,
            "AnomalyDetectionLambda",
            function_name="AnomalyDetectionLambda",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="anomaly_detection.handler",
            code=lambda_.Code.from_asset("lambda/anomaly_detection"),
            timeout=Duration.seconds(30),
            memory_size=256,
            environment=common_lambda_env,
            log_group=logs.LogGroup(
                self,
                "AnomalyDetectionLambdaLogGroup",
                log_group_name="/aws/lambda/AnomalyDetectionLambda",
                retention=logs.RetentionDays.ONE_MONTH,
                removal_policy=RemovalPolicy.DESTROY,
            ),
        )
        self.contracts_table.grant_read_data(self.anomaly_lambda)
        self.live_state_table.grant_read_write_data(self.anomaly_lambda)
        self.alert_topic.grant_publish(self.anomaly_lambda)

        # ------------------------------------------------------------------
        # Lambda: OverdueCheckLambda (nightly cron via EventBridge)
        # ------------------------------------------------------------------
        self.overdue_lambda = lambda_.Function(
            self,
            "OverdueCheckLambda",
            function_name="OverdueCheckLambda",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="overdue_check.handler",
            code=lambda_.Code.from_asset("lambda/overdue_check"),
            timeout=Duration.minutes(2),
            memory_size=256,
            environment=common_lambda_env,
            log_group=logs.LogGroup(
                self,
                "OverdueCheckLambdaLogGroup",
                log_group_name="/aws/lambda/OverdueCheckLambda",
                retention=logs.RetentionDays.ONE_MONTH,
                removal_policy=RemovalPolicy.DESTROY,
            ),
        )
        self.contracts_table.grant_read_write_data(self.overdue_lambda)
        self.alert_topic.grant_publish(self.overdue_lambda)

        events.Rule(
            self,
            "OverdueCheckNightlyRule",
            rule_name="cat-rentals-overdue-check-nightly",
            schedule=events.Schedule.cron(minute="0", hour="6"),  # 06:00 UTC daily
            targets=[targets.LambdaFunction(self.overdue_lambda)],
        )

        # ------------------------------------------------------------------
        # Kinesis Data Firehose: buffer + convert to Parquet + write to S3
        # ------------------------------------------------------------------
        firehose_role = iam.Role(
            self,
            "FirehoseDeliveryRole",
            assumed_by=iam.ServicePrincipal("firehose.amazonaws.com"),
        )
        self.telemetry_lake.grant_read_write(firehose_role)
        firehose_role.add_to_policy(
            iam.PolicyStatement(
                actions=["glue:GetTable", "glue:GetTableVersion", "glue:GetTableVersions"],
                resources=[
                    f"arn:aws:glue:{self.region}:{self.account}:catalog",
                    f"arn:aws:glue:{self.region}:{self.account}:database/{glue_db.ref}",
                    f"arn:aws:glue:{self.region}:{self.account}:table/{glue_db.ref}/{glue_table.ref}",
                ],
            )
        )

        firehose_log_group = logs.LogGroup(
            self,
            "FirehoseLogGroup",
            log_group_name="/aws/kinesisfirehose/cat-rentals-telemetry",
            retention=logs.RetentionDays.ONE_MONTH,
            removal_policy=RemovalPolicy.DESTROY,
        )
        firehose_log_group.grant_write(firehose_role)

        self.delivery_stream = firehose.CfnDeliveryStream(
            self,
            "TelemetryFirehose",
            delivery_stream_name="cat-rentals-telemetry-firehose",
            delivery_stream_type="DirectPut",
            extended_s3_destination_configuration=firehose.CfnDeliveryStream.ExtendedS3DestinationConfigurationProperty(
                bucket_arn=self.telemetry_lake.bucket_arn,
                role_arn=firehose_role.role_arn,
                prefix="telemetry/year=!{timestamp:yyyy}/month=!{timestamp:MM}/day=!{timestamp:dd}/",
                error_output_prefix="telemetry-errors/!{firehose:error-output-type}/",
                buffering_hints=firehose.CfnDeliveryStream.BufferingHintsProperty(
                    interval_in_seconds=300, size_in_m_bs=128
                ),
                compression_format="UNCOMPRESSED",  # required to be UNCOMPRESSED when converting to Parquet
                cloud_watch_logging_options=firehose.CfnDeliveryStream.CloudWatchLoggingOptionsProperty(
                    enabled=True,
                    log_group_name=firehose_log_group.log_group_name,
                    log_stream_name="S3Delivery",
                ),
                data_format_conversion_configuration=firehose.CfnDeliveryStream.DataFormatConversionConfigurationProperty(
                    enabled=True,
                    input_format_configuration=firehose.CfnDeliveryStream.InputFormatConfigurationProperty(
                        deserializer=firehose.CfnDeliveryStream.DeserializerProperty(
                            open_x_json_ser_de=firehose.CfnDeliveryStream.OpenXJsonSerDeProperty()
                        )
                    ),
                    output_format_configuration=firehose.CfnDeliveryStream.OutputFormatConfigurationProperty(
                        serializer=firehose.CfnDeliveryStream.SerializerProperty(
                            parquet_ser_de=firehose.CfnDeliveryStream.ParquetSerDeProperty()
                        )
                    ),
                    schema_configuration=firehose.CfnDeliveryStream.SchemaConfigurationProperty(
                        catalog_id=self.account,
                        region=self.region,
                        database_name=glue_db.ref,
                        table_name=glue_table.ref,
                        role_arn=firehose_role.role_arn,
                        version_id="LATEST",
                    ),
                ),
            ),
        )
        self.delivery_stream.node.add_dependency(glue_table)

        # ------------------------------------------------------------------
        # AWS IoT Core: topic rule fans out fleet/telemetry/v1 to Firehose + Lambda
        # ------------------------------------------------------------------
        iot_rule_role = iam.Role(
            self,
            "IotRuleRole",
            assumed_by=iam.ServicePrincipal("iot.amazonaws.com"),
        )
        iot_rule_role.add_to_policy(
            iam.PolicyStatement(
                actions=["firehose:PutRecord", "firehose:PutRecordBatch"],
                resources=[self.delivery_stream.attr_arn],
            )
        )

        self.topic_rule = iot.CfnTopicRule(
            self,
            "FleetTelemetryRule",
            rule_name="cat_rentals_fleet_telemetry_v1",
            topic_rule_payload=iot.CfnTopicRule.TopicRulePayloadProperty(
                sql="SELECT * FROM 'fleet/telemetry/v1'",
                aws_iot_sql_version="2016-03-23",
                actions=[
                    iot.CfnTopicRule.ActionProperty(
                        firehose=iot.CfnTopicRule.FirehoseActionProperty(
                            delivery_stream_name=self.delivery_stream.delivery_stream_name,
                            role_arn=iot_rule_role.role_arn,
                            separator="\n",
                        )
                    ),
                    iot.CfnTopicRule.ActionProperty(
                        lambda_=iot.CfnTopicRule.LambdaActionProperty(
                            function_arn=self.anomaly_lambda.function_arn
                        )
                    ),
                ],
            ),
        )

        self.anomaly_lambda.add_permission(
            "IotInvokeAnomalyLambda",
            principal=iam.ServicePrincipal("iot.amazonaws.com"),
            source_arn=self.topic_rule.attr_arn,
        )
