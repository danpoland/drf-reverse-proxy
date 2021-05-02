
from mock import patch

import os

from django.test import TestCase, RequestFactory
from six.moves.urllib.parse import ParseResult

from drfreverseproxy.exceptions import InvalidUpstream
from drfreverseproxy.views import ProxyView
from .utils import get_urlopen_mock


class ViewTest(TestCase):

    def setUp(self):
        self.factory = RequestFactory()
        urlopen_mock = get_urlopen_mock()
        self.urlopen_patcher = patch('urllib3.PoolManager.urlopen',
                                     urlopen_mock)
        self.urlopen = self.urlopen_patcher.start()

    def test_connection_pool_singleton(self):
        view1 = ProxyView(upstream='http://example.com/')
        view2 = ProxyView(upstream='http://example.com/')
        self.assertIs(view1.http, view2.http)

    def test_url_injection(self):
        path = 'http://example.org'
        request = self.factory.get(path)

        view = ProxyView.as_view(upstream='http://example.com/')
        view(request, path=path)

        headers = {u'Cookie': u''}
        url = 'http://example.com/http://example.org'

        self.urlopen.assert_called_with('GET', url,
                                        body=b'',
                                        redirect=False,
                                        retries=None,
                                        preload_content=False,
                                        decode_content=False,
                                        headers=headers)

    def test_set_upstream_as_argument(self):
        url = 'http://example.com/'
        view = ProxyView.as_view(upstream=url)

        request = self.factory.get('')
        response = view(request, path='')

        headers = {u'Cookie': u''}
        self.urlopen.assert_called_with('GET', url,
                                        body=b'',
                                        redirect=False,
                                        retries=None,
                                        preload_content=False,
                                        decode_content=False,
                                        headers=headers)

    def test_upstream_not_implemented(self):
        with self.assertRaises(NotImplementedError):
            proxy_view = ProxyView()

    def test_upstream_without_scheme(self):
        class BrokenProxyView(ProxyView):
            upstream = 'www.example.com'

        with self.assertRaises(InvalidUpstream):
            BrokenProxyView()

    def test_upstream_overriden(self):
        class CustomProxyView(ProxyView):
            upstream = 'http://www.google.com/'

        proxy_view = CustomProxyView()
        self.assertEqual(proxy_view.upstream, 'http://www.google.com/')

    def test_upstream_without_trailing_slash(self):
        class CustomProxyView(ProxyView):
            upstream = 'http://example.com/area'

        request = self.factory.get('login')
        CustomProxyView.as_view()(request, path='login')

        headers = {u'Cookie': u''}
        self.urlopen.assert_called_with('GET', 'http://example.com/area/login',
                                        body=b'',
                                        redirect=False,
                                        retries=None,
                                        preload_content=False,
                                        decode_content=False,
                                        headers=headers)

    def test_tilde_is_not_escaped(self):
        class CustomProxyView(ProxyView):
            upstream = 'http://example.com'

        request = self.factory.get('~')
        CustomProxyView.as_view()(request, path='~')

        url = 'http://example.com/~'
        headers = {u'Cookie': u''}
        self.urlopen.assert_called_with('GET', url,
                                        body=b'',
                                        redirect=False,
                                        retries=None,
                                        preload_content=False,
                                        decode_content=False,
                                        headers=headers)

    def test_space_is_escaped(self):
        class CustomProxyView(ProxyView):
            upstream = 'http://example.com'

        path = ' test test'
        request = self.factory.get(path)
        CustomProxyView.as_view()(request, path=path)

        url = 'http://example.com/+test+test'
        headers = {u'Cookie': u''}
        self.urlopen.assert_called_with('GET', url,
                                        body=b'',
                                        redirect=False,
                                        retries=None,
                                        preload_content=False,
                                        decode_content=False,
                                        headers=headers)

    def test_extending_headers(self):
        class CustomProxyView(ProxyView):
            upstream = 'http://example.com'

            def get_proxy_request_headers(self, request):
                headers = super(CustomProxyView, self). \
                    get_proxy_request_headers(request)
                headers['DNT'] = 1
                return headers

        path = ''
        request = self.factory.get(path)
        CustomProxyView.as_view()(request, path=path)

        url = 'http://example.com'
        headers = {u'Cookie': u''}
        custom_headers = {'DNT': 1}
        custom_headers.update(headers)
        self.urlopen.assert_called_with('GET', url,
                                        body=b'',
                                        redirect=False,
                                        retries=None,
                                        preload_content=False,
                                        decode_content=False,
                                        headers=custom_headers)
