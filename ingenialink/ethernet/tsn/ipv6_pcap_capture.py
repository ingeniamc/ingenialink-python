"""Windows-specific packet capture support for IPv6 discovery."""

from typing import Optional

try:
    import cypcap  # type: ignore[import-not-found, import-untyped, unused-ignore]
except ImportError as ex:
    cypcap = None
    cypcap_import_error = ex

MAX_PACKET_SIZE = 65_535
READ_TIMEOUT_S = 0.01


class PcapCapture:
    """Pcap packet capture for a single Windows network interface."""

    def __init__(self, interface: str) -> None:
        if not cypcap:
            raise cypcap_import_error
        self._capture = None
        try:
            self._capture = cypcap.create(interface)
            self._capture.set_snaplen(MAX_PACKET_SIZE)
            self._capture.set_promisc(False)
            self._capture.set_timeout(READ_TIMEOUT_S)
            self._capture.activate()
            if self._capture.datalink() != cypcap.DatalinkType.EN10MB:
                raise OSError("Pcap discovery requires an Ethernet interface.")
            self._capture.setfilter("ip6 or (vlan and ip6)")
        except cypcap.Error as error:
            self.close()
            raise OSError(f"Unable to configure pcap capture: {error}") from error
        except OSError:
            self.close()
            raise

    def __enter__(self) -> "PcapCapture":
        """Return the active capture for use in a context manager."""
        return self

    def __exit__(self, *args: object) -> None:
        """Close the capture when leaving its context manager."""
        self.close()

    def close(self) -> None:
        """Close the pcap capture handle once.

        Raises:
            OSError: If cypcap cannot close the capture.
        """
        if self._capture is not None:
            capture = self._capture
            self._capture = None
            try:
                capture.close()
            except cypcap.Error as error:
                raise OSError(f"Unable to close pcap capture: {error}") from error

    def read_packet(self) -> Optional[bytes]:
        """Read one packet, returning ``None`` when the capture times out.

        Returns:
            The captured packet bytes, or ``None`` on a read timeout.

        Raises:
            OSError: If the capture is closed or cannot read a packet.
        """
        if self._capture is None:
            raise OSError("Pcap capture handle is closed.")
        try:
            packet_header, packet_data = next(self._capture)
        except cypcap.Error as error:
            raise OSError(f"Unable to read pcap packet: {error}") from error
        except StopIteration as error:
            raise OSError("Pcap capture terminated unexpectedly.") from error
        if packet_header is None:
            return None
        return bytes(packet_data)
