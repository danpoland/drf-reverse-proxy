drf-reverse-proxy
======================================

[![pypi-version]][pypi]
[![build-status-image]][travis]

Overview
--------

This is a Django REST Framework port of the excellent django-revproxy (https://github.com/TracyWebTech/django-revproxy) library.

This port allows you to reverse proxy HTTP requests while still utilizing DRF features such as authentication, permissions and throttling.

This library works exactly like the django-revproxy library, the documentation for django-revproxy can be found at: http://django-revproxy.readthedocs.org/


Features
---------

* Proxies all HTTP methods: HEAD, GET, POST, PUT, DELETE, OPTIONS, TRACE, CONNECT and PATCH
* Copy all http headers sent from the client to the proxied server
* Copy all http headers sent from the proxied server to the client (except `hop-by-hop <http://www.w3.org/Protocols/rfc2616/rfc2616-sec13.html#sec13.5.1>`_)
* Basic URL rewrite
* Handles redirects
* Few external dependencies
* Maintains the usability of DRF features like authentication, permissions and throttling.


Requirements
------------

-  Python (2.7, 3.3, 3.4, 3.5)
-  Django (1.8, 1.9, 1.10)
-  Django REST Framework (3.3, 3.4, 3.5)

Installation
------------

Install using ``pip``\ …

```bash
$ pip install drf-reverse-proxy
```

Example
-------

Create a custom reverse proxy view:

```python
from drfreverseproxy import ProxyView

class TestProxyView(ProxyView):
   upstream = 'http://example.com'
```

Or just use the default:

```python
from drfreverseproxy import ProxyView

urlpatterns = [
   url(r'^(?P<path>.*)$', ProxyView.as_view(upstream='http://example.com/')),
]
```

[build-status-image]: https://travis-ci.org/danpoland/drf-reverse-proxy.svg?branch=master
[travis]: https://travis-ci.org/danpoland/drf-reverse-proxy
[pypi-version]: https://img.shields.io/pypi/v/drf-reverse-proxy.svg
[pypi]: https://pypi.python.org/pypi/drf-reverse-proxy
