# Mosquitto Casbin Access Control Plugin

[![CI Status](https://github.com/gubertoli/mosquitto-casbin/actions/workflows/cmake-multi-platform.yml/badge.svg?branch=main)](https://github.com/gubertoli/mosquitto-casbin/actions/workflows/cmake-multi-platform.yml)

A flexible authorization plugin for the [Mosquitto MQTT Broker](https://mosquitto.org/) (v2.0+) that delegates access control decisions to [Casbin](https://casbin.org/).

This plugin implements the **Mosquitto Plugin Interface v5**. It is designed to be **authentication-agnostic**, meaning it focuses solely on Authorization and can work alongside password files, TLS certificate authentication, or anonymous access.

## Features

* **Granular Access Control**: Manage permissions using Casbin's powerful policy engine (ACL, RBAC, ABAC).
* **Authentication Agnostic**: Automatically resolves the user identity from:
    1.  MQTT Username (password authentication, or TLS with `use_identity_as_username` configured)
    2.  TLS Certificate Common Name (CN) — only when no MQTT username is provided
    3.  Fallback to `"anonymous"`


## Security Behavior

When a policy evaluation error occurs (e.g., malformed policy file or internal Casbin exception), the plugin **denies access by default** (fail-closed). Access is also denied for any ACL action type not recognised by the plugin. The plugin never falls back to another plugin or grants access on error.

## Dependencies

To build this plugin, you need a C++17 compatible compiler and the following:

* **CMake** (>= 3.19)
* **Mosquitto** — broker plugin headers: `mosquitto-dev` on Debian/Ubuntu, or the headers from a Mosquitto source build / Windows installer
* **OpenSSL**

In a Debian/Ubuntu environment:
```bash
sudo apt install mosquitto mosquitto-dev libssl-dev cmake build-essential
```

### Build
```bash
cmake -B build
cmake --build build
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
