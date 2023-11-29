# Simple implementation of the OCPP - MQTT bridge

Enables to send mqtt commands (and receive mqtt messages as responses and status updates, though not implemented right now). I use this bridge for managing charge station from OpenHAB.

Send mqtt commands to /ocpp/cmd

Poetry is used to manage dependencies.

To start program:
poetry run python ./central_system.py

For automation needs I implemented these commands:
- start (start charging)
- stop
- trigger
- profile [arg] ( set charging profile, in my implementation argument is max current in Amps, message e.g. profile 8)
- configuration (read local CP configuration)
- change_configuration (set local CP configuration item)
- exit (stop bridge)


Note: check specific dependencies if implemented without poetry, as latest versions of some packages break functionalities.

Note: Every charge station may have peculiarities of OCPP implementation. The code is tested and fully works with:
- Elinta Charge https://elintacharge.com/product/private-ev-charging-station-homebox-slim/

# Dependencies and Contributions
OCPP implementation: https://github.com/mobilityhouse/ocpp 