import argparse
import time
import uuid
from kubernetes import client, config, watch
from kubernetes.client.rest import ApiException

def get_args():
    parser = argparse.ArgumentParser(description='Check node versions via KubeAPI')
    parser.add_argument('--api-url', help='Kubernetes API URL', required=False)
    parser.add_argument('--token', help='Kubernetes API Token', required=False)
    parser.add_argument('--kubeconfig', help='Path to kubeconfig file', required=False)
    return parser.parse_args()

def setup_k8s_client(args):
    # Suppress InsecureRequestWarning
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    if args.api_url and args.token:
        configuration = client.Configuration()
        configuration.host = args.api_url
        configuration.verify_ssl = False
        configuration.api_key = {"authorization": "Bearer " + args.token}
        client.Configuration.set_default(configuration)
    elif args.kubeconfig:
        config.load_kube_config(config_file=args.kubeconfig)
    else:
        try:
            config.load_kube_config()
        except:
            print("Could not load kubeconfig. Please provide --api-url and --token or --kubeconfig.")
            exit(1)

def create_daemonset(api_instance, namespace, name):
    # Script to run on the host
    # We use nsenter or chroot. Since we mount /host, chroot is easier.
    # We check for crio, criu, runc.
    
    cmd = """
    chroot /host /bin/sh -c '
        echo "NODE_NAME: $HOSTNAME"
        
        echo -n "CRIO_VERSION: "
        if command -v crio >/dev/null 2>&1; then
            crio --version | head -n 1
        else
            echo "NOT_FOUND"
        fi
        
        echo -n "CRIU_INSTALLED: "
        if command -v criu >/dev/null 2>&1; then
            echo "YES"
        else
            echo "NO"
        fi
        
        echo -n "RUNC_VERSION: "
        if command -v runc >/dev/null 2>&1; then
            runc --version | head -n 1
        else
            echo "NOT_FOUND"
        fi
    '
    """

    container = client.V1Container(
        name="node-checker",
        image="registry.access.redhat.com/ubi9/ubi:latest",
        command=["/bin/sh", "-c", cmd + " && sleep 3600"], # Sleep to keep pod running so we can read logs
        security_context=client.V1SecurityContext(privileged=True),
        volume_mounts=[
            client.V1VolumeMount(
                mount_path="/host",
                name="host-root"
            )
        ]
    )

    template = client.V1PodTemplateSpec(
        metadata=client.V1ObjectMeta(labels={"app": name}),
        spec=client.V1PodSpec(
            host_network=True,
            host_pid=True,
            host_ipc=True,
            containers=[container],
            volumes=[
                client.V1Volume(
                    name="host-root",
                    host_path=client.V1HostPathVolumeSource(path="/")
                )
            ],
            tolerations=[
                client.V1Toleration(operator="Exists") # Run on all nodes, including masters
            ]
        )
    )

    daemonset = client.V1DaemonSet(
        api_version="apps/v1",
        kind="DaemonSet",
        metadata=client.V1ObjectMeta(name=name, namespace=namespace),
        spec=client.V1DaemonSetSpec(
            selector=client.V1LabelSelector(match_labels={"app": name}),
            template=template
        )
    )

    apps_api = client.AppsV1Api(api_instance)
    try:
        apps_api.create_namespaced_daemon_set(namespace=namespace, body=daemonset)
        print(f"DaemonSet {name} created.")
    except ApiException as e:
        print(f"Exception when creating DaemonSet: {e}")
        exit(1)

def get_pod_logs(core_api, namespace, label_selector):
    pods = core_api.list_namespaced_pod(namespace, label_selector=label_selector)
    results = {}
    
    print(f"Waiting for {len(pods.items)} pods to be ready...")
    
    # Simple wait loop (in production, use a watcher or proper timeout)
    # We just wait a bit for them to pull image and start
    time.sleep(10) 
    
    pods = core_api.list_namespaced_pod(namespace, label_selector=label_selector)
    
    for pod in pods.items:
        node_name = pod.spec.node_name
        pod_name = pod.metadata.name
        try:
            log = core_api.read_namespaced_pod_log(pod_name, namespace)
            results[node_name] = log
        except ApiException as e:
            print(f"Could not read log for pod {pod_name} on {node_name}: {e}")
            
    return results

def parse_and_report(results):
    print("\n" + "="*40)
    print("NODE VERSION REPORT")
    print("="*40)
    
    for node, log in results.items():
        print(f"Node: {node}")
        lines = log.split('\n')
        crio = "Unknown"
        criu = "Unknown"
        runc = "Unknown"
        
        for line in lines:
            if "CRIO_VERSION:" in line:
                crio = line.split("CRIO_VERSION:")[1].strip()
            if "CRIU_INSTALLED:" in line:
                criu = line.split("CRIU_INSTALLED:")[1].strip()
            if "RUNC_VERSION:" in line:
                runc = line.split("RUNC_VERSION:")[1].strip()
                
        print(f"  CRIO: {crio}")
        print(f"  CRIU Installed: {criu}")
        print(f"  RUNC: {runc}")
        
        # Validation logic requested by user
        # crio is on version 1.31.2
        # criu is installed
        # runc is install and on version 1.2.4
        
        issues = []
        if "1.31.2" not in crio:
            issues.append(f"CRIO version mismatch (expected 1.31.2)")
        if criu != "YES":
            issues.append("CRIU not installed")
        if "1.2.4" not in runc:
            issues.append(f"RUNC version mismatch (expected 1.2.4)")
            
        if issues:
            print("  [FAIL] Issues found:")
            for issue in issues:
                print(f"    - {issue}")
        else:
            print("  [PASS] All checks passed.")
        print("-" * 20)

def cleanup(api_instance, namespace, name):
    apps_api = client.AppsV1Api(api_instance)
    try:
        apps_api.delete_namespaced_daemon_set(name, namespace)
        print(f"DaemonSet {name} deleted.")
    except ApiException as e:
        print(f"Exception when deleting DaemonSet: {e}")

def main():
    args = get_args()
    setup_k8s_client(args)
    
    api_client = client.ApiClient()
    core_api = client.CoreV1Api(api_client)
    
    namespace = "default" # Could be parameterized
    ds_name = f"node-checker-{uuid.uuid4().hex[:6]}"
    
    try:
        create_daemonset(api_client, namespace, ds_name)
        # Give it some time to schedule and run
        # A better approach is to watch for Pod status, but sleep is simple for this script
        print("Waiting for pods to run...")
        time.sleep(10) 
        
        results = get_pod_logs(core_api, namespace, f"app={ds_name}")
        parse_and_report(results)
        
    finally:
        cleanup(api_client, namespace, ds_name)

if __name__ == "__main__":
    main()
