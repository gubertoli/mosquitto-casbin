import sys
import subprocess
import time
import paho.mqtt.client as mqtt

BROKER_EXE = sys.argv[1]
CONF_FILE = sys.argv[2]

def main():
    print(f"--- Starting Broker: {BROKER_EXE} -c {CONF_FILE} ---")
    broker = subprocess.Popen(
        [BROKER_EXE, "-c", CONF_FILE],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    time.sleep(2)

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

if __name__ == "__main__":
    main()