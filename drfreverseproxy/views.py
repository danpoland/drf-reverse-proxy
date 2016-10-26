import re
import logging
import mimetypes

import urllib3

from django.utils.six.moves.urllib.parse import urlparse, urlencode, quote_plus
from django.shortcuts import redirect

from rest_framework.views import APIView

from .pool import PoolManager
from .utilites import normalize_request_headers, encode_items
from .response import get_django_response
from .exceptions import InvalidUpstream


# Chars that don't need to be quoted. We use same as nginx:
#   https://github.com/nginx/nginx/blob/nginx-1.9/src/core/ngx_string.c (Lines 1433-1449)
QUOTE_SAFE = '<.;>\(}*+|~=-$/_:^@)[{]&\'!,"`'

ERRORS_MESSAGES = {
    'upstream-no-scheme': "Upstream URL scheme must be either 'http' or 'https' (%s)."
}

HTTP_POOLS = PoolManager()


class ProxyView(APIView):
    """
    Proxy the Django request, while still tapping into DRF functionality
    like authentication, permissions and throttling.
    """

    _upstream = None

    add_remote_user = False
    default_content_type = 'application/json'
    retries = None
    rewrite = tuple()

    def __init__(self, *args, **kwargs):
        super(ProxyView, self).__init__(**kwargs)

        self._parsed_url = urlparse(self.upstream)

        if self._parsed_url.scheme not in ('http', 'https'):
            raise InvalidUpstream(ERRORS_MESSAGES['upstream-no-scheme'] % self.upstream)

        self._rewrite = []

        for from_pattern, to_pattern in self.rewrite:
            from_re = re.compile(from_pattern)
            self._rewrite.append((from_re, to_pattern))

        self.http = HTTP_POOLS
        self.log = logging.getLogger(__name__)

    @property
    def upstream(self):
        if not self._upstream:
            raise NotImplementedError('Upstream server must be set')

        return self._upstream

    @upstream.setter
    def upstream(self, value):
        self._upstream = value

    def _format_path_to_redirect(self, request):
        full_path = request.get_full_path()
        self.log.debug("Dispatch full path: %s", full_path)

        for from_re, to_pattern in self._rewrite:
            if from_re.match(full_path):
                redirect_to = from_re.sub(to_pattern, full_path)
                self.log.debug("Redirect to: %s", redirect_to)
                return redirect_to

    def get_proxy_request_headers(self, request):
        """
        Get normalized headers for the upstream

        Gets all headers from the original request and normalizes them.
        Normalization occurs by removing the prefix ``HTTP_`` and
        replacing and ``_`` by ``-``. Example: ``HTTP_ACCEPT_ENCODING``
        becomes ``Accept-Encoding``.

        :param request:  The original HTTPRequest instance
        :returns:  Normalized headers for the upstream
        """

        return normalize_request_headers(request)

    def get_request_headers(self):
        """
        Return request headers that will be sent to upstream.

        The header REMOTE_USER is set to the current user
        if the view's add_remote_user property is True
        """

        request_headers = self.get_proxy_request_headers(self.request)

        if self.add_remote_user and self.request.user.is_active:
            request_headers['REMOTE_USER'] = self.request.user.username
            self.log.info("REMOTE_USER set")

        return request_headers

    def _created_proxy_response(self, request, path):
        request_payload = request.body

        self.log.debug("Request headers: %s", self.request_headers)

        path = quote_plus(path.encode('utf8'), QUOTE_SAFE)
        request_url = (self.upstream + '/' if path and self.upstream[-1] != '/' else self.upstream) + path

        self.log.debug("Request URL: %s", request_url)

        if request.GET:
            get_data = encode_items(request.GET.lists())
            request_url += '?' + urlencode(get_data)
            self.log.debug("Request URL: %s", request_url)

        try:
            proxy_response = self.http.urlopen(
                request.method,
                request_url,
                redirect=False,
                retries=self.retries,
                headers=self.request_headers,
                body=request_payload,
                decode_content=False,
                preload_content=False
            )
            self.log.debug("Proxy response header: %s", proxy_response.getheaders())
        except urllib3.exceptions.HTTPError as error:
            self.log.exception(error)
            raise

        return proxy_response

    def _replace_host_on_redirect_location(self, request, proxy_response):
        location = proxy_response.headers.get('Location')

        if location:
            if request.is_secure():
                scheme = 'https://'
            else:
                scheme = 'http://'

            request_host = scheme + request.get_host()

            upstream_host_http = 'http://' + self._parsed_url.netloc
            upstream_host_https = 'https://' + self._parsed_url.netloc

            location = location.replace(upstream_host_http, request_host)
            location = location.replace(upstream_host_https, request_host)

            proxy_response.headers['Location'] = location

            self.log.debug("Proxy response LOCATION: %s", proxy_response.headers['Location'])

    def _set_content_type(self, request, proxy_response):
        content_type = proxy_response.headers.get('Content-Type')

        if not content_type:
            content_type = (mimetypes.guess_type(request.path)[0] or self.default_content_type)
            proxy_response.headers['Content-Type'] = content_type

            self.log.debug("Proxy response CONTENT-TYPE: %s", proxy_response.headers['Content-Type'])

    def dispatch(self, request, *args, **kwargs):
        path = kwargs.get('path', '')

        # This block of code recreates the behavior of the DRF ApiView's dispatch method.
        # It's what allows us to tap into DRF functionality like authorization, permissions and throttling.
        self.args = args
        self.kwargs = kwargs
        request = self.initialize_request(request, *args, **kwargs)
        self.request = request
        self.headers = self.default_response_headers  # deprecate?

        try:
            self.initial(request, *args, **kwargs)
        except Exception as e:
            response = self.handle_exception(exc=e)
            response = self.finalize_response(request, response, *args, **kwargs)
            return response

        # ----- End ApiView block -----

        self.request_headers = self.get_request_headers()

        redirect_to = self._format_path_to_redirect(request)

        if redirect_to:
            return redirect(redirect_to)

        proxy_response = self._created_proxy_response(request, path)

        self._replace_host_on_redirect_location(request, proxy_response)
        self._set_content_type(request, proxy_response)

        response = get_django_response(proxy_response)

        self.log.debug("RESPONSE RETURNED: %s", response)

        return response
