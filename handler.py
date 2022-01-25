import os
import re
import json
import subprocess
import logging
import urllib.request
import requests
from requests.exceptions import Timeout

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

soracom_auth_key_id = os.getenv('SORACOM_AUTH_KEY_ID')
soracom_auth_key = os.getenv('SORACOM_AUTH_KEY')
soracom_imsi = os.getenv('IMSI')
slack_url = os.getenv('SLACK_URL')

# SORACOM API
soracom_common_arg = ' --auth-key-id ' + \
    soracom_auth_key_id + ' --auth-key ' + soracom_auth_key


def create_url():
    # You can use another port for monitoring (up to device configuration)
    soracom_cli_create_port_mapping = "soracom port-mappings create --body '{\"destination\": {\"imsi\": \"" + \
        soracom_imsi + "\", \"port\": 80}, \"duration\": 30, \"tlsRequired\": true}'" + \
        soracom_common_arg
    port_mapping_info = json.loads((subprocess.run(
        soracom_cli_create_port_mapping, shell=True, stdout=subprocess.PIPE)).stdout.decode())
    url = "https://" + \
        port_mapping_info["hostname"] + ":" + \
        str(port_mapping_info["port"]) + \
        "/"  # You can add your custom path here
    logger.info("Created port mapping.")
    return url


def delete_port_mapping(url):
    # url = https://xx-xx-xx-xx.napter.soracom.io:xxxxx/
    ip_address = re.split(r'[/\.]', url)[2].replace('-', '.')
    port = re.split(r'[:/]', url)[4]

    soracom_cli_delete_port_mapping = "soracom port-mappings delete --ip-address " + \
        ip_address + " --port " + port + soracom_common_arg
    subprocess.run(
        soracom_cli_delete_port_mapping, shell=True, stdout=subprocess.PIPE)
    logger.info("Deleted port mapping.")
    return


def http_monitoring(url):
    try:
        res = requests.get(url, timeout=(3.0, 7.5))
        res.raise_for_status()
    except Timeout:
        return
    except requests.exceptions.RequestException:
        return
    status_code = res.status_code
    return status_code


def send_alert_to_slack(message):
    # NOTE: If you don't need to send alert to Slack, you can modify this function.
    message = "HTTP monitoring to IMSI " + \
        soracom_imsi + " got error: " + str(message)
    send_data = {
        "text": message,
    }
    send_text = json.dumps(send_data)
    request = urllib.request.Request(
        slack_url,
        data=send_text.encode('utf-8'),
        method="POST"
    )
    with urllib.request.urlopen(request) as response:
        response_body = response.read().decode('utf-8')
        logger.info(response_body)


def lambda_handler(event, context):
    url = create_url()
    http_monitoring_result = http_monitoring(url)

    if http_monitoring_result is None:
        send_alert_to_slack("No response to HTTP request")
    elif http_monitoring_result != 200:
        send_alert_to_slack("status code is " + str(http_monitoring_result))
    else:
        logger.info("HTTP Monitoring success.")

    delete_port_mapping(url)

    return


# if __name__ == '__main__':
#     lambda_handler("foo", "bar")
