class ReverseProxyException(Exception):
    """
    Base exception
    """


class InvalidUpstream(ReverseProxyException):
    """
    Invalid upstream
    """
