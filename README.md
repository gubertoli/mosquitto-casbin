# Mosquitto Casbin Access Control Plugin

[![CI Status](https://github.com/gubertoli/mosquitto-casbin/actions/workflows/cmake-multi-platform.yml/badge.svg?branch=main)](https://github.com/gubertoli/mosquitto-casbin/actions/workflows/cmake-multi-platform.yml)

A flexible authorization plugin for the [Mosquitto MQTT Broker](https://mosquitto.org/) (v2.0+) that delegates access control decisions to [Casbin](https://casbin.org/).

This plugin implements the **Mosquitto Plugin Interface v5**. It is designed to be **authentication-agnostic**, meaning it focuses solely on Authorization and can work alongside password files, TLS certificate authentication, or anonymous access.

## Features

* **Granular Access Control**: Manage permissions using Casbin's powerful policy engine (ACL, RBAC, ABAC).
* **Authentication Agnostic**: Automatically resolves the user identity from:
    1.  MQTT Username (Password auth or TLS `use_identity_as_username`)
    2.  TLS Certificate Common Name (CN) (if no username is present)
    3.  Fallback to "anonymous"


## Dependencies

To build this plugin, you need a C++17 compatible compiler and the following:

* **CMake** (>= 3.19)
* **Mosquitto** (Development headers for v2.0+)
* **OpenSSL**

### Build
```bash
mkdir build && cd build
cmake ..
make
```

This will produce the shared library file: `mosquitto-casbin.so`.

## Configuration

1. Configure Mosquitto (`mosquitto.conf`)
Add the following lines to your `mosquitto.conf` to load the plugin and point it to your Casbin files.

```
# Load the plugin
plugin /path/to/build/mosquitto-casbin.so

# Path to the Casbin Model definition
auth_opt_casbin_model  /etc/mosquitto/casbin/model.conf

# Path to the Casbin Policy file
auth_opt_casbin_policy /etc/mosquitto/casbin/policy.csv
```

2. Configure Casbin
The plugin maps MQTT events to a Casbin Request tuple `(sub, obj, act)` as follows:

`sub` (Subject): The Client Identity (Username, Cert CN, or "anonymous").

`obj` (Object): The MQTT Topic (e.g., `sensors/temp`).

`act` (Action): The operation type: `read`, `write`, or `subscribe`.

## References
- [mosquitto-auth-plug reference design](https://github.com/jpmens/mosquitto-auth-plug/)
- [Mosquitto Plugin API](https://mosquitto.org/api/files/mosquitto_plugin-h.html)
- [Casbin-CPP Repository](https://github.com/casbin/casbin-cpp)