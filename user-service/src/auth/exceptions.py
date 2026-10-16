class AuthenticationUnavailableError(RuntimeError):
    pass


class UserAlreadyExistsError(ValueError):
    pass


class UserNotFoundError(ValueError):
    pass
