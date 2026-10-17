class CreditNotFoundError(ValueError):
    pass


class CreditReservationNotFoundError(ValueError):
    pass


class InsufficientCreditsError(ValueError):
    pass


class CreditReservationConflictError(ValueError):
    pass


class CreditConsistencyError(ValueError):
    pass


class CreditRequestConflictError(ValueError):
    pass
