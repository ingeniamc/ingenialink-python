from GetAdaptersAddresses cimport *
from libc.stdlib cimport malloc, free
from libc.stdint cimport uint32_t
from typing import Optional
import dataclasses
import cython

_WORKING_BUFFER_SIZE = 15000

def get_adapters_addresses():
    cdef:
        unsigned long dwRetVal   = 0
        unsigned int i = 0
        unsigned long flags = GAA_FLAG_INCLUDE_PREFIX
        unsigned long family = AF_UNSPEC
        void* lpMsgBuf = NULL

        PIP_ADAPTER_ADDRESSES_LH pAddresses
        uint32_t outBufLen = 0
        uint32_t Iterations = 0

        PIP_ADAPTER_ADDRESSES_LH pCurrAddresses = NULL
        PIP_ADAPTER_UNICAST_ADDRESS_LH pUnicast = NULL
        PIP_ADAPTER_ANYCAST_ADDRESS_XP pAnycast = NULL
        PIP_ADAPTER_MULTICAST_ADDRESS_XP pMulticast = NULL
        IP_ADAPTER_DNS_SERVER_ADDRESS_XP *pDnServer = NULL
        IP_ADAPTER_PREFIX_XP* pPrefix = NULL


    outBufLen = _WORKING_BUFFER_SIZE