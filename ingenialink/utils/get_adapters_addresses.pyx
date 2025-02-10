from GetAdaptersAddresses cimport *
from libc.stdlib cimport malloc, free
from libc.stdint cimport uint32_t
import dataclasses
import cython

_MAX_TRIES = 3
_WORKING_BUFFER_SIZE = 15000

cpdef enum AdapterFamily:
    INET = 0
    INET6 = 1
    UNSPEC = 2

@cython.cclass
@dataclasses.dataclass
class CyAdapter:
    IfIndex: int
    #AdapterName: str
    #Description: str
    #FriendlyName: str

cdef list _parse_adapters(PIP_ADAPTER_ADDRESSES_LH adapters_addresses):
    cdef PIP_ADAPTER_ADDRESSES_LH current_adapter = adapters_addresses
    adapters_list = []

    while current_adapter:
        parsed_adapter = CyAdapter(
            IfIndex=current_adapter.IfIndex,
            #AdapterName=current_adapter.AdapterName.decode("utf-8"),
            #Description=current_adapter.Description.decode("utf-8"),
            #FriendlyName=current_adapter.FriendlyName.decode("utf-8"),
        )
        print(parsed_adapter)
        print("-----------")
        adapters_list.append(parsed_adapter)
        current_adapter = current_adapter.Next

    return adapters_list

def get_adapters_addresses(adapter_family: AdapterFamily = AdapterFamily.UNSPEC):
    cdef:
        unsigned long dwRetVal = 0
        unsigned int i = 0
        unsigned long flags = GAA_FLAG_INCLUDE_PREFIX
        unsigned long family = AF_UNSPEC

        PIP_ADAPTER_ADDRESSES_LH pAddresses = NULL
        unsigned long outBufLen = 0
        uint32_t Iterations = 0

        PIP_ADAPTER_ADDRESSES_LH pCurrAddresses = NULL
        PIP_ADAPTER_UNICAST_ADDRESS_LH pUnicast = NULL
        PIP_ADAPTER_ANYCAST_ADDRESS_XP pAnycast = NULL
        PIP_ADAPTER_MULTICAST_ADDRESS_XP pMulticast = NULL
        IP_ADAPTER_DNS_SERVER_ADDRESS_XP *pDnServer = NULL
        IP_ADAPTER_PREFIX_XP* pPrefix = NULL
    
    if adapter_family == AdapterFamily.INET:
        family = AF_INET
    elif adapter_family == AdapterFamily.INET6:
        family = AF_INET6

    outBufLen = _WORKING_BUFFER_SIZE
    dwRetVal = ERROR_BUFFER_OVERFLOW # TODO:check this magic

    print(f"Checking {family=}")
    print(f"{dwRetVal=}, {ERROR_BUFFER_OVERFLOW=}")

    while (dwRetVal == ERROR_BUFFER_OVERFLOW) & (Iterations < _MAX_TRIES):
        pAddresses = <PIP_ADAPTER_ADDRESSES_LH> malloc(outBufLen)
        if pAddresses == NULL:
            raise MemoryError("Memory allocation failed for IP_ADAPTER_ADDRESSES struct")

        dwRetVal = GetAdaptersAddresses(family, flags, NULL, pAddresses, &outBufLen)
        if dwRetVal == ERROR_BUFFER_OVERFLOW:
            print(f"{Iterations=}: ERROR_BUFFER_OVERFLOW")
            free(pAddresses)
            pAddresses = NULL
        else:
            print(f"Adapter addresses retrieved")
            break
        Iterations += 1

    print(f"Finished: {dwRetVal=}")

    if dwRetVal != NO_ERROR:
        free(pAddresses)
        if dwRetVal == ERROR_NO_DATA:
            raise OSError("No addresses were found for the requested parameters")
        else:
            raise OSError(f"Error trying to retrieve adapter addresses: {dwRetVal}")

    adapters = _parse_adapters(pAddresses)
    free(pAddresses)
    return adapters