class StoreError(Exception):
    pass


class StoreVersionError(StoreError):
    pass


class StoreCorruptError(StoreError):
    pass


class StoreValidationError(StoreError):
    pass


class UnitConversionError(StoreError):
    pass
