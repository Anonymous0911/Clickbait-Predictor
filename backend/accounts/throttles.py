from rest_framework.throttling import SimpleRateThrottle, UserRateThrottle


class AuthThrottle(SimpleRateThrottle):
    """Keyed on IP for everyone. AnonRateThrottle skips signed-in callers, so a throwaway
    account would lift the limit on login guessing."""

    scope = "auth"

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


class PasswordChangeThrottle(UserRateThrottle):
    scope = "password"
