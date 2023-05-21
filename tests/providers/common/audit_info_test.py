import boto3
import botocore
import sure  # noqa
from boto3 import session
from mock import patch
from moto import mock_ec2, mock_resourcegroupstaggingapi

from prowler.providers.aws.lib.audit_info.models import AWS_Audit_Info
from prowler.providers.azure.azure_provider import Azure_Provider
from prowler.providers.azure.lib.audit_info.models import (
    Azure_Audit_Info,
    Azure_Identity_Info,
)
from prowler.providers.common.audit_info import (
    Audit_Info,
    get_tagged_resources,
    set_provider_audit_info,
)
from prowler.providers.gcp.gcp_provider import GCP_Provider
from prowler.providers.gcp.lib.audit_info.models import GCP_Audit_Info

EXAMPLE_AMI_ID = "ami-12c6146b"
AWS_ACCOUNT_NUMBER = "123456789012"


mock_azure_audit_info = Azure_Audit_Info(
    credentials=None,
    identity=Azure_Identity_Info(),
    audit_metadata=None,
    audit_resources=None,
)

mock_set_audit_info = Audit_Info()

# Mocking GetCallerIdentity for China and GovCloud
make_api_call = botocore.client.BaseClient._make_api_call


def mock_get_caller_identity_china(self, operation_name, kwarg):
    if operation_name == "GetCallerIdentity":
        return {
            "UserId": "XXXXXXXXXXXXXXXXXXXXX",
            "Account": AWS_ACCOUNT_NUMBER,
            "Arn": f"arn:aws-cn:iam::{AWS_ACCOUNT_NUMBER}:user/test-user",
        }

    return make_api_call(self, operation_name, kwarg)


def mock_get_caller_identity_gov_cloud(self, operation_name, kwarg):
    if operation_name == "GetCallerIdentity":
        return {
            "UserId": "XXXXXXXXXXXXXXXXXXXXX",
            "Account": AWS_ACCOUNT_NUMBER,
            "Arn": f"arn:aws-us-gov:iam::{AWS_ACCOUNT_NUMBER}:user/test-user",
        }

    return make_api_call(self, operation_name, kwarg)


def mock_validate_credentials(*_):
    caller_identity = {
        "Arn": "arn:aws:iam::123456789012:user/test",
        "Account": "123456789012",
        "UserId": "test",
    }
    return caller_identity


def mock_print_audit_credentials(*_):
    pass


def mock_set_identity_info(*_):
    return Azure_Identity_Info()


def mock_set_azure_credentials(*_):
    return {}


def mock_set_gcp_credentials(*_):
    return (None, "project")


class Test_Set_Audit_Info:
    # Mocked Audit Info
    def set_mocked_audit_info(self):
        audit_info = AWS_Audit_Info(
            session_config=None,
            original_session=None,
            audit_session=session.Session(
                profile_name=None,
                botocore_session=None,
            ),
            audited_account=AWS_ACCOUNT_NUMBER,
            audited_user_id=None,
            audited_partition="aws",
            audited_identity_arn="arn:aws:iam::123456789012:user/test",
            profile=None,
            profile_region="eu-west-1",
            credentials=None,
            assumed_role_info=None,
            audited_regions=["eu-west-2", "eu-west-1"],
            organizations_metadata=None,
            audit_resources=None,
        )

        return audit_info

    @patch(
        "prowler.providers.common.audit_info.validate_aws_credentials",
        new=mock_validate_credentials,
    )
    @patch(
        "prowler.providers.common.audit_info.print_aws_credentials",
        new=mock_print_audit_credentials,
    )
    def test_set_audit_info_aws(self):
        with patch(
            "prowler.providers.common.audit_info.current_audit_info",
            new=self.set_mocked_audit_info(),
        ):
            provider = "aws"
            arguments = {
                "profile": None,
                "role": None,
                "session_duration": None,
                "external_id": None,
                "regions": None,
                "organizations_role": None,
                "subscriptions": None,
                "az_cli_auth": None,
                "sp_env_auth": None,
                "browser_auth": None,
                "managed_entity_auth": None,
            }

            audit_info = set_provider_audit_info(provider, arguments)
            assert isinstance(audit_info, AWS_Audit_Info)

    @patch(
        "prowler.providers.common.audit_info.azure_audit_info",
        new=mock_azure_audit_info,
    )
    @patch.object(Azure_Provider, "__set_credentials__", new=mock_set_azure_credentials)
    @patch.object(Azure_Provider, "__set_identity_info__", new=mock_set_identity_info)
    def test_set_audit_info_azure(self):
        provider = "azure"
        arguments = {
            "profile": None,
            "role": None,
            "session_duration": None,
            "external_id": None,
            "regions": None,
            "organizations_role": None,
            "subscriptions": None,
            # We need to set exactly one auth method
            "az_cli_auth": True,
            "sp_env_auth": None,
            "browser_auth": None,
            "managed_entity_auth": None,
        }

        audit_info = set_provider_audit_info(provider, arguments)
        assert isinstance(audit_info, Azure_Audit_Info)

    @patch.object(GCP_Provider, "__set_credentials__", new=mock_set_gcp_credentials)
    @patch.object(Audit_Info, "print_gcp_credentials", new=mock_print_audit_credentials)
    def test_set_audit_info_gcp(self):
        provider = "gcp"
        arguments = {
            "profile": None,
            "role": None,
            "session_duration": None,
            "external_id": None,
            "regions": None,
            "organizations_role": None,
            "subscriptions": None,
            # We need to set exactly one auth method
            "credentials_file": None,
        }

        audit_info = set_provider_audit_info(provider, arguments)
        assert isinstance(audit_info, GCP_Audit_Info)

    @mock_resourcegroupstaggingapi
    @mock_ec2
    def test_get_tagged_resources(self):
        with patch(
            "prowler.providers.common.audit_info.current_audit_info",
            new=self.set_mocked_audit_info(),
        ) as mock_audit_info:
            client = boto3.client("ec2", region_name="eu-central-1")
            instances = client.run_instances(
                ImageId=EXAMPLE_AMI_ID,
                MinCount=1,
                MaxCount=1,
                InstanceType="t2.micro",
                TagSpecifications=[
                    {
                        "ResourceType": "instance",
                        "Tags": [
                            {"Key": "MY_TAG1", "Value": "MY_VALUE1"},
                            {"Key": "MY_TAG2", "Value": "MY_VALUE2"},
                        ],
                    },
                    {
                        "ResourceType": "instance",
                        "Tags": [{"Key": "ami", "Value": "test"}],
                    },
                ],
            )
            instance_id = instances["Instances"][0]["InstanceId"]
            image_id = client.create_image(Name="testami", InstanceId=instance_id)[
                "ImageId"
            ]
            client.create_tags(
                Resources=[image_id], Tags=[{"Key": "ami", "Value": "test"}]
            )

            mock_audit_info.audited_regions = ["eu-central-1"]
            mock_audit_info.audit_session = boto3.session.Session()
            assert len(get_tagged_resources(["ami=test"], mock_audit_info)) == 2
            assert image_id in str(get_tagged_resources(["ami=test"], mock_audit_info))
            assert instance_id in str(
                get_tagged_resources(["ami=test"], mock_audit_info)
            )
            assert (
                len(get_tagged_resources(["MY_TAG1=MY_VALUE1"], mock_audit_info)) == 1
            )
            assert instance_id in str(
                get_tagged_resources(["MY_TAG1=MY_VALUE1"], mock_audit_info)
            )
