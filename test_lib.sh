coverage run -m pytest tests/                         # Test functions without communication
coverage run -a -m pytest tests/ --protocol canopen   # Test canopen functions
coverage run -a -m pytest tests/ --protocol ethernet  # Test ethernet functions
coverage run -a -m pytest tests/ --protocol ethercat  # Test ethercat functions
coverage report -m --include=ingenialink/*            # Prints the full coverage report