from time import sleep
import os
import signal
import subprocess
import pytest

COMPONENT_FACTORY_FILE_PATH = "pipert/core/component_factory.py"
DUMMY_COMPONENT_CONFIG_PATH = 'tests/pipert/core/utils/dummy_component_config.yaml'
COMPONENT_PORT = "5050"


def test_bad_config_path():
    bad_config_path = 'tests/pipert/core/utils/bad_path.yaml'
    cmd = "python " + COMPONENT_FACTORY_FILE_PATH + " -cp " + bad_config_path + " -p " + COMPONENT_PORT
    print("1")
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    print("2")
    process_is_running = does_process_running(process)
    print("3")
    if process_is_running:
        print("4")
        kill_process(process)
        print("4.5")
        assert False
        # assert not process_is_running, "Expected to get an error"
    print("5")
    assert process.returncode


def test_no_port_sent():
    cmd = "python " + COMPONENT_FACTORY_FILE_PATH + " -cp " + DUMMY_COMPONENT_CONFIG_PATH
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    process_is_running = does_process_running(process)
    if process_is_running:
        kill_process(process)
        assert not process_is_running, "Expected to get an error"

    _, error = process.communicate()
    assert process.returncode
    assert error == "Must get port for the zeroRPC server in the script parameters"


def test_good_parameters():
    cmd = "python " + COMPONENT_FACTORY_FILE_PATH + " -cp " + DUMMY_COMPONENT_CONFIG_PATH + " -p " + COMPONENT_PORT
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    sleep(3)
    assert does_process_running(process)
    kill_process(process)


def does_process_running(process):
    return process.poll() is None


def kill_process(process):
    os.killpg(os.getpgid(process.pid), signal.SIGTERM)  # Send the signal to all the process groups
