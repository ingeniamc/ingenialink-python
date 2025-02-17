from ingenialink.cython_files.GetAdaptersAddresses cimport *

def get_adapters_addresses() -> list[int]:
    """Retrieves the addresses associated with the adapters on the local computer.

    Returns:
        adapters on the local computer.
    """
    # FIXME: INGK-1017
    return []