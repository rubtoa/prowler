import uuid
from unittest import mock

from prowler.providers.aws.services.acm.acm_service import Certificate

AWS_REGION = "us-east-1"
AWS_ACCOUNT_NUMBER = "123456789012"
DAYS_TO_EXPIRE_THRESHOLD = 7


class Test_acm_certificates_expiration_check:
    def test_no_acm_certificates(self):
        acm_client = mock.MagicMock
        acm_client.certificates = []

        with mock.patch(
            "prowler.providers.aws.services.acm.acm_service.ACM",
            new=acm_client,
        ):
            # Test Check
            from prowler.providers.aws.services.acm.acm_certificates_transparency_logs_enabled.acm_certificates_transparency_logs_enabled import (
                acm_certificates_transparency_logs_enabled,
            )

            check = acm_certificates_transparency_logs_enabled()
            result = check.execute()

            assert len(result) == 0

    def test_acm_certificate_expirated(self):
        certificate_arn = f"arn:aws:acm:{AWS_REGION}:{AWS_ACCOUNT_NUMBER}:certificate/{str(uuid.uuid4())}"
        certificate_name = "test-certificate.com"
        certificate_type = "AMAZON_ISSUED"

        acm_client = mock.MagicMock
        acm_client.certificates = [
            Certificate(
                arn=certificate_arn,
                name=certificate_name,
                type=certificate_type,
                expiration_days=5,
                transparency_logging=True,
                region=AWS_REGION,
            )
        ]

        with mock.patch(
            "prowler.providers.aws.services.acm.acm_service.ACM",
            new=acm_client,
        ):
            # Test Check
            from prowler.providers.aws.services.acm.acm_certificates_expiration_check.acm_certificates_expiration_check import (
                acm_certificates_expiration_check,
            )

            check = acm_certificates_expiration_check()
            result = check.execute()

            assert len(result) == 1
            assert result[0].status == "FAIL"
            assert (
                result[0].status_extended
                == f"ACM Certificate for {certificate_name} is about to expire in {DAYS_TO_EXPIRE_THRESHOLD} days."
            )
            assert result[0].resource_id == certificate_name
            assert result[0].resource_arn == certificate_arn
            assert result[0].region == AWS_REGION

    def test_acm_certificate_not_expirated(self):
        certificate_arn = f"arn:aws:acm:{AWS_REGION}:{AWS_ACCOUNT_NUMBER}:certificate/{str(uuid.uuid4())}"
        certificate_name = "test-certificate.com"
        certificate_type = "AMAZON_ISSUED"
        expiration_days = 365

        acm_client = mock.MagicMock
        acm_client.certificates = [
            Certificate(
                arn=certificate_arn,
                name=certificate_name,
                type=certificate_type,
                expiration_days=expiration_days,
                transparency_logging=True,
                region=AWS_REGION,
            )
        ]

        with mock.patch(
            "prowler.providers.aws.services.acm.acm_service.ACM",
            new=acm_client,
        ):
            # Test Check
            from prowler.providers.aws.services.acm.acm_certificates_expiration_check.acm_certificates_expiration_check import (
                acm_certificates_expiration_check,
            )

            check = acm_certificates_expiration_check()
            result = check.execute()

            assert len(result) == 1
            assert result[0].status == "PASS"
            assert (
                result[0].status_extended
                == f"ACM Certificate for {certificate_name} expires in {expiration_days} days."
            )
            assert result[0].resource_id == certificate_name
            assert result[0].resource_arn == certificate_arn
            assert result[0].region == AWS_REGION
