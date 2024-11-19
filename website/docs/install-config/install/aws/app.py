#!/usr/bin/env python3

import json

from aws_cdk import (
    App,
    CfnOutput,
    CfnParameter,
    Duration,
    RemovalPolicy,
    Stack,
)
from aws_cdk import (
    aws_ec2 as ec2,
)
from aws_cdk import (
    aws_ecs as ecs,
)
from aws_cdk import (
    aws_elasticache as elasticache,
)
from aws_cdk import (
    aws_elasticloadbalancingv2 as elbv2,
)
from aws_cdk import (
    aws_iam as iam,
)
from aws_cdk import (
    aws_rds as rds,
)
from aws_cdk import (
    aws_s3 as s3,
)
from aws_cdk import (
    aws_secretsmanager as secretsmanager,
)
from constructs import Construct

from authentik import __version__


class AuthentikStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, *kwargs)

        ### Inputs

        db_instance_type = CfnParameter(
            self,
            "DBInstanceType",
            type="String",
            default="m5.large",
            description="RDS PostgreSQL instance type (without the leading db.)",
        )
        db_version = CfnParameter(
            self, "DBVersion", type="String", default="17.1", description="RDS PostgreSQL version"
        )
        db_storage = CfnParameter(
            self,
            "DBStorage",
            type="Number",
            default=10,
            min_value=10,
            description="RDS PostgreSQL storage size in GB",
        )

        redis_instance_type = CfnParameter(
            self,
            "RedisInstanceType",
            type="String",
            default="cache.t4g.medium",
            description="ElastiCache Redis instance type (with the leading cache.)",
        )
        redis_version = CfnParameter(
            self,
            "RedisVersion",
            type="String",
            default="7.1",
            description="ElastiCache Redis version",
        )

        authentik_image = CfnParameter(
            self,
            "AuthentikImage",
            type="String",
            default="ghcr.io/goauthentik/server",
            description="authentik Docker image",
        )
        authentik_version = CfnParameter(
            self,
            "AuthentikVersion",
            type="String",
            default=__version__,
            description="authentik Docker image tag",
        )

        server_cpu = CfnParameter(
            self,
            "AuthentikServerCPU",
            type="Number",
            default=512,
            description="authentik server CPU units (1024 = 1 vCPU)",
        )
        server_memory = CfnParameter(
            self,
            "AuthentikServerMemory",
            type="Number",
            default=1024,
            description="authentik server memory in MiB",
        )
        server_desired_count = CfnParameter(
            self,
            "AuthentikServerDesiredCount",
            type="Number",
            default=2,
            min_value=1,
            description="Desired number of authentik server tasks",
        )

        worker_cpu = CfnParameter(
            self,
            "AuthentikWorkerCPU",
            type="Number",
            default=512,
            description="authentik worker CPU units (1024 = 1 vCPU)",
        )
        worker_memory = CfnParameter(
            self,
            "AuthentikWorkerMemory",
            type="Number",
            default=1024,
            description="authentik worker memory in MiB",
        )
        worker_desired_count = CfnParameter(
            self,
            "AuthentikWorkerDesiredCount",
            type="Number",
            default=2,
            min_value=1,
            description="Desired number of authentik worker tasks",
        )

        storage_media_s3_bucket_name = CfnParameter(
            self,
            "AuthentikStorageMediaS3BucketName",
            type="String",
            description="Bucket name where to store authentik media files",
        )

        certificate_arn = CfnParameter(
            self,
            "CertificateARN",
            type="String",
            description="ACM certificate ARN for HTTPS access",
        )

        authentik_domains = CfnParameter(
            self,
            "AuthentikDomains",
            type="CommaDelimitedList",
            description="List of comma-separated domains from which authentik will be accessed",
        )

        ### Resources

        # VPC

        vpc = ec2.Vpc(self, "AuthentikVpc", max_azs=2, nat_gateways=1)

        # Security Groups

        db_security_group = ec2.SecurityGroup(
            self, "DatabaseSG", vpc=vpc, description="Security Group for authentik RDS PostgreSQL"
        )
        redis_security_group = ec2.SecurityGroup(
            self, "RedisSG", vpc=vpc, description="Security Group for authentik ElastiCache Redis"
        )
        authentik_security_group = ec2.SecurityGroup(
            self, "AuthentikSG", vpc=vpc, description="Security Group for authentik services"
        )
        db_security_group.add_ingress_rule(
            peer=authentik_security_group,
            connection=ec2.Port.tcp(5432),
            description="Allow authentik to connect to RDS PostgreSQL",
        )
        redis_security_group.add_ingress_rule(
            peer=authentik_security_group,
            connection=ec2.Port.tcp(6379),
            description="Allow authentik to connect to ElastiCache Redis",
        )

        # Generated secrets

        db_password = secretsmanager.Secret(
            self,
            "DBPassword",
            generate_secret_string=secretsmanager.SecretStringGenerator(
                secret_string_template=json.dumps({"username": "authentik"}),
                generate_string_key="password",
                password_length=64,
                exclude_characters='"@/\\',
            ),
        )
        secret_key = secretsmanager.Secret(
            self,
            "AuthentikSecretKey",
            generate_secret_string=secretsmanager.SecretStringGenerator(
                password_length=64, exclude_characters='"@/\\'
            ),
        )

        # Database

        database = rds.DatabaseInstance(
            self,
            "AuthentikDB",
            engine=rds.DatabaseInstanceEngine.postgres(
                version=rds.PostgresEngineVersion.of(db_version.value_as_string, ""),
            ),
            instance_type=ec2.InstanceType(db_instance_type.value_as_string),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            allocated_storage=db_storage.value_as_number,
            security_groups=[db_security_group],
            database_name="authentik",
            credentials=rds.Credentials.from_secret(db_password),
            multi_az=True,
            removal_policy=RemovalPolicy.SNAPSHOT,
        )

        # Redis

        redis_subnet_group = elasticache.CfnSubnetGroup(
            self,
            "AuthentikRedisSubnetGroup",
            subnet_ids=vpc.select_subnets(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ).subnet_ids,
            description="Subnet group for authentik ElastiCache Redis",
        )

        redis = elasticache.CfnReplicationGroup(
            self,
            "AuthentikRedis",
            replication_group_description="Redis cluster for authentik",
            engine="redis",
            engine_version=redis_version.value_as_string,
            cache_node_type=redis_instance_type.value_as_string,
            num_cache_clusters=2,
            automatic_failover_enabled=True,
            security_group_ids=[redis_security_group.security_group_id],
            cache_subnet_group_name=redis_subnet_group.ref,
        )

        # S3

        storage_media_s3_bucket = s3.Bucket(
            self,
            "AuthentikS3MediaBucket",
            bucket_name=storage_media_s3_bucket_name.value_as_string,
            removal_policy=RemovalPolicy.RETAIN,
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
            cors=[
                s3.CorsRule(
                    allowed_methods=[s3.HttpMethods.GET],
                    allowed_headers=["Authorization"],
                    allowed_origins=authentik_domains.value_as_list,
                    max_age=3000,
                )
            ],
        )

        s3_access_role = iam.Role(
            self,
            "AuthentikS3AccessRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
        )
        storage_media_s3_bucket.grant_read_write(s3_access_role)

        # ECS Cluster

        cluster = ecs.Cluster(self, "AuthentikCluster", vpc=vpc)

        environment = {
            "AUTHENTIK_POSTGRESQL__HOST": database.instance_endpoint.hostname,
            "AUTHENTIK_POSTGRESQL__USER": "authentik",
            "AUTHENTIK_REDIS__HOST": redis.attr_primary_end_point_address,
            "AUTHENTIK_STORAGE__MEDIA__BACKEND": "s3",
            "AUTHENTIK_STORAGE__MEDIA__S3__REGION": Stack.of(self).region,
        }

        secrets = {
            "AUTHENTIK_POSTGRESQL__PASSWORD": ecs.Secret.from_secrets_manager(
                db_password, field="password"
            ),
            "AUTHENTIK_SECRET_KEY": ecs.Secret.from_secrets_manager(secret_key),
        }

        server_task = ecs.FargateTaskDefinition(
            self,
            "AuthentikServerTask",
            cpu=server_cpu.value_as_number,
            memory_limit_mib=server_memory.value_as_number,
        )
        server_container = server_task.add_container(
            "AuthentikServerContainer",
            image=ecs.ContainerImage.from_registry(
                f"{authentik_image.value_as_string}:{authentik_version.value_as_string}"
            ),
            command=["server"],
            environment=environment,
            secrets=secrets,
            logging=ecs.LogDriver.aws_logs(stream_prefix="authentik-server"),
            enable_restart_policy=True,
            health_check=ecs.HealthCheck(
                command=["CMD", "ak", "healthcheck"],
                interval=Duration.seconds(30),
                retries=3,
                start_period=Duration.seconds(60),
                timeout=Duration.seconds(30),
            ),
        )
        server_container.add_port_mappings(ecs.PortMapping(container_port=9000))
        server_service = ecs.FargateService(
            self,
            "AuthentikServerService",
            cluster=cluster,
            task_definition=server_task,
            desired_count=server_desired_count.value_as_number,
            security_groups=[authentik_security_group],
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
        )
        server_task.add_to_task_role_policy(
            iam.PolicyStatement(
                actions=[
                    "s3:DeleteObject*",
                    "s3:GetBucket*",
                    "s3:GetObject*",
                    "s3:List*",
                    "s3:PutObject*",
                ],
                resources=[
                    storage_media_s3_bucket.bucket_arn,
                    f"{storage_media_s3_bucket.bucket_arn}/*",
                ],
            )
        )

        worker_task = ecs.FargateTaskDefinition(
            self,
            "AuthentikWorkerTask",
            cpu=worker_cpu.value_as_number,
            memory_limit_mib=worker_memory.value_as_number,
        )
        worker_container = worker_task.add_container(  # noqa: F841
            "AuthentikWorkerContainer",
            image=ecs.ContainerImage.from_registry(
                f"{authentik_image.value_as_string}:{authentik_version.value_as_string}"
            ),
            command=["worker"],
            environment=environment,
            secrets=secrets,
            logging=ecs.LogDriver.aws_logs(stream_prefix="authentik-worker"),
            enable_restart_policy=True,
            health_check=ecs.HealthCheck(
                command=["CMD", "ak", "healthcheck"],
                interval=Duration.seconds(30),
                retries=3,
                start_period=Duration.seconds(60),
                timeout=Duration.seconds(30),
            ),
        )
        worker_service = ecs.FargateService(  # noqa: F841
            self,
            "AuthentikWorkerService",
            cluster=cluster,
            task_definition=worker_task,
            desired_count=worker_desired_count.value_as_number,
            security_groups=[authentik_security_group],
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
        )
        worker_task.add_to_task_role_policy(
            iam.PolicyStatement(
                actions=[
                    "s3:DeleteObject*",
                    "s3:GetBucket*",
                    "s3:GetObject*",
                    "s3:List*",
                    "s3:PutObject*",
                ],
                resources=[
                    storage_media_s3_bucket.bucket_arn,
                    f"{storage_media_s3_bucket.bucket_arn}/*",
                ],
            )
        )

        # Load balancer

        lb = elbv2.ApplicationLoadBalancer(
            self,
            "AuthentikALB",
            vpc=vpc,
            internet_facing=True,
        )
        https_redirect = lb.add_listener(  # noqa: F841
            "AuthentikHttpListener",
            port=80,
            default_action=elbv2.ListenerAction.redirect(permanent=True, protocol="HTTPS"),
        )
        listener = lb.add_listener(
            "AuthentikHttpsListener",
            port=443,
            certificates=[
                elbv2.ListenerCertificate(certificate_arn=certificate_arn.value_as_string)
            ],
        )
        target_group = listener.add_targets(  # noqa: F841
            "AuthentikServerTarget",
            protocol=elbv2.ApplicationProtocol.HTTP,
            port=9000,
            targets=[server_service],
            health_check=elbv2.HealthCheck(
                path="/-/health/live/",
                healthy_http_codes="200",
            ),
        )

        CfnOutput(
            self,
            "LoadBalancerDNS",
            value=lb.load_balancer_dns_name,
        )


app = App()
AuthentikStack(app, "AuthentikStack")
app.synth()
