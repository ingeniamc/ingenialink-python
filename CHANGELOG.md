# Changelog

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