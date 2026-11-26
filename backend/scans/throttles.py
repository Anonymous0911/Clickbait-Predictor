from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


class ScanAnonThrottle(AnonRateThrottle):
    scope = "scan_anon"


class ScanUserThrottle(UserRateThrottle):
    scope = "scan_user"
