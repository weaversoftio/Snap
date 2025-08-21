import subprocess
import json
import logging
import os
from fastapi import HTTPException

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

async def generate_node_store(cluster_config_name: str):
    """
    Generate and store node inventory information for a Kubernetes cluster.
    
    Args:
        cluster_config_name (str): Name of the cluster configuration
        
    Returns:
        dict: Result of the operation containing success/error status and message
    """
    logging.debug(f"Starting node store generation for cluster: {cluster_config_name}")

    try:
        # Execute the 'oc get nodes' command to retrieve node information in JSON format
        result = subprocess.run(
            ['oc', 'get', 'nodes', '-o', 'json'],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        # Parse the JSON output
        nodes_data = json.loads(result.stdout)
        logging.debug("Nodes data retrieved successfully.")
    except subprocess.CalledProcessError as e:
        # Handle errors in the subprocess
        logging.error(f"An error occurred while executing 'oc get nodes': {e}")
        if e.stderr:
            logging.error(f"Error details: {e.stderr}")
        return {"error": False, "message": f"Error retrieving nodes: {e}"}
    except json.JSONDecodeError:
        # Handle JSON parsing errors
        logging.error("Error parsing the JSON output from 'oc get nodes'.")
        return {"error": False, "message": "Error parsing node data"}

    # Initialize the inventory structure
    inventory = {
        "nodes": {
            "hosts": {}
        }
    }

    # Populate the inventory with node information
    for node in nodes_data.get('items', []):
        node_name = node['metadata']['name']
        # Extract node IP addresses
        node_ips = [address['address'] for address in node.get('status', {}).get('addresses', [])
                    if address.get('type') == 'InternalIP']
        # Use the first IP address as the host key
        if node_ips:
            host_key = node_ips[0]
            inventory['nodes']['hosts'][host_key] = {
                "ansible_user": "core",  # Adjust based on your specific user
                "hostname": node_name,
                "ip": node_ips[0]
            }

    logging.debug(f"Inventory created: {inventory}")

    try:
        # Save the inventory to a new path: config/nodeStore/<cluster name>/<cluster name>.json
        node_store_path = f"config/nodeStore/{cluster_config_name}/{cluster_config_name}.json"
        os.makedirs(os.path.dirname(node_store_path), exist_ok=True)

        with open(node_store_path, 'w') as file:
            json.dump(inventory, file, indent=4)
        logging.debug(f"Inventory saved to {node_store_path}")
        
        return {"success": True, "message": "Node store generated successfully"}
    except Exception as e:
        logging.error(f"Error saving inventory: {e}")
        return {"error": False, "message": f"Error saving inventory: {str(e)}"}
