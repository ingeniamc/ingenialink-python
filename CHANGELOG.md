# Changelog

## [Unreleased] 
### Changed
- Read a register instead of doing a ping in the Ethernet's NetStatusListener
- Use inspect instead of pkg_resources to find the path to the FoE application.


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