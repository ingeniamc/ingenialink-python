import pytest

from ingenialink.ethernet.tsn.ipv6_pcap_capture import PcapCapture


@pytest.mark.pcap
def test_pcap_capture_applies_ipv6_filter(mocker):
    """Configure an Ethernet capture with the IPv6 and VLAN filter."""
    capture = mocker.MagicMock()
    capture.datalink.return_value = 1
    cypcap = mocker.MagicMock()
    cypcap.create.return_value = capture
    cypcap.DatalinkType.EN10MB = 1
    mocker.patch("ingenialink.ethernet.tsn.ipv6_pcap_capture.cypcap", cypcap)

    pcap_capture = PcapCapture(r"\Device\NPF_{DEADC0FF-EEEE-4444-8888-2BF6900CBFA0}")

    cypcap.create.assert_called_once_with(r"\Device\NPF_{DEADC0FF-EEEE-4444-8888-2BF6900CBFA0}")
    capture.set_snaplen.assert_called_once_with(65_535)
    capture.set_promisc.assert_called_once_with(False)
    capture.set_timeout.assert_called_once_with(0.01)
    capture.activate.assert_called_once_with()
    capture.setfilter.assert_called_once_with(
        "ip6 or (vlan and ip6)", netmask=cypcap.NETMASK_UNKNOWN
    )
    pcap_capture.close()


@pytest.mark.pcap
def test_pcap_capture_converts_library_errors(mocker):
    """Convert cypcap configuration errors into OS errors."""
    cypcap = mocker.MagicMock()
    cypcap.Error = RuntimeError
    cypcap.create.side_effect = RuntimeError("unable to open capture")
    mocker.patch("ingenialink.ethernet.tsn.ipv6_pcap_capture.cypcap", cypcap)

    with pytest.raises(OSError, match="unable to open capture"):
        PcapCapture("Ethernet")


@pytest.mark.pcap
def test_pcap_capture_defers_missing_npcap_error(mocker):
    """Raise the stored import error only when pcap capture is used."""
    import_error = ImportError("Failed to load Npcap")
    mocker.patch("ingenialink.ethernet.tsn.ipv6_pcap_capture.cypcap", None)
    mocker.patch(
        "ingenialink.ethernet.tsn.ipv6_pcap_capture.cypcap_import_error",
        import_error,
        create=True,
    )

    with pytest.raises(ImportError, match="Failed to load Npcap"):
        PcapCapture("Ethernet")


@pytest.mark.pcap
def test_pcap_capture_reports_unexpected_termination(mocker):
    """Convert pcap's termination status into a descriptive OS error."""
    capture = PcapCapture.__new__(PcapCapture)
    capture._capture = mocker.MagicMock()
    capture._capture.__next__.side_effect = StopIteration
    cypcap = mocker.MagicMock()
    cypcap.Error = RuntimeError
    mocker.patch("ingenialink.ethernet.tsn.ipv6_pcap_capture.cypcap", cypcap)

    with pytest.raises(OSError, match="terminated unexpectedly"):
        capture.read_packet()


@pytest.mark.pcap
def test_pcap_capture_reports_read_errors(mocker):
    """Expose the error returned by pcap when packet capture fails."""
    capture = PcapCapture.__new__(PcapCapture)
    capture._capture = mocker.MagicMock()
    capture._capture.__next__.side_effect = RuntimeError("read failure")
    cypcap = mocker.MagicMock()
    cypcap.Error = RuntimeError
    mocker.patch("ingenialink.ethernet.tsn.ipv6_pcap_capture.cypcap", cypcap)

    with pytest.raises(OSError, match="read failure"):
        capture.read_packet()


@pytest.mark.pcap
def test_pcap_capture_close_is_idempotent(mocker):
    """Close an active pcap handle no more than once."""
    capture = PcapCapture.__new__(PcapCapture)
    pcap = mocker.Mock()
    capture._capture = pcap
    cypcap = mocker.MagicMock()
    cypcap.Error = RuntimeError
    mocker.patch("ingenialink.ethernet.tsn.ipv6_pcap_capture.cypcap", cypcap)

    capture.close()
    capture.close()

    pcap.close.assert_called_once_with()
