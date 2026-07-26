class CapabilityRegistryError(RuntimeError):
    pass


class CapabilityRegistryNotLoadedError(CapabilityRegistryError):
    pass


class CapabilityRegistryValidationError(CapabilityRegistryError):
    pass


class BenchmarkArtifactError(CapabilityRegistryError):
    pass


class BenchmarkHashMismatchError(BenchmarkArtifactError):
    pass


class UnsupportedBenchmarkFormatError(BenchmarkArtifactError):
    pass


class UnknownCapabilityError(CapabilityRegistryError):
    pass


class UnknownModelError(CapabilityRegistryError):
    pass


class UnknownCompatibilityTargetError(CapabilityRegistryError):
    pass
