from GetAdaptersAddresses cimport *
from libc.stdlib cimport malloc, free
from typing import Optional
import dataclasses
import cython

def get_adapters_addresses():
    cdef:
        unsigned long dw_ret_val  = 0
        unsigned int i = 0
        unsigned long flags = GAA_FLAG_INCLUDE_PREFIX
        unsigned long family = AF_UNSPEC
        # unsigned long out_buf_len = sizeof(IP_ADAPTER_INFO)
        # IP_ADAPTER_INFO* adapter_info = <IP_ADAPTER_INFO*> malloc(sizeof(IP_ADAPTER_INFO))

