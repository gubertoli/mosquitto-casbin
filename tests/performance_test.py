import sys
import subprocess
import time
import os
import paho.mqtt.client as mqtt

BROKER_EXE = sys.argv[1]
PLUGIN_CONFIG = sys.argv[2]
MSG_COUNT = 10000 
PORT_PLUGIN = 18885
PORT_BASE = 18886

def run_benchmark(config_file, port, label):
    broker = None
    try:
        base_config = "mosquitto_baseline.conf"
        if label == "Baseline":
            with open(base_config, "w") as f:
                f.write(f"listener {port}\nallow_anonymous true\n")
            config_to_use = base_config
        else:
            config_to_use = config_file

        broker = subprocess.Popen(
            [BROKER_EXE, "-c", config_to_use],
            stdout=subprocess.DEVNULL
        )
        time.sleep(1.5)

        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, protocol=mqtt.MQTTv5)
        client.connect("localhost", port)

        client.loop_start()
        
        start_time = time.time()
        for i in range(MSG_COUNT):
            client.publish("perf/test", "payload", qos=1)
        
        while client._out_messages:
            time.sleep(0.01)

        end_time = time.time()
        
        client.loop_stop()

        duration = end_time - start_time
        mps = MSG_COUNT / duration
        return mps
    
    except Exception as e:
        print(f"\n[FAIL] Test Failed: {e}")
        broker.terminate()
        sys.exit(1)

    finally:
        if broker is not None and broker.poll() is None:
            print("Shutting down the Mosquitto broker...")
            broker.terminate()
            try:
                broker.wait(timeout=5)
                print("Broker shut down cleanly.")
            except subprocess.TimeoutExpired:
                broker.kill()
                broker.wait()
        
        if label == "Baseline" and os.path.exists("mosquitto_baseline.conf"):
            os.remove("mosquitto_baseline.conf")

if __name__ == "__main__":
    print(f"--- Benchmarking {MSG_COUNT} Messages (QoS 1) ---")
    
    base_mps = run_benchmark(None, PORT_BASE, "Baseline")
    print(f"Baseline (No Plugin): {base_mps:.2f} msg/s")
    
    plugin_mps = run_benchmark(PLUGIN_CONFIG, PORT_PLUGIN, "With Plugin")
    print(f"With Casbin Plugin:   {plugin_mps:.2f} msg/s")
    
    overhead = ((base_mps - plugin_mps) / base_mps) * 100
    print(f"Performance Impact:   {overhead:.2f}% overhead")