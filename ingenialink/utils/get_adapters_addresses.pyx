from GetAdaptersAddresses cimport *
from libc.stdlib cimport malloc, free
import dataclasses
import cython
from libc.string cimport strlen

_MAX_TRIES = 3
_WORKING_BUFFER_SIZE = 15000

cpdef enum AdapterFamily:
    INET = AF_INET
    INET6 = AF_INET6
    UNSPEC = AF_UNSPEC

cpdef enum ScanFlags:
    SKIP_UNICAST = GAA_FLAG_SKIP_UNICAST
    SKIP_ANYCAST = GAA_FLAG_SKIP_ANYCAST
    SKIP_MULTICAST = GAA_FLAG_SKIP_MULTICAST
    SKIP_DNS_SERVER = GAA_FLAG_SKIP_DNS_SERVER
    INCLUDE_PREFIX = GAA_FLAG_INCLUDE_PREFIX
    SKIP_FRIENDLY_NAME = GAA_FLAG_SKIP_FRIENDLY_NAME
    INCLUDE_WINS_INFO = GAA_FLAG_INCLUDE_WINS_INFO
    INCLUDE_GATEWAYS = GAA_FLAG_INCLUDE_GATEWAYS
    INCLUDE_ALL_INTERFACES = GAA_FLAG_INCLUDE_ALL_INTERFACES
    INCLUDE_ALL_COMPARTMENTS = GAA_FLAG_INCLUDE_ALL_COMPARTMENTS
    INCLUDE_TUNNEL_BINDINGORDER = GAA_FLAG_INCLUDE_TUNNEL_BINDINGORDER

@cython.cclass
@dataclasses.dataclass
class CyAdapter:
    IfIndex: int
    AdapterName: str
    Description: str
    FriendlyName: str

cdef _pwchar_to_str(PWCHAR wide_str):
    if wide_str is NULL:
        return None
    
    cdef int length = 0
    while wide_str[length] != 0:
        length += 1
    return (<char *>wide_str)[:length * 2].decode('utf-16le')

cdef list _parse_adapters(PIP_ADAPTER_ADDRESSES_LH adapters_addresses):
    cdef PIP_ADAPTER_ADDRESSES_LH current_adapter = adapters_addresses
    adapters_list = []

    while current_adapter:
        parsed_adapter = CyAdapter(
            IfIndex=current_adapter.IfIndex,
            AdapterName=current_adapter.AdapterName.decode("utf-8"),
            Description=_pwchar_to_str(current_adapter.Description),
            FriendlyName=_pwchar_to_str(current_adapter.FriendlyName),
        )
        adapters_list.append(parsed_adapter)
        current_adapter = current_adapter.Next

    return adapters_list

cdef _get_adapters_addresses_by_family(
    adapter_family: AdapterFamily,
    scan_flags: list[ScanFlags] | ScanFlags,
):
    cdef:
        unsigned long dwRetVal = 0
        unsigned int i = 0
        uint32_t flags = 0
        uint32_t family = <uint32_t> adapter_family

        PIP_ADAPTER_ADDRESSES_LH pAddresses = NULL
        unsigned long outBufLen = 0
        uint32_t Iterations = 0

        PIP_ADAPTER_ADDRESSES_LH pCurrAddresses = NULL
        PIP_ADAPTER_UNICAST_ADDRESS_LH pUnicast = NULL
        PIP_ADAPTER_ANYCAST_ADDRESS_XP pAnycast = NULL
        PIP_ADAPTER_MULTICAST_ADDRESS_XP pMulticast = NULL
        IP_ADAPTER_DNS_SERVER_ADDRESS_XP *pDnServer = NULL
        IP_ADAPTER_PREFIX_XP* pPrefix = NULL
    
    if not isinstance(scan_flags, list):
        scan_flags = [scan_flags]
    for flag in scan_flags:
        flags |= <uint32_t> flag

    outBufLen = _WORKING_BUFFER_SIZE
    while Iterations < _MAX_TRIES:
        pAddresses = <PIP_ADAPTER_ADDRESSES_LH> malloc(outBufLen)
        if pAddresses == NULL:
            raise MemoryError("Memory allocation failed for IP_ADAPTER_ADDRESSES struct")

        dwRetVal = GetAdaptersAddresses(family, flags, NULL, pAddresses, &outBufLen)
        if dwRetVal == ERROR_BUFFER_OVERFLOW:
            free(pAddresses)
            pAddresses = NULL
        else:
            break
        Iterations += 1

    if dwRetVal != NO_ERROR:
        free(pAddresses)
        if dwRetVal == ERROR_NO_DATA:
            raise OSError("No addresses were found for the requested parameters")
        else:
            raise OSError(f"Error trying to retrieve adapter addresses: {dwRetVal}")

    adapters = _parse_adapters(pAddresses)
    free(pAddresses)
    return adapters

def get_adapters_addresses(
    adapter_families: list[AdapterFamily] | AdapterFamily = AdapterFamily.UNSPEC,
    scan_flags: list[ScanFlags] | ScanFlags = ScanFlags.INCLUDE_PREFIX,
) -> list[CyAdapter]:
    adapters = []
    if not isinstance(adapter_families, list):
        adapter_families = [adapter_families]
    for adapter_family in adapter_families:
        adapters.extend(_get_adapters_addresses_by_family(adapter_family, scan_flags))
    return adapters