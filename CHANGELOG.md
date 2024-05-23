# Changelog

## [Unreleased]

### Added
- Set RPDOMap values by byte string.
- Function to check if a configuration had been applied to the drive.

### Changed
- The signature of the load_firmware method of EthercatNetwork is changed to add the boot_in_app argument.

### Fixed
- Issue when connecting to the virtual drive using an EVE CANopen dictionary.

## [7.3.1] - 2024-05-10

### Fixed
- Bug that when the path to the FoE binary has blank spaces.
- The Interface attribute format in the configuration file.
- CANopen communication re-establishment after a power cycle.
- Exception when scanning drives using an IXXAT tranceiver.

## [7.3.0] - 2024-04-23

### Add
- Dictionary V3 support
- ILWrongWorkingCount exception raised when the working count in PDO is not the expected one.
- Register type for monitoring/disturbance data.
- Support for merging dictionary instances. (It can only be used for merging COM-KIT and CORE dictionaries.)
- Support to socketcan so the canopen communication can be used in Linux.
- Default value and description attributes to registers.
- Read/write functionalities for bit register type.
- Method to set the PDO watchdog time.
- FoE binary compiled for Linux machines.

### Changed
- Dictionary class properties, such as subnodes and interface.
- Add monitoring/disturbance registers to the dictionary if monitoring/disturbance is supported.
- Add PDO registers to the dictionary for EtherCAT drives.
- IXXAT missing DLLs logs are ignored.

### Fixed
- Bug that prevented the slaves to reach Operational state after the PDO exchange is re-started.
- Recover the CoE communication after a power-cycle. The network status listener must be turned on in order for it to work.

## [7.2.0] - 2024-03-13

### Add
- Motor enable and disable features in the virtual drive.
- Emulate control loops in the virtual drive.
- Support to Python 3.9 to 3.12.
- EtherCAT PDO module.
- Store and restore functionalities for subnode 0.
- Add functionalities to update ECAT state machine
- Add send_receive_processdata function
- Add scan_slaves_info method

### Fixed
- Raise exception when ECAT SDO write/read is wrong

### Deprecated
- Support to Python 3.6 to 3.8.

### Changed
- The PCAN transceiver bus is automatically reset when the bus-off state is reached.
- Emergency (EMCY) messages are discarded when using the CoE protocol.
- The enums are represented using dicts in the Register class.

## [7.1.1] - 2024-01-03

### Added
- Missing EtherCAT protocol documentation.

### Fixed
- Import Ingenialink does not raise an error if WinPcap is not installed, but ethercat features are disabled.

## [7.1.0] - 2023-11-28

### Add
- Support for multi-drive in CANopen's NetStatusListener.
- EtherCAT communication via CoE (SDOs).
- Add image attribute to dictionary class.
- Add EthercatDictionary class.
- Add EthercatRegister class.
- Create EtherCAT PDOs example script.

### Fixed
- Fix CANopen load_firmware function.
- Set product name correctly if no dictionary is provided.
- Docstrings from Register constructor and its subclasses are updated.
- CanopenRegister and EthernetRegister have the same signature.
- Add PySOEM to setup.py.
- Exception error when trying to write an int to a register of dtype float.
- Fix acquisition data variable initialization in Poller class.
- Unexpected closing when disconnecting from an EtherCAT (SDOs) drive if servo status listener is active.
- Avoid crashes in the Poller due to read timeouts.
- Poller timer thread not closing after the poller is finished.
- Improve the enable and disable methods of the Servo class.
- Unexpected VCIErrors.

### Changed
- Raise ILValueError when the disturbance data does not fit in a register.

### Deprecated 
- Support to Python 3.6 and 3.7.

## [7.0.4] - 2023-10-11

### Fixed
- Reread when ethernet read a wrong address
- Read strings until NULL character

## [7.0.3] - 2023-09-05

### Add
- Virtual drive.

### Changed
- convert_bytes_to_dtype raises an ILValueError string bytes are wrong
- Wait EoE starts before connect drive
- Remove EDS file path param from CANopen connection. It is no longer necessary.

### Fixed
- Catch EoE service deinit error when disconnecting the drive.
- Log exceptions in read_coco_moco_register function correctly.


## [7.0.2] - 2023-05-22
### Changed
- Read a register instead of doing a ping in the Ethernet's NetStatusListener
- Use inspect instead of pkg_resources to find the path to the FoE application.
- Call FoE application with utf-8 encoding.

### Fixed
- Capture all the ingenialink exceptions in servo status listener
- Truncate NACK error code to a int32

## [7.0.1] - 2023-04-04
### Fixed
- Recover old Monitoring/Disturbance compatibility
- Fix ServoStatusListener for multiaxis

## [7.0.0] - 2023-03-31
### Add
- Interface a Network class with SOEM service
- Add multi-slaves support to EoE service
- Implement stop EoE service feature
- Create mapped register property
- Create project toml file
- Use FoE application to load FW in windows

### Changed
- Update the load_FWs script to only use ingenialink.
- Improve the load_FWs script when using canopen protocol.

### Removed
- Remove numpy from requirements
- Remove binding to the [ingenialink](https://github.com/ingeniamc/ingenialink) C library.
- Move virtual drive from tests to ingenialink.

### Fixed
- NACK error code formatting.
- Fix pytest tests launch
- Wrong float range

## [6.5.1] - 2023-01-17
### Fixed
- Truncate received data in ethernet by the expected data length.
- Don't add PartNumber to the configuration file if it does not exist in the dictionary.
- CAN load firmware error if net_status_listener is disabled.

## [6.5.0] - 2023-01-04
### Added
- Tests are separated by communication protocol.
- Pull request template.

### Changed
- Re-organize the tests by protocol and add a no-connection mark to separate test that do not need a servo connected.
- Remove enums_count as an argument to create a Register.
- Convert enums type from list[dict] to dict.
- Ethernet communication is done using Python's standard library.
- Ethernet network now supports connection to multiple devices.
- Improved tests.
- Improved code formatting.
- Configuration file only stores registers that are stored in non-volatile memory and have access type RW.

### Deprecated 
- TCP support for ethernet devices.


## [6.4.0] - 2022-07-13
### Added
- Support monitoring/disturbance with CANopen protocol.
- Check for IP address validity in change_tcp_ip_parameters function.

### Changed
- On multiaxis drives the function load_configuration now allows to load the configuration of one axis into another.
- Set Ingenialink-C library log level to warning by default.
- Raise ILError on IPB monitoring/disturbance functions when an operation is not successful.

### Deprecated 
- monitoring_data function in ipb/servo use monitoring_channel_data instead.
- All serial protocol functions.