import pulumi
import pulumi_digitalocean as do
import os

# Configuration
config = pulumi.Config()
domain_name = config.get("domain") or "setback.troyfischer.net"
base_domain = "troyfischer.net"

# 1. Upload SSH Key to DigitalOcean
key_path = os.path.expanduser("~/.ssh/setback-do-key.pub")

with open(key_path, "r") as key_file:
    public_key_content = key_file.read()

ssh_key = do.SshKey(
    "setback-ssh-key",
    name="setback-deployment-key",
    public_key=public_key_content,
)

# 2. User data script to set up the droplet
user_data_script = """#!/bin/bash
set -e

# Update apt and install dependencies
apt-get update -y
apt-get install -y ca-certificates curl gnupg git

# Add Docker's official GPG key
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg

# Add the repository
echo \
  "deb [arch=\"$(dpkg --print-architecture)\" signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker Engine and Compose
apt-get update -y
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Allow 'root' user to run docker commands
usermod -aG docker root

# Create app directory
mkdir -p /opt/setback
"""

# 3. Create Droplet
droplet = do.Droplet(
    "setback-droplet",
    name="setback-game-server",
    region="nyc3",
    size="s-2vcpu-2gb",  # $18/month - similar to t2.small (2 vCPU, 2GB RAM)
    image="ubuntu-22-04-x64",
    ssh_keys=[ssh_key.id],
    user_data=user_data_script,
    tags=["setback", "game-server"],
)

# 4. Create Cloud Firewall and attach to droplet
firewall = do.Firewall(
    "setback-firewall",
    name="setback-game-server",
    inbound_rules=[
        do.FirewallInboundRuleArgs(
            protocol="tcp",
            port_range="22",
            source_addresses=["0.0.0.0/0", "::/0"],
        ),
        do.FirewallInboundRuleArgs(
            protocol="tcp",
            port_range="80",
            source_addresses=["0.0.0.0/0", "::/0"],
        ),
        do.FirewallInboundRuleArgs(
            protocol="tcp",
            port_range="443",
            source_addresses=["0.0.0.0/0", "::/0"],
        ),
    ],
    outbound_rules=[
        do.FirewallOutboundRuleArgs(
            protocol="tcp",
            port_range="all",
            destination_addresses=["0.0.0.0/0", "::/0"],
        ),
        do.FirewallOutboundRuleArgs(
            protocol="udp",
            port_range="all",
            destination_addresses=["0.0.0.0/0", "::/0"],
        ),
        do.FirewallOutboundRuleArgs(
            protocol="icmp",
            destination_addresses=["0.0.0.0/0", "::/0"],
        ),
    ],
    droplet_ids=[droplet.id],
)

# 5. Create DNS A Record for setback.troyfischer.net
dns_record = do.DnsRecord(
    "setback-dns-record",
    domain=base_domain,
    type="A",
    name="setback",
    value=droplet.ipv4_address,
    ttl=300,
)

# 6. Export outputs
pulumi.export("droplet_id", droplet.id)
pulumi.export("public_ip", droplet.ipv4_address)
pulumi.export("domain_name", domain_name)
pulumi.export("url", pulumi.Output.concat("https://", domain_name))
