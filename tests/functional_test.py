import sys
import subprocess
import socket
import tempfile
import os
import time
import paho.mqtt.client as mqtt

BROKER_EXE = sys.argv[1]
CONF_FILE = sys.argv[2]

def wait_for_broker(host, port, timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return
        except OSError:
            time.sleep(0.1)
    raise TimeoutError(f"Broker did not start on {host}:{port} within {timeout}s")

def main():
    print(f"--- Starting Broker: {BROKER_EXE} -c {CONF_FILE} ---")
    broker = subprocess.Popen(
        [BROKER_EXE, "-c", CONF_FILE],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    wait_for_broker("localhost", 18885)

    received_messages = []

    def on_message(client, userdata, msg):
        received_messages.append(msg.topic)

    try:
        c_bob = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, protocol=mqtt.MQTTv5)
        c_bob.username_pw_set("bob", "password")
        c_bob.on_message = on_message
        c_bob.connect("localhost", 18885)
        c_bob.loop_start()
        c_bob.subscribe("#", qos=1) # Subscribe to all topics

        c_alice = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, protocol=mqtt.MQTTv5)
        c_alice.username_pw_set("alice", "password")
        c_alice.connect("localhost", 18885)
        c_alice.loop_start()

        time.sleep(1)

        # ==========================================
        # TEST 1: Alice Good Write
        # ==========================================
        c_alice.publish("data/alice", "hello", qos=1).wait_for_publish()
        time.sleep(0.5)
        if "data/alice" not in received_messages:
            raise Exception("Alice failed to write to data/alice!")
        print("[PASS] Alice wrote to data/alice")

        # ==========================================
        # TEST 2: Alice Bad Write (Should be blocked)
        # ==========================================
        c_alice.publish("data/bob", "hacking", qos=1).wait_for_publish()
        time.sleep(0.5) 
        if "data/bob" in received_messages:
            raise Exception("Casbin failed to block Alice! She wrote to data/bob.")
        print("[PASS] Alice was denied writing to data/bob")

        # ==========================================
        # TEST 3: Bob Admin Write
        # ==========================================
        c_bob.publish("system/critical", "admin_override", qos=1).wait_for_publish()
        time.sleep(0.5)
        if "system/critical" not in received_messages:
            raise Exception("Bob failed to write as admin to system/critical!")
        print("[PASS] Bob wrote to system/critical using admin role")

        # ==========================================
        # TEST 4: Alice Subscribe Denial
        # ==========================================
        alice_received = []
        c_alice.on_message = lambda c, u, m: alice_received.append(m.topic)
        c_alice.subscribe("data/bob", qos=1)
        time.sleep(0.5)
        # Bob publishes to data/bob; Alice should not receive it because her
        # subscription to data/bob was denied by the Casbin policy.
        c_bob.publish("data/bob", "secret", qos=1).wait_for_publish()
        time.sleep(0.5)
        if "data/bob" in alice_received:
            raise Exception("Alice received data/bob after her subscribe should have been denied!")
        print("[PASS] Alice was denied subscribing to data/bob")

        c_alice.loop_stop()
        c_bob.loop_stop()
        c_alice.disconnect()
        c_bob.disconnect()

    except Exception as e:
        print(f"\n[FAIL] Test Failed: {e}")
        sys.exit(1)

    finally:
        if broker is not None and broker.poll() is None:
            print("Shutting down the Mosquitto broker...")
            broker.terminate()
            try:
                broker.wait(timeout=5)
                print("Broker shut down cleanly.")
            except subprocess.TimeoutExpired:
                print("Forcing kill...")
                broker.kill()
                broker.wait()

def test_init_failure_is_fail_closed(broker_exe, valid_conf_file):
    # Parse plugin path from the working conf so we can reuse it.
    plugin_path = None
    for line in open(valid_conf_file):
        if line.startswith("plugin "):
            plugin_path = line.split(None, 1)[1].strip()
            break
    if not plugin_path:
        raise Exception("Could not parse plugin path from conf file")

    # A syntactically broken model forces the Casbin Enforcer constructor to
    # throw, triggering mosquitto_plugin_init → MOSQ_ERR_UNKNOWN → broker exit.
    broken_model = tempfile.NamedTemporaryFile(
        mode="w", suffix=".conf", delete=False
    )
    broken_model.write("[request_definition]\nr = sub, obj, act\n\nTHIS IS GARBAGE\n")
    broken_model.flush()

    tmp_conf = tempfile.NamedTemporaryFile(mode="w", suffix=".conf", delete=False)
    tmp_conf.write(f"listener 18887\nallow_anonymous true\npersistence false\n")
    tmp_conf.write(f"plugin {plugin_path}\n")
    tmp_conf.write(f"auth_opt_casbin_model  {broken_model.name}\n")
    tmp_conf.write(f"auth_opt_casbin_policy /tmp/policy_placeholder.csv\n")
    tmp_conf.flush()

    broker = None
    try:
        broker = subprocess.Popen(
            [broker_exe, "-c", tmp_conf.name],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        # Broker should exit within 3 s; poll until it does.
        deadline = time.time() + 3.0
        while time.time() < deadline and broker.poll() is None:
            time.sleep(0.1)

        if broker.poll() is None:
            raise Exception(
                "Broker stayed alive despite broken plugin config — plugin is NOT fail-closed on init failure!"
            )
        if broker.returncode == 0:
            raise Exception(
                f"Broker exited cleanly (rc=0) instead of with an error code — unexpected."
            )
        print(f"[PASS] Broker refused to start with broken plugin config (rc={broker.returncode}, fail-closed)")
    finally:
        if broker is not None and broker.poll() is None:
            broker.terminate()
            broker.wait(timeout=5)
        for f in (broken_model, tmp_conf):
            f.close()
            try:
                os.unlink(f.name)
            except OSError:
                pass


if __name__ == "__main__":
    main()
    test_init_failure_is_fail_closed(BROKER_EXE, CONF_FILE)
    print("--- All tests passed ---")