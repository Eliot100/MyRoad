"""Store / domain errors for MyRoad persistence."""


class StoreError(Exception):
    """Base persistence error with a stable machine code."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


class NotFoundError(StoreError):
    def __init__(self, message: str) -> None:
        super().__init__("NOT_FOUND", message)


class ImmutableError(StoreError):
    def __init__(self, message: str) -> None:
        super().__init__("IMMUTABLE", message)


class StatusError(StoreError):
    def __init__(self, message: str) -> None:
        super().__init__("INVALID_STATUS", message)


class RbacDenyError(StoreError):
    def __init__(self, message: str) -> None:
        super().__init__("RBAC_DENY", message)
