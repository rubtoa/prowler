from datetime import datetime
from re import search
from unittest import mock

from prowler.providers.aws.services.ecr.ecr_service import (
    FindingSeverityCounts,
    ImageDetails,
    Registry,
    Repository,
)

# Mock Test Region
AWS_REGION = "eu-west-1"
AWS_ACCOUNT_NUMBER = "123456789012"
repository_name = "test_repo"
repository_arn = (
    f"arn:aws:ecr:eu-west-1:{AWS_ACCOUNT_NUMBER}:repository/{repository_name}"
)
repo_policy_public = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "ECRRepositoryPolicy",
            "Effect": "Allow",
            "Principal": {"AWS": f"arn:aws:iam::{AWS_ACCOUNT_NUMBER}:user/username"},
            "Action": ["ecr:DescribeImages", "ecr:DescribeRepositories"],
        }
    ],
}


class Test_ecr_repositories_scan_vulnerabilities_in_latest_image:
    def test_no_registries(self):
        ecr_client = mock.MagicMock
        ecr_client.registries = {}

        with mock.patch(
            "prowler.providers.aws.services.ecr.ecr_service.ECR",
            ecr_client,
        ):
            from prowler.providers.aws.services.ecr.ecr_repositories_scan_vulnerabilities_in_latest_image.ecr_repositories_scan_vulnerabilities_in_latest_image import (
                ecr_repositories_scan_vulnerabilities_in_latest_image,
            )

            check = ecr_repositories_scan_vulnerabilities_in_latest_image()
            result = check.execute()
            assert len(result) == 0

    def test_registry_no_repositories(self):
        ecr_client = mock.MagicMock
        ecr_client.registries = {}
        ecr_client.registries[AWS_REGION] = Registry(
            id=AWS_ACCOUNT_NUMBER,
            region=AWS_REGION,
            scan_type="BASIC",
            repositories=[],
            rules=[],
        )

        with mock.patch(
            "prowler.providers.aws.services.ecr.ecr_service.ECR",
            ecr_client,
        ):
            from prowler.providers.aws.services.ecr.ecr_repositories_scan_vulnerabilities_in_latest_image.ecr_repositories_scan_vulnerabilities_in_latest_image import (
                ecr_repositories_scan_vulnerabilities_in_latest_image,
            )

            check = ecr_repositories_scan_vulnerabilities_in_latest_image()
            result = check.execute()
            assert len(result) == 0

    def test_empty_repository(self):
        ecr_client = mock.MagicMock
        ecr_client.registries = {}
        ecr_client.registries[AWS_REGION] = Registry(
            id=AWS_ACCOUNT_NUMBER,
            region=AWS_REGION,
            scan_type="BASIC",
            repositories=[
                Repository(
                    name=repository_name,
                    arn=repository_arn,
                    region=AWS_REGION,
                    scan_on_push=True,
                    policy=repo_policy_public,
                    images_details=[],
                    lifecycle_policy=None,
                )
            ],
            rules=[],
        )

        with mock.patch(
            "prowler.providers.aws.services.ecr.ecr_service.ECR",
            ecr_client,
        ):
            from prowler.providers.aws.services.ecr.ecr_repositories_scan_vulnerabilities_in_latest_image.ecr_repositories_scan_vulnerabilities_in_latest_image import (
                ecr_repositories_scan_vulnerabilities_in_latest_image,
            )

            check = ecr_repositories_scan_vulnerabilities_in_latest_image()
            result = check.execute()
            assert len(result) == 0

    def test_image_scaned_without_findings(self):
        ecr_client = mock.MagicMock
        ecr_client.registries = {}
        ecr_client.registries[AWS_REGION] = Registry(
            id=AWS_ACCOUNT_NUMBER,
            region=AWS_REGION,
            scan_type="BASIC",
            repositories=[
                Repository(
                    name=repository_name,
                    arn=repository_arn,
                    region=AWS_REGION,
                    scan_on_push=True,
                    policy=repo_policy_public,
                    images_details=[
                        ImageDetails(
                            latest_tag="test-tag",
                            latest_digest="test-digest",
                            image_pushed_at=datetime(2023, 1, 1),
                            scan_findings_status="COMPLETE",
                            scan_findings_severity_count=FindingSeverityCounts(
                                critical=0, high=0, medium=0
                            ),
                        ),
                    ],
                    lifecycle_policy=None,
                )
            ],
            rules=[],
        )

        with mock.patch(
            "prowler.providers.aws.services.ecr.ecr_service.ECR",
            ecr_client,
        ):
            from prowler.providers.aws.services.ecr.ecr_repositories_scan_vulnerabilities_in_latest_image.ecr_repositories_scan_vulnerabilities_in_latest_image import (
                ecr_repositories_scan_vulnerabilities_in_latest_image,
            )

            check = ecr_repositories_scan_vulnerabilities_in_latest_image()
            result = check.execute()
            assert len(result) == 1
            assert result[0].status == "PASS"
            assert search("scanned without findings", result[0].status_extended)
            assert result[0].resource_id == repository_name
            assert result[0].resource_arn == repository_arn

    def test_image_scanned_with_findings(self):
        ecr_client = mock.MagicMock
        ecr_client.registries = {}
        ecr_client.registries[AWS_REGION] = Registry(
            id=AWS_ACCOUNT_NUMBER,
            region=AWS_REGION,
            scan_type="BASIC",
            repositories=[
                Repository(
                    name=repository_name,
                    arn=repository_arn,
                    region=AWS_REGION,
                    scan_on_push=True,
                    policy=repo_policy_public,
                    images_details=[
                        ImageDetails(
                            latest_tag="test-tag",
                            latest_digest="test-digest",
                            image_pushed_at=datetime(2023, 1, 1),
                            scan_findings_status="COMPLETE",
                            scan_findings_severity_count=FindingSeverityCounts(
                                critical=12, high=34, medium=7
                            ),
                        )
                    ],
                    lifecycle_policy=None,
                )
            ],
            rules=[],
        )

        with mock.patch(
            "prowler.providers.aws.services.ecr.ecr_service.ECR",
            ecr_client,
        ):
            from prowler.providers.aws.services.ecr.ecr_repositories_scan_vulnerabilities_in_latest_image.ecr_repositories_scan_vulnerabilities_in_latest_image import (
                ecr_repositories_scan_vulnerabilities_in_latest_image,
            )

            check = ecr_repositories_scan_vulnerabilities_in_latest_image()
            result = check.execute()
            assert len(result) == 1
            assert result[0].status == "FAIL"
            assert search("scanned with findings:", result[0].status_extended)
            assert result[0].resource_id == repository_name
            assert result[0].resource_arn == repository_arn

    def test_image_scanned_fail_scan(self):
        ecr_client = mock.MagicMock
        ecr_client.registries = {}
        ecr_client.registries[AWS_REGION] = Registry(
            id=AWS_ACCOUNT_NUMBER,
            region=AWS_REGION,
            scan_type="BASIC",
            repositories=[
                Repository(
                    name=repository_name,
                    arn=repository_arn,
                    region=AWS_REGION,
                    scan_on_push=True,
                    policy=repo_policy_public,
                    images_details=[
                        ImageDetails(
                            latest_tag="test-tag",
                            latest_digest="test-digest",
                            image_pushed_at=datetime(2023, 1, 1),
                            scan_findings_status="FAILED",
                            scan_findings_severity_count=FindingSeverityCounts(
                                critical=0, high=0, medium=0
                            ),
                        )
                    ],
                    lifecycle_policy=None,
                )
            ],
            rules=[],
        )

        with mock.patch(
            "prowler.providers.aws.services.ecr.ecr_service.ECR",
            ecr_client,
        ):
            from prowler.providers.aws.services.ecr.ecr_repositories_scan_vulnerabilities_in_latest_image.ecr_repositories_scan_vulnerabilities_in_latest_image import (
                ecr_repositories_scan_vulnerabilities_in_latest_image,
            )

            check = ecr_repositories_scan_vulnerabilities_in_latest_image()
            result = check.execute()
            assert len(result) == 1
            assert result[0].status == "FAIL"
            assert search("with scan status FAILED", result[0].status_extended)
            assert result[0].resource_id == repository_name
            assert result[0].resource_arn == repository_arn

    def test_image_not_scanned(self):
        ecr_client = mock.MagicMock
        ecr_client.registries = {}
        ecr_client.registries[AWS_REGION] = Registry(
            id=AWS_ACCOUNT_NUMBER,
            region=AWS_REGION,
            scan_type="BASIC",
            repositories=[
                Repository(
                    name=repository_name,
                    arn=repository_arn,
                    region=AWS_REGION,
                    scan_on_push=True,
                    policy=repo_policy_public,
                    images_details=[
                        ImageDetails(
                            latest_tag="test-tag",
                            latest_digest="test-digest",
                            image_pushed_at=datetime(2023, 1, 1),
                            scan_findings_status="",
                            scan_findings_severity_count=FindingSeverityCounts(
                                critical=0, high=0, medium=0
                            ),
                        )
                    ],
                    lifecycle_policy=None,
                )
            ],
            rules=[],
        )

        with mock.patch(
            "prowler.providers.aws.services.ecr.ecr_service.ECR",
            ecr_client,
        ):
            from prowler.providers.aws.services.ecr.ecr_repositories_scan_vulnerabilities_in_latest_image.ecr_repositories_scan_vulnerabilities_in_latest_image import (
                ecr_repositories_scan_vulnerabilities_in_latest_image,
            )

            check = ecr_repositories_scan_vulnerabilities_in_latest_image()
            result = check.execute()
            assert len(result) == 1
            assert result[0].status == "FAIL"
            assert search("without a scan", result[0].status_extended)
            assert result[0].resource_id == repository_name
            assert result[0].resource_arn == repository_arn
