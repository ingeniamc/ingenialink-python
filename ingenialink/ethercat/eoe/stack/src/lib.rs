//! Userspace UDP/IPv4 stack over Ethernet-over-EtherCAT (`EoE`) frames.
//!
//! Wraps [`smoltcp`] behind a small Python API: Python exchanges raw Ethernet
//! frames with this stack (tunneling them through the `EtherCAT` mailbox via
//! pysoem), while ARP, IPv4 and UDP are fully handled by smoltcp. No TAP device
//! or OS networking is involved.

use std::collections::{HashMap, VecDeque};

use pyo3::exceptions::{PyOSError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::PyBytes;
use smoltcp::iface::{Config, Interface, SocketHandle, SocketSet};
use smoltcp::phy::{Device, DeviceCapabilities, Medium, RxToken, TxToken};
use smoltcp::socket::udp;
use smoltcp::time::Instant;
use smoltcp::wire::{EthernetAddress, HardwareAddress, IpAddress, IpCidr, IpEndpoint, Ipv4Address};

/// Queue-backed smoltcp device fed by Python with raw `EoE` Ethernet frames.
#[derive(Default)]
struct EoeDevice {
    /// Frames received from the drive, pending processing by smoltcp.
    rx_queue: VecDeque<Vec<u8>>,
    /// Frames produced by smoltcp, pending transmission to the drive.
    tx_queue: VecDeque<Vec<u8>>,
}

/// Receive token handing one queued frame to smoltcp.
struct EoeRxToken(Vec<u8>);

/// Transmit token appending one frame to the transmit queue.
struct EoeTxToken<'a>(&'a mut VecDeque<Vec<u8>>);

impl RxToken for EoeRxToken {
    fn consume<R, F>(mut self, f: F) -> R
    where
        F: FnOnce(&mut [u8]) -> R,
    {
        f(&mut self.0)
    }
}

impl TxToken for EoeTxToken<'_> {
    fn consume<R, F>(self, len: usize, f: F) -> R
    where
        F: FnOnce(&mut [u8]) -> R,
    {
        let mut frame = vec![0u8; len];
        let result = f(&mut frame);
        self.0.push_back(frame);
        result
    }
}

impl Device for EoeDevice {
    type RxToken<'a> = EoeRxToken;
    type TxToken<'a> = EoeTxToken<'a>;

    fn receive(&mut self, _timestamp: Instant) -> Option<(Self::RxToken<'_>, Self::TxToken<'_>)> {
        let frame = self.rx_queue.pop_front()?;
        Some((EoeRxToken(frame), EoeTxToken(&mut self.tx_queue)))
    }

    fn transmit(&mut self, _timestamp: Instant) -> Option<Self::TxToken<'_>> {
        Some(EoeTxToken(&mut self.tx_queue))
    }

    fn capabilities(&self) -> DeviceCapabilities {
        let mut caps = DeviceCapabilities::default();
        caps.medium = Medium::Ethernet;
        caps.max_transmission_unit = 1500;
        caps
    }
}

/// Parse an `aa:bb:cc:dd:ee:ff` MAC address string.
///
/// # Errors
/// Returns a [`PyValueError`] if the string is not a valid MAC address.
fn parse_mac(mac: &str) -> PyResult<EthernetAddress> {
    let octets: Vec<u8> = mac
        .split(':')
        .map(|part| u8::from_str_radix(part, 16))
        .collect::<Result<_, _>>()
        .map_err(|_| PyValueError::new_err(format!("invalid MAC address: {mac}")))?;
    let octets: [u8; 6] = octets
        .try_into()
        .map_err(|_| PyValueError::new_err(format!("invalid MAC address: {mac}")))?;
    Ok(EthernetAddress(octets))
}

/// Parse a dotted-quad IPv4 address string.
///
/// # Errors
/// Returns a [`PyValueError`] if the string is not a valid IPv4 address.
fn parse_ipv4(ip: &str) -> PyResult<Ipv4Address> {
    let addr: std::net::Ipv4Addr = ip
        .parse()
        .map_err(|_| PyValueError::new_err(format!("invalid IPv4 address: {ip}")))?;
    Ok(Ipv4Address::from_bytes(&addr.octets()))
}

/// Userspace UDP/IPv4 stack bound to a single Ethernet interface over `EoE`.
///
/// Frames flow in through [`UdpStack::push_frame`] and out through
/// [`UdpStack::pop_frame`]; [`UdpStack::poll`] runs the smoltcp state machine
/// (ARP resolution and replies, IPv4 processing, UDP socket dispatch).
#[pyclass]
struct UdpStack {
    /// Queue-backed device exchanging frames with Python.
    device: EoeDevice,
    /// smoltcp network interface owning ARP/IPv4 processing.
    iface: Interface,
    /// Socket storage for all bound UDP sockets.
    sockets: SocketSet<'static>,
    /// Map of local UDP port to its socket handle.
    handles: HashMap<u16, SocketHandle>,
}

#[pymethods]
impl UdpStack {
    /// Create a stack with the given MAC address and IPv4 address/prefix.
    ///
    /// # Errors
    /// Returns a [`PyValueError`] if the MAC or IP address is invalid, or a
    /// [`PyOSError`] if the address cannot be assigned to the interface.
    #[new]
    fn new(mac: &str, ip: &str, prefix_len: u8) -> PyResult<Self> {
        let hw_addr = parse_mac(mac)?;
        let ip_addr = parse_ipv4(ip)?;
        let mut device = EoeDevice::default();
        let config = Config::new(HardwareAddress::Ethernet(hw_addr));
        let mut iface = Interface::new(config, &mut device, Instant::now());
        let mut push_ok = false;
        iface.update_ip_addrs(|addrs| {
            push_ok = addrs
                .push(IpCidr::new(IpAddress::Ipv4(ip_addr), prefix_len))
                .is_ok();
        });
        if !push_ok {
            return Err(PyOSError::new_err(format!(
                "failed to assign IP address {ip}/{prefix_len}"
            )));
        }
        Ok(Self {
            device,
            iface,
            sockets: SocketSet::new(Vec::new()),
            handles: HashMap::new(),
        })
    }

    /// Queue a raw Ethernet frame received from the drive over `EoE`.
    fn push_frame(&mut self, frame: &[u8]) {
        self.device.rx_queue.push_back(frame.to_vec());
    }

    /// Take the next Ethernet frame to be sent to the drive over `EoE`, if any.
    fn pop_frame<'py>(&mut self, py: Python<'py>) -> Option<Bound<'py, PyBytes>> {
        self.device
            .tx_queue
            .pop_front()
            .map(|frame| PyBytes::new(py, &frame))
    }

    /// Run the interface state machine, processing queued frames and sockets.
    ///
    /// Returns `True` if something was processed.
    fn poll(&mut self) -> bool {
        self.iface
            .poll(Instant::now(), &mut self.device, &mut self.sockets)
    }

    /// Bind a UDP socket on the given local port. Binding twice is a no-op.
    ///
    /// # Errors
    /// Returns a [`PyOSError`] if binding fails (e.g. port 0).
    fn bind(&mut self, port: u16) -> PyResult<()> {
        if self.handles.contains_key(&port) {
            return Ok(());
        }
        let rx_buffer =
            udp::PacketBuffer::new(vec![udp::PacketMetadata::EMPTY; 16], vec![0u8; 16384]);
        let tx_buffer =
            udp::PacketBuffer::new(vec![udp::PacketMetadata::EMPTY; 16], vec![0u8; 16384]);
        let mut socket = udp::Socket::new(rx_buffer, tx_buffer);
        socket.bind(port).map_err(|err| {
            PyOSError::new_err(format!("failed to bind UDP port {port}: {err:?}"))
        })?;
        self.handles.insert(port, self.sockets.add(socket));
        Ok(())
    }

    /// Send a UDP datagram from `src_port` to `dst_ip:dst_port`.
    ///
    /// The source socket is bound on demand. ARP resolution of the destination
    /// is handled transparently by subsequent [`UdpStack::poll`] calls.
    ///
    /// # Errors
    /// Returns a [`PyValueError`] for an invalid destination IP, or a
    /// [`PyOSError`] if the socket cannot be bound or its buffer is full.
    fn send(&mut self, src_port: u16, dst_ip: &str, dst_port: u16, payload: &[u8]) -> PyResult<()> {
        self.bind(src_port)?;
        let dst_addr = parse_ipv4(dst_ip)?;
        let endpoint = IpEndpoint::new(IpAddress::Ipv4(dst_addr), dst_port);
        let handle = *self
            .handles
            .get(&src_port)
            .ok_or_else(|| PyOSError::new_err(format!("UDP port {src_port} is not bound")))?;
        let socket = self.sockets.get_mut::<udp::Socket>(handle);
        socket
            .send_slice(payload, endpoint)
            .map_err(|err| PyOSError::new_err(format!("UDP send failed: {err:?}")))
    }

    /// Receive a pending UDP datagram on the socket bound to `port`, if any.
    ///
    /// Returns a `(payload, source_ip, source_port)` tuple, or `None` if the
    /// port is not bound or no datagram is pending.
    fn recv<'py>(
        &mut self,
        py: Python<'py>,
        port: u16,
    ) -> Option<(Bound<'py, PyBytes>, String, u16)> {
        let handle = *self.handles.get(&port)?;
        let socket = self.sockets.get_mut::<udp::Socket>(handle);
        let mut buffer = [0u8; 2048];
        let (size, metadata) = socket.recv_slice(&mut buffer).ok()?;
        Some((
            PyBytes::new(py, &buffer[..size]),
            metadata.endpoint.addr.to_string(),
            metadata.endpoint.port,
        ))
    }
}

/// Python module exposing the [`UdpStack`] class.
#[pymodule]
fn eoe_stack(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_class::<UdpStack>()?;
    Ok(())
}
