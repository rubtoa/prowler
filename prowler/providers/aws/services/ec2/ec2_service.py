import threading
from datetime import datetime
from typing import Optional

from botocore.client import ClientError
from pydantic import BaseModel

from prowler.lib.logger import logger
from prowler.lib.scan_filters.scan_filters import is_resource_filtered
from prowler.providers.aws.aws_provider import generate_regional_clients


################## EC2
class EC2:
    def __init__(self, audit_info):
        self.service = "ec2"
        self.session = audit_info.audit_session
        self.audited_partition = audit_info.audited_partition
        self.audited_account = audit_info.audited_account
        self.audit_resources = audit_info.audit_resources
        self.regional_clients = generate_regional_clients(self.service, audit_info)
        self.instances = []
        self.__threading_call__(self.__describe_instances__)
        self.__get_instance_user_data__()
        self.security_groups = []
        self.__threading_call__(self.__describe_security_groups__)
        self.network_acls = []
        self.__threading_call__(self.__describe_network_acls__)
        self.snapshots = []
        self.__threading_call__(self.__describe_snapshots__)
        self.__get_snapshot_public__()
        self.network_interfaces = []
        self.__threading_call__(self.__describe_public_network_interfaces__)
        self.__threading_call__(self.__describe_sg_network_interfaces__)
        self.images = []
        self.__threading_call__(self.__describe_images__)
        self.volumes = []
        self.__threading_call__(self.__describe_volumes__)
        self.ebs_encryption_by_default = []
        self.__threading_call__(self.__get_ebs_encryption_by_default__)
        self.elastic_ips = []
        self.__threading_call__(self.__describe_addresses__)

    def __get_session__(self):
        return self.session

    def __threading_call__(self, call):
        threads = []
        for regional_client in self.regional_clients.values():
            threads.append(threading.Thread(target=call, args=(regional_client,)))
        for t in threads:
            t.start()
        for t in threads:
            t.join()

    def __describe_instances__(self, regional_client):
        logger.info("EC2 - Describing EC2 Instances...")
        try:
            describe_instances_paginator = regional_client.get_paginator(
                "describe_instances"
            )
            for page in describe_instances_paginator.paginate():
                for reservation in page["Reservations"]:
                    for instance in reservation["Instances"]:
                        arn = f"arn:{self.audited_partition}:ec2:{regional_client.region}:{self.audited_account}:instance/{instance['InstanceId']}"
                        if not self.audit_resources or (
                            is_resource_filtered(arn, self.audit_resources)
                        ):
                            http_tokens = None
                            http_endpoint = None
                            public_dns = None
                            public_ip = None
                            private_ip = None
                            instance_profile = None
                            if "MetadataOptions" in instance:
                                http_tokens = instance["MetadataOptions"]["HttpTokens"]
                                http_endpoint = instance["MetadataOptions"][
                                    "HttpEndpoint"
                                ]
                            if (
                                "PublicDnsName" in instance
                                and "PublicIpAddress" in instance
                            ):
                                public_dns = instance["PublicDnsName"]
                                public_ip = instance["PublicIpAddress"]
                            if "PrivateIpAddress" in instance:
                                private_ip = instance["PrivateIpAddress"]
                            if "IamInstanceProfile" in instance:
                                instance_profile = instance["IamInstanceProfile"]

                            self.instances.append(
                                Instance(
                                    id=instance["InstanceId"],
                                    arn=arn,
                                    state=instance["State"]["Name"],
                                    region=regional_client.region,
                                    type=instance["InstanceType"],
                                    image_id=instance["ImageId"],
                                    launch_time=instance["LaunchTime"],
                                    private_dns=instance["PrivateDnsName"],
                                    private_ip=private_ip,
                                    public_dns=public_dns,
                                    public_ip=public_ip,
                                    http_tokens=http_tokens,
                                    http_endpoint=http_endpoint,
                                    instance_profile=instance_profile,
                                    tags=instance.get("Tags"),
                                )
                            )
        except Exception as error:
            logger.error(
                f"{regional_client.region} -- {error.__class__.__name__}[{error.__traceback__.tb_lineno}]: {error}"
            )

    def __describe_security_groups__(self, regional_client):
        logger.info("EC2 - Describing Security Groups...")
        try:
            describe_security_groups_paginator = regional_client.get_paginator(
                "describe_security_groups"
            )
            for page in describe_security_groups_paginator.paginate():
                for sg in page["SecurityGroups"]:
                    arn = f"arn:{self.audited_partition}:ec2:{regional_client.region}:{self.audited_account}:security-group/{sg['GroupId']}"
                    if not self.audit_resources or (
                        is_resource_filtered(arn, self.audit_resources)
                    ):
                        self.security_groups.append(
                            SecurityGroup(
                                name=sg["GroupName"],
                                arn=arn,
                                region=regional_client.region,
                                id=sg["GroupId"],
                                ingress_rules=sg["IpPermissions"],
                                egress_rules=sg["IpPermissionsEgress"],
                                tags=sg.get("Tags"),
                            )
                        )
        except Exception as error:
            logger.error(
                f"{regional_client.region} -- {error.__class__.__name__}[{error.__traceback__.tb_lineno}]: {error}"
            )

    def __describe_network_acls__(self, regional_client):
        logger.info("EC2 - Describing Network ACLs...")
        try:
            describe_network_acls_paginator = regional_client.get_paginator(
                "describe_network_acls"
            )
            for page in describe_network_acls_paginator.paginate():
                for nacl in page["NetworkAcls"]:
                    arn = f"arn:{self.audited_partition}:ec2:{regional_client.region}:{self.audited_account}:network-acl/{nacl['NetworkAclId']}"
                    if not self.audit_resources or (
                        is_resource_filtered(arn, self.audit_resources)
                    ):
                        self.network_acls.append(
                            NetworkACL(
                                id=nacl["NetworkAclId"],
                                arn=arn,
                                region=regional_client.region,
                                entries=nacl["Entries"],
                                tags=nacl.get("Tags"),
                            )
                        )
        except Exception as error:
            logger.error(
                f"{regional_client.region} -- {error.__class__.__name__}[{error.__traceback__.tb_lineno}]: {error}"
            )

    def __describe_snapshots__(self, regional_client):
        logger.info("EC2 - Describing Snapshots...")
        try:
            describe_snapshots_paginator = regional_client.get_paginator(
                "describe_snapshots"
            )
            encrypted = False
            for page in describe_snapshots_paginator.paginate(OwnerIds=["self"]):
                for snapshot in page["Snapshots"]:
                    arn = f"arn:{self.audited_partition}:ec2:{regional_client.region}:{self.audited_account}:snapshot/{snapshot['SnapshotId']}"
                    if not self.audit_resources or (
                        is_resource_filtered(arn, self.audit_resources)
                    ):
                        if snapshot["Encrypted"]:
                            encrypted = True
                        self.snapshots.append(
                            Snapshot(
                                id=snapshot["SnapshotId"],
                                arn=arn,
                                region=regional_client.region,
                                encrypted=encrypted,
                                tags=snapshot.get("Tags"),
                            )
                        )
        except Exception as error:
            logger.error(
                f"{regional_client.region} -- {error.__class__.__name__}[{error.__traceback__.tb_lineno}]: {error}"
            )

    def __get_snapshot_public__(self):
        logger.info("EC2 - Gettting snapshots encryption...")
        for snapshot in self.snapshots:
            try:
                regional_client = self.regional_clients[snapshot.region]
                snapshot_public = regional_client.describe_snapshot_attribute(
                    Attribute="createVolumePermission", SnapshotId=snapshot.id
                )
                for permission in snapshot_public["CreateVolumePermissions"]:
                    if "Group" in permission:
                        if permission["Group"] == "all":
                            snapshot.public = True

            except ClientError as error:
                if error.response["Error"]["Code"] == "InvalidSnapshot.NotFound":
                    logger.warning(
                        f"{snapshot.region} --"
                        f" {error.__class__.__name__}[{error.__traceback__.tb_lineno}]:"
                        f" {error}"
                    )
                    continue

            except Exception as error:
                logger.error(
                    f"{error.__class__.__name__}[{error.__traceback__.tb_lineno}]: {error}"
                )

    def __describe_public_network_interfaces__(self, regional_client):
        logger.info("EC2 - Describing Network Interfaces...")
        try:
            # Get Network Interfaces with Public IPs
            describe_network_interfaces_paginator = regional_client.get_paginator(
                "describe_network_interfaces"
            )
            for page in describe_network_interfaces_paginator.paginate():
                for interface in page["NetworkInterfaces"]:
                    if interface.get("Association"):
                        self.network_interfaces.append(
                            NetworkInterface(
                                public_ip=interface["Association"]["PublicIp"],
                                type=interface["InterfaceType"],
                                private_ip=interface["PrivateIpAddress"],
                                subnet_id=interface["SubnetId"],
                                vpc_id=interface["VpcId"],
                                region=regional_client.region,
                                tags=interface.get("TagSet"),
                            )
                        )

        except Exception as error:
            logger.error(
                f"{regional_client.region} -- {error.__class__.__name__}[{error.__traceback__.tb_lineno}]: {error}"
            )

    def __describe_sg_network_interfaces__(self, regional_client):
        logger.info("EC2 - Describing Network Interfaces...")
        try:
            # Get Network Interfaces for Security Groups
            for sg in self.security_groups:
                regional_client = self.regional_clients[sg.region]
                describe_network_interfaces_paginator = regional_client.get_paginator(
                    "describe_network_interfaces"
                )
                for page in describe_network_interfaces_paginator.paginate(
                    Filters=[
                        {
                            "Name": "group-id",
                            "Values": [
                                sg.id,
                            ],
                        },
                    ],
                ):
                    for interface in page["NetworkInterfaces"]:
                        sg.network_interfaces.append(interface["NetworkInterfaceId"])
        except Exception as error:
            logger.error(
                f"{regional_client.region} -- {error.__class__.__name__}[{error.__traceback__.tb_lineno}]: {error}"
            )

    def __get_instance_user_data__(self):
        logger.info("EC2 - Gettting instance user data...")
        for instance in self.instances:
            try:
                regional_client = self.regional_clients[instance.region]
                user_data = regional_client.describe_instance_attribute(
                    Attribute="userData", InstanceId=instance.id
                )["UserData"]
                if "Value" in user_data:
                    instance.user_data = user_data["Value"]

            except ClientError as error:
                if error.response["Error"]["Code"] == "InvalidInstanceID.NotFound":
                    logger.warning(
                        f"{error.__class__.__name__}[{error.__traceback__.tb_lineno}]: {error}"
                    )
                    continue
            except Exception as error:
                logger.error(
                    f"{error.__class__.__name__}[{error.__traceback__.tb_lineno}]: {error}"
                )

    def __describe_images__(self, regional_client):
        logger.info("EC2 - Describing Images...")
        try:
            public = False
            for image in regional_client.describe_images(Owners=["self"])["Images"]:
                arn = f"arn:{self.audited_partition}:ec2:{regional_client.region}:{self.audited_account}:image/{image['ImageId']}"
                if not self.audit_resources or (
                    is_resource_filtered(arn, self.audit_resources)
                ):
                    if image["Public"]:
                        public = True
                    self.images.append(
                        Image(
                            id=image["ImageId"],
                            arn=arn,
                            name=image["Name"],
                            public=public,
                            region=regional_client.region,
                            tags=image.get("Tags"),
                        )
                    )
        except Exception as error:
            logger.error(
                f"{regional_client.region} -- {error.__class__.__name__}[{error.__traceback__.tb_lineno}]: {error}"
            )

    def __describe_volumes__(self, regional_client):
        logger.info("EC2 - Describing Volumes...")
        try:
            describe_volumes_paginator = regional_client.get_paginator(
                "describe_volumes"
            )
            for page in describe_volumes_paginator.paginate():
                for volume in page["Volumes"]:
                    arn = f"arn:{self.audited_partition}:ec2:{regional_client.region}:{self.audited_account}:volume/{volume['VolumeId']}"
                    if not self.audit_resources or (
                        is_resource_filtered(arn, self.audit_resources)
                    ):
                        self.volumes.append(
                            Volume(
                                id=volume["VolumeId"],
                                arn=arn,
                                region=regional_client.region,
                                encrypted=volume["Encrypted"],
                                tags=volume.get("Tags"),
                            )
                        )
        except Exception as error:
            logger.error(
                f"{regional_client.region} -- {error.__class__.__name__}[{error.__traceback__.tb_lineno}]: {error}"
            )

    def __describe_addresses__(self, regional_client):
        logger.info("EC2 - Describing Elastic IPs...")
        try:
            for address in regional_client.describe_addresses()["Addresses"]:
                public_ip = None
                association_id = None
                allocation_id = None
                if "PublicIp" in address:
                    public_ip = address["PublicIp"]
                if "AssociationId" in address:
                    association_id = address["AssociationId"]
                if "AllocationId" in address:
                    allocation_id = address["AllocationId"]
                elastic_ip_arn = f"arn:{self.audited_partition}:ec2:{regional_client.region}:{self.audited_account}:eip-allocation/{allocation_id}"
                if not self.audit_resources or (
                    is_resource_filtered(elastic_ip_arn, self.audit_resources)
                ):
                    self.elastic_ips.append(
                        ElasticIP(
                            public_ip=public_ip,
                            association_id=association_id,
                            allocation_id=allocation_id,
                            arn=elastic_ip_arn,
                            region=regional_client.region,
                            tags=address.get("Tags"),
                        )
                    )
        except Exception as error:
            logger.error(
                f"{regional_client.region} -- {error.__class__.__name__}[{error.__traceback__.tb_lineno}]: {error}"
            )

    def __get_ebs_encryption_by_default__(self, regional_client):
        logger.info("EC2 - Get EBS Encryption By Default...")
        try:
            self.ebs_encryption_by_default.append(
                EbsEncryptionByDefault(
                    status=regional_client.get_ebs_encryption_by_default()[
                        "EbsEncryptionByDefault"
                    ],
                    region=regional_client.region,
                )
            )
        except Exception as error:
            logger.error(
                f"{regional_client.region} -- {error.__class__.__name__}[{error.__traceback__.tb_lineno}]: {error}"
            )


class Instance(BaseModel):
    id: str
    arn: str
    state: str
    region: str
    type: str
    image_id: str
    launch_time: datetime
    private_dns: str
    private_ip: Optional[str]
    public_dns: Optional[str]
    public_ip: Optional[str]
    user_data: Optional[str]
    http_tokens: Optional[str]
    http_endpoint: Optional[str]
    instance_profile: Optional[dict]
    tags: Optional[list] = []


class Snapshot(BaseModel):
    id: str
    arn: str
    region: str
    encrypted: bool
    public: bool = False
    tags: Optional[list] = []


class Volume(BaseModel):
    id: str
    arn: str
    region: str
    encrypted: bool
    tags: Optional[list] = []


class SecurityGroup(BaseModel):
    name: str
    arn: str
    region: str
    id: str
    network_interfaces: list[str] = []
    ingress_rules: list[dict]
    egress_rules: list[dict]
    tags: Optional[list] = []


class NetworkACL(BaseModel):
    id: str
    arn: str
    region: str
    entries: list[dict]
    tags: Optional[list] = []


class NetworkInterface(BaseModel):
    public_ip: str
    private_ip: str
    type: str
    subnet_id: str
    vpc_id: str
    region: str
    tags: Optional[list] = []


class ElasticIP(BaseModel):
    public_ip: Optional[str]
    association_id: Optional[str]
    arn: str
    allocation_id: Optional[str]
    region: str
    tags: Optional[list] = []


class Image(BaseModel):
    id: str
    arn: str
    name: str
    public: bool
    region: str
    tags: Optional[list] = []


class EbsEncryptionByDefault(BaseModel):
    status: bool
    region: str
