import argparse
import yaml
from pipert.utils.useful_methods import open_config_file


def prometheus_handler(pods):
    # 1. add the monitoring system and the port for each one of the components to listen
    # 2. and add the services in the docker compose and generate the prometheus yaml

    global docker_compose_dictionary
    docker_compose_dictionary["services"]["prometheus"] = {
        "container_name": "prometheus",
        "image": "prom/prometheus:latest",
        "logging": {
            "driver": "none"
        },
        "networks": {
            "default": {
                "aliases": [
                    "prometheus"
                ]
            }
        },
        "restart": "always",
        "volumes": [
            "./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml"
        ],
        "ports": [
            "9090:9090"
        ]
    }

    docker_compose_dictionary["services"]["grafana"] = {
        "container_name": "grafana",
        "image": "grafana/grafana:latest",
        "logging": {
            "driver": "none"
        },
        "networks": {
            "default": {
                "aliases": [
                    "grafana"
                ]
            }
        },
        "restart": "always",
        "volumes": [
            "./monitoring/provisioning/dashboards:/etc/grafana/provisioning/dashboards",
            "./monitoring/provisioning/datasources:/etc/grafana/provisioning/datasources",
            "./monitoring/dashboards:/var/lib/grafana/dashboards",
            "grafana_data:/var/lib/grafana"
        ],
        "environment": {
            "GF_INSTALL_PLUGINS": "grafana-piechart-panel"
        },
        "ports": [
            "3000:3000"
        ]
    }

    if "volumes" not in docker_compose_dictionary:
        docker_compose_dictionary["volumes"] = {}
    docker_compose_dictionary["volumes"]["grafana_data"] = {}

    prometheus_dictionary = \
        {
            "global": {
                "scrape_interval": "5s",
                "evaluation_interval": "15s"
            },
            "scrape_configs": [
                {
                    "job_name": "prometheus",
                    "static_configs": [
                        {
                            "targets": [
                                "localhost:9090"
                            ]
                        }
                    ]
                },
                {
                    "job_name": "pipert",
                    "static_configs": []
                }
            ]
        }

    prometheus_port_counter = 30000

    for _, curr_pod_comps in pods.items():
        for component_name, component_params in curr_pod_comps["components"].items():
            component_params["monitoring_system"] = \
                {
                    "name": "Prometheus",
                    "port": prometheus_port_counter
                }
            prometheus_dictionary["scrape_configs"][1]["static_configs"].append(
                {
                    "targets": [
                        "pipert:" + str(prometheus_port_counter)
                    ],
                    "labels": {
                        "service_name": component_name
                    }
                }
            )
            prometheus_port_counter += 1

    with open("monitoring/prometheus.yml", 'w') as prometheus_config:
        yaml.dump(prometheus_dictionary, prometheus_config)
        print("Created prometheus.yaml config")


def add_ports_if_needed(pod_dict, components):
    # Add to the services ports if they expose flask server
    for component in components.values():
        if ("component_type_name" in component) and ("flask" in component["component_type_name"].lower()):
            port = str(component["component_args"]["port"])
            pod_dict["ports"].append(port + ":" + port)


def get_config_file():
    parser = argparse.ArgumentParser()
    parser.add_argument('-cp', '--config_path', help='Configuration file path',
                        type=str, default='pipert/utils/config_files/config.yaml')
    opts, unknown = parser.parse_known_args()
    config_file = open_config_file(opts.config_path)
    if isinstance(config_file, str):
        exit(config_file)
    return config_file


def create_config_file_for_pod(pod_configuration, pod_name):
    global GENERATED_CONFIG_FILES_FOLDER
    pod_config_path = GENERATED_CONFIG_FILES_FOLDER + pod_name + ".yaml"
    with open(pod_config_path, 'w') as pod_config_file:
        yaml.dump(pod_configuration, pod_config_file)
        print("Created config file for pod " + pod_name)
    return pod_config_path


def create_pod(pod_template, pod_name, pod_config):
    # 1. Create the pod config file
    # 2. Add the pod to the docker compose

    global docker_compose_dictionary

    pod_config_path = create_config_file_for_pod(pod_configuration=pod_config,
                                                 pod_name=pod_name)

    pod_template["container_name"] = pod_name
    pod_template["environment"]["CONFIG_PATH"] = pod_config_path

    add_ports_if_needed(pod_template, pod_config["components"])

    # static ip of container
    if "ip" in pod_config:
        pod_template["networks"]["static-network"] = {}
        pod_template["networks"]["static-network"]["ipv4_address"] = pod_config["ip"]

        if len(docker_compose_dictionary["networks"]["static-network"]["ipam"]["config"]) == 0:
            docker_compose_dictionary["networks"]["static-network"]["ipam"]["config"].append(
                {
                    "subnet": pod_config["ip"].rsplit(".", 1)[0] + ".0/16"
                }
            )

    docker_compose_dictionary["services"][pod_name] = pod_template

    return pod_name


def dockerfile_name_handler(config_dict):
    global docker_compose_dictionary

    dockerfile_name = config_dict.get("dockerfile", "Dockerfile")
    docker_compose_dictionary["services"]["base-pipert"]["build"]["dockerfile"] = dockerfile_name


def monitoring_system_handler(config_dict):
    monitoring_system = config_dict.get("monitoring_system", "no_monitor")
    if monitoring_system.lower() == "prometheus":
        prometheus_handler(pods=config_dict["pods"])


if __name__ == "__main__":
    flask_port_counter = 5000

    GENERATED_CONFIG_FILES_FOLDER = "pipert/utils/config_files/"

    docker_compose_dictionary = {
        "version": "3.7",
        "services": {
            "redis": {
                "container_name": "redis",
                "image": "redis:5.0.7-buster",
                "logging": {
                    "driver": "none"
                },
                "networks": {
                    "default": {
                        "aliases": [
                            "redis"
                        ]
                    }
                },
                "restart": "always",
                "ports": [
                    "6379:6379"
                ]
            },
            "base-pipert": {
                "container_name": "base-pipert",
                "logging": {
                    "driver": "none"
                },
                "ipc": "host",
                "build": {
                    "context": "pipe-base/.",
                    "dockerfile": "Dockerfile"
                },
                "networks": {
                    "default": {
                        "aliases": [
                            "base-pipert"
                        ]
                    }
                }
            }
        },
        "networks": {
            "static-network": {
                "ipam": {
                    "config": [

                    ]
                }
            }
        }
    }

    config_file = get_config_file()

    monitoring_system_handler(config_dict=config_file)

    dockerfile_name_handler(config_dict=config_file)

    # Create the first pod
    pipeline_first_pod = {
        "container_name": "",
        "image": "pipert_pipert",
        "build": {
            "context": ".",
            "args": {
                "SPLUNK": "no",
                "DETECTRON": "no",
                "TORCHVISION": 'no'
            }
        },
        "ipc": "host",
        "networks": {
            "default": {
                "aliases": [
                    "pipert"
                ]
            }
        },
        "depends_on": [
            "redis",
            "base-pipert"
        ],
        "environment": {
            "REDIS_URL": "redis://redis:6379/0",
            "UI": "${UI:-false}",
            "UI_PORT": "${UI_PORT:-5005}",
            "CLI_ENDPOINT": "${CLI_ENDPOINT:-4001}",
            "CONFIG_PATH": ""
        },
        "ports": []
    }
    first_pod_name, first_pod_config = config_file["pods"].popitem()
    first_pod_name = create_pod(pod_template=pipeline_first_pod,
                                pod_name=first_pod_name,
                                pod_config=first_pod_config)

    PIPELINE_OTHER_PODS_TEMPLATE = {
        "container_name": "",
        "image": "pipert_pipert",
        "networks": {
            "default": {
                "aliases": [
                    "pipert"
                ]
            }
        },
        "ipc": "host",
        "depends_on": [first_pod_name],
        "environment": {
            "REDIS_URL": "redis://redis:6379/0",
            "UI": "${UI:-false}",
            "UI_PORT": "${UI_PORT:-5005}",
            "CLI_ENDPOINT": "${CLI_ENDPOINT:-4001}",
            "CONFIG_PATH": ""
        },
        "ports": []
    }

    # Create all other pods
    for pod_name, pod_config in config_file["pods"].items():
        create_pod(pod_template=PIPELINE_OTHER_PODS_TEMPLATE.copy(),
                   pod_name=pod_name,
                   pod_config=pod_config)

    # write the docker compose file
    with open("docker-compose.yaml", 'w') as generated_compose:
        yaml.dump(docker_compose_dictionary, generated_compose)
        print("Generated the docker compose")
