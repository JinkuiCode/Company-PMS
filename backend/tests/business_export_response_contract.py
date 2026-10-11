"""Business download responses remove their file on every completion path."""
import asyncio
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.api import business_exports


class BusinessExportResponseContract(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='pms-export-response-test-')
        self.path = Path(self.directory.name) / 'export.xlsx'
        self.content = b'PK\x03\x04business-export-response-fixture'
        self.path.write_bytes(self.content)
        self.messages = []
        self.context = {'user_id': 7, 'permissions': ['project:list:view', 'project:list:export']}

    def tearDown(self):
        self.directory.cleanup()

    def response(self):
        data = business_exports.BusinessExportRequest(columns=['project_code'])
        db, request = object(), object()
        with patch.object(business_exports, 'create_business_export', return_value=(self.path, '项目列表.xlsx')) as create:
            response = business_exports.download(db, 'project', data, self.context, request)
        create.assert_called_once_with(db, 'project', data, self.context, request, project_id=None)
        return response

    async def send(self, message):
        self.assertTrue(self.path.exists(), 'file must remain available while the response is sending')
        self.messages.append(message)

    async def receive(self):
        raise AssertionError('a file download must not read a request body')

    async def invoke(self, response, *, range_header=None, send=None):
        headers = [] if range_header is None else [(b'range', range_header.encode('ascii'))]
        await response({'type': 'http', 'method': 'POST', 'headers': headers}, self.receive, send or self.send)

    def assert_cleaned_response(self, status):
        self.assertEqual(self.messages[0]['status'], status)
        self.assertFalse(self.path.exists(), 'export file leaked after response completion')

    async def test_success_preserves_download_headers_and_bytes_then_deletes(self):
        await self.invoke(self.response())
        self.assert_cleaned_response(200)
        headers = dict(self.messages[0]['headers'])
        self.assertEqual(headers[b'content-type'], b'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        self.assertEqual(headers[b'content-disposition'].decode(), "attachment; filename*=utf-8''" + quote('项目列表.xlsx'))
        self.assertEqual(b''.join(m.get('body', b'') for m in self.messages), self.content)

    async def test_valid_partial_range_preserves_bytes_then_deletes(self):
        await self.invoke(self.response(), range_header='bytes=0-3')
        self.assert_cleaned_response(206)
        self.assertEqual(b''.join(m.get('body', b'') for m in self.messages), self.content[:4])

    async def test_unsatisfiable_range_returns_416_and_deletes(self):
        await self.invoke(self.response(), range_header='bytes=999999999999-')
        self.assert_cleaned_response(416)

    async def test_malformed_range_returns_400_and_deletes(self):
        await self.invoke(self.response(), range_header='not-a-range')
        self.assert_cleaned_response(400)

    async def test_send_header_failure_propagates_and_deletes(self):
        failure = OSError('response header send failed')

        async def fail(message):
            await self.send(message)
            raise failure

        with self.assertRaises(OSError) as caught:
            await self.invoke(self.response(), send=fail)
        self.assertIs(caught.exception, failure)
        self.assertFalse(self.path.exists(), 'export file leaked after send failure')

    async def test_send_body_failure_propagates_and_deletes(self):
        failure = OSError('response body send failed')

        async def fail(message):
            await self.send(message)
            if message['type'] == 'http.response.body':
                raise failure

        with self.assertRaises(OSError) as caught:
            await self.invoke(self.response(), send=fail)
        self.assertIs(caught.exception, failure)
        self.assertFalse(self.path.exists(), 'export file leaked after body failure')

    async def test_send_cancellation_propagates_and_deletes(self):
        async def cancel(message):
            await self.send(message)
            if message['type'] == 'http.response.body':
                raise asyncio.CancelledError()

        with self.assertRaises(asyncio.CancelledError):
            await self.invoke(self.response(), send=cancel)
        self.assertFalse(self.path.exists(), 'export file leaked after cancellation')


if __name__ == '__main__':
    unittest.main()
