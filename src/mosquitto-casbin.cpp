/*
 * Copyright 2026 Gustavo Bertoli
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

#include <casbin/casbin.h>
#include <openssl/x509.h>
#include <openssl/asn1.h>
// Mosquitto 2.1+ reorganised plugin headers under mosquitto/ and deprecated the
// flat mosquitto_broker.h (with a #warning that MSVC rejects as an error).
// mosquitto/broker.h is self-contained (pulls in mosquitto/defs.h for MOSQ_ERR_*
// and MOSQ_LOG_* constants). The 2.0.x flat headers are not self-contained so
// mosquitto.h must be included explicitly.
#if __has_include(<mosquitto/broker.h>)
#  include <mosquitto/broker.h>
#else
#  include <mosquitto.h>
#  include <mosquitto_broker.h>
#  include <mosquitto_plugin.h>
#endif
#include <memory>
#include <string>
#include <vector>
#include <stdexcept>

#ifdef WIN32
#  define PLUGIN_EXPORT __declspec(dllexport)
#else
#  define PLUGIN_EXPORT __attribute__((visibility("default")))
#endif

struct UserData {
    std::unique_ptr<casbin::Enforcer> enforcer;
    std::string model_path;
    std::string policy_path;
};

std::string get_action_string(int access) {
    switch (access) {
        case MOSQ_ACL_READ:
            return "read";
        case MOSQ_ACL_WRITE:
            return "write";
        case MOSQ_ACL_SUBSCRIBE:
            return "subscribe";
        default:
            return "unknown";
    }
}

// Helper to Extract CN from Cert
std::string extract_cn_from_cert(X509* cert) {
    if (!cert) return "";

    X509_NAME *subj_name = X509_get_subject_name(cert);
    if (!subj_name) return "";

    int nid = X509_NAME_get_index_by_NID(subj_name, NID_commonName, -1);
    if (nid == -1) return "";

    X509_NAME_ENTRY *entry = X509_NAME_get_entry(subj_name, nid);
    if (!entry) return "";

    ASN1_STRING *entry_data = X509_NAME_ENTRY_get_data(entry);
    if (!entry_data) return "";
    
    unsigned char *utf8 = nullptr;
    int len = ASN1_STRING_to_UTF8(&utf8, entry_data);
    
    std::string cn = "";
    if (len > 0 && utf8) {
        cn = std::string(reinterpret_cast<char*>(utf8), len);
        OPENSSL_free(utf8);
    }
    return cn;
}

/* * Callback: ACL Check
 * Event: MOSQ_EVT_ACL_CHECK
 */
int callback_acl_check([[maybe_unused]] int event, void *event_data, void *userdata) {
    auto *ud = static_cast<UserData*>(userdata);
    auto *ed = static_cast<struct mosquitto_evt_acl_check*>(event_data);

    // Casbin Subject ~ MQTT Client
    const char* client_username = mosquitto_client_username(ed->client);
    std::string sub = (client_username) ? client_username : "anonymous";
	
	X509* cert = (X509*)mosquitto_client_certificate(ed->client);
	if (cert) {
		if (sub == "anonymous") {
			std::string cert_cn = extract_cn_from_cert(cert);
			if (!cert_cn.empty()) {
				sub = cert_cn;
			}
		}
		X509_free(cert);
	}

    // Casbin Object ~ MQTT Topic
    std::string obj = (ed->topic) ? ed->topic : "";

    // Casbin Action ~ MQTT Access Type
    std::string act = get_action_string(ed->access);
    if (act == "unknown") {
        mosquitto_log_printf(MOSQ_LOG_WARNING, "mosquitto-casbin: unrecognized ACL action %d, denying.", ed->access);
        return MOSQ_ERR_ACL_DENIED;
    }

    // Casbin Request
    bool authorized = false;
    try {
        authorized = ud->enforcer->Enforce({ sub, obj, act });
    } catch (...) {
        mosquitto_log_printf(MOSQ_LOG_ERR, "mosquitto-casbin: Enforce threw an exception, denying.");
        return MOSQ_ERR_ACL_DENIED;
    }

    return authorized ? MOSQ_ERR_SUCCESS : MOSQ_ERR_ACL_DENIED;
}

extern "C" {

PLUGIN_EXPORT int mosquitto_plugin_version(int supported_version_count, const int *supported_versions) { //
    for (int i = 0; i < supported_version_count; i++) {
        if (supported_versions[i] == 5) {
            return 5;
        }
    }
    return -1;
}

PLUGIN_EXPORT int mosquitto_plugin_init(mosquitto_plugin_id_t *identifier, void **userdata, struct mosquitto_opt *opts, int opt_count) {
    auto *ud = new UserData();

    ud->model_path = "model.conf";
    ud->policy_path = "policy.csv";

    // Parse options from mosquitto.conf
    for (int i = 0; i < opt_count; i++) {
        std::string key(opts[i].key);
        std::string value(opts[i].value);

        if (key == "casbin_model") {
            ud->model_path = value;
        } else if (key == "casbin_policy") {
            ud->policy_path = value;
        }
    }

    try {
        ud->enforcer = std::make_unique<casbin::Enforcer>(ud->model_path, ud->policy_path);
        mosquitto_log_printf(MOSQ_LOG_INFO, "mosquitto-casbin: Enforcer initialized with %s", ud->model_path.c_str());
    } catch (const std::exception& e) {
        mosquitto_log_printf(MOSQ_LOG_ERR, "mosquitto-casbin: Failed to initialize Enforcer: %s", e.what());
        delete ud;
        return MOSQ_ERR_UNKNOWN;
    } catch (...) {
        mosquitto_log_printf(MOSQ_LOG_ERR, "mosquitto-casbin: Failed to initialize Enforcer");
        delete ud;
        return MOSQ_ERR_UNKNOWN;
    }

    int rc = mosquitto_callback_register(identifier, MOSQ_EVT_ACL_CHECK, callback_acl_check, NULL, ud);
    if (rc != MOSQ_ERR_SUCCESS) {
        delete ud;
        return rc;
    }

    *userdata = ud;
    return MOSQ_ERR_SUCCESS;
}

PLUGIN_EXPORT int mosquitto_plugin_cleanup(void *userdata, [[maybe_unused]] struct mosquitto_opt *opts, [[maybe_unused]] int opt_count) {
    delete static_cast<UserData*>(userdata);
    return MOSQ_ERR_SUCCESS;
}

}
