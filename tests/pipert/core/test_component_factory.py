from time import sleep
import os
import signal
import subprocess
import pytest

COMPONENT_FACTORY_FILE_PATH = "pipert/core/component_factory.py"
DUMMY_COMPONENT_CONFIG_PATH = 'tests/pipert/core/utils/dummy_component_config.yaml'
COMPONENT_PORT = "5050"


# def test_bad_config_path():
#     bad_config_path = 'tests/pipert/core/utils/bad_path.yaml'
#     cmd = "python " + COMPONENT_FACTORY_FILE_PATH + " -cp " + bad_config_path + " -p " + COMPONENT_PORT
#     process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
#     _, error = process.communicate()
#     if error != b'':
#         kill_process(process)
#         assert False, "Expected to get an error"
#     assert True


def test_no_port_sent(script_runner):
    ret = script_runner.run_subprocess(COMPONENT_FACTORY_FILE_PATH, " -cp " + DUMMY_COMPONENT_CONFIG_PATH)
    # cmd = "python " + COMPONENT_FACTORY_FILE_PATH + " -cp " + DUMMY_COMPONENT_CONFIG_PATH
    # process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    # _, error = process.communicate()
    # assert process.returncode
    # assert str(error) == b"Must get port for the zeroRPC server in the script parameters"
    print(ret.stderr)
    print(ret.stdout)
    print(ret.returncode)
    assert False


# def test_good_parameters():
#     cmd = "python " + COMPONENT_FACTORY_FILE_PATH + " -cp " + DUMMY_COMPONENT_CONFIG_PATH + " -p " + COMPONENT_PORT
#     process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
#     sleep(3)


def does_process_running(process):
    return process.poll() is None


def kill_process(process):
    # os.killpg(os.getpgid(process.pid), signal.SIGTERM)  # Send the signal to all the process groups
    # process.kill()
    os.kill(process.pid, signal.SIGKILL)
