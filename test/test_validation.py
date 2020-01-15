import unittest

from cf_es_mirror.validation import validate_request

from .base import BaseTestCase


VALID_HEADERS = {
    "X-Contentful-Topic": "ContentManagement.Entry.publish",
    "X-Contentful-Webhook-Name": "Anything",
    "Content-Type": "application/vnd.contentful.management.v1+json",
}


class ValidationTestCase(BaseTestCase):
    EXTRA_SETTINGS = {
        "WEBHOOK_AUTH": {"test": "test"},
    }
    def test_missing_headers(self):
        tests = [
            {},
            {"X-Contentful-Topic": "something"},
            {"X-Contentful-Topic": "something", "X-Contentful-Webhook-Name": "something"},
        ]
        for test in tests:
            self.assertEqual(validate_request(test, {}, {}), -1, "Did not invalidate request properly.")

    def test_webhook_auth(self):
        self.assertEqual(validate_request(VALID_HEADERS, {}, {}), -2, "Did not invalidate missing auth properly.")
        self.assertEqual(validate_request(VALID_HEADERS, {"username": "wrong", "password": "user"}, {}), -2, "Did not invalidate wrong auth user properly.")
        self.assertEqual(validate_request(VALID_HEADERS, {"username": "test", "password": "wrong"}, {}), -2, "Did not invalidate wrong auth password properly.")
        self.assertNotEqual(validate_request(VALID_HEADERS, {"username": "test", "password": "test"}, {}), -2, "Did not pass auth properly.")
