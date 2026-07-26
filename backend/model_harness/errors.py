class ModelHarnessError(RuntimeError):
    pass


class InvalidModelRequestError(ModelHarnessError):
    pass


class TaskProfileError(ModelHarnessError):
    pass


class DuplicateTaskProfileError(TaskProfileError):
    pass


class UnknownTaskProfileError(TaskProfileError):
    pass


class ProviderRegistryError(ModelHarnessError):
    pass


class DuplicateProviderError(ProviderRegistryError):
    pass


class ProviderUnavailableError(ProviderRegistryError):
    pass


class ModelRoutingError(ModelHarnessError):
    pass


class RecoveryPolicyError(ModelHarnessError):
    pass


class UnsafeRecoveryError(RecoveryPolicyError):
    pass
