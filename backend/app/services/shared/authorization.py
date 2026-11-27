class AccessDeniedError(Exception):
    """Raised when a user is not permitted to access an object.

    Callers should translate this to a 404 response for object lookups so
    that unauthorized users cannot probe for resource existence.
    """
