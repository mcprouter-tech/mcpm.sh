"""
Client command for MCPM
"""

import json
import os
import subprocess

import click
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from rich.table import Table

from mcpm.clients.client_config import ClientConfigManager
from mcpm.clients.client_registry import ClientRegistry
from mcpm.utils.display import print_client_error, print_error, print_server_config

console = Console()
client_config_manager = ClientConfigManager()


@click.group(context_settings=dict(help_option_names=["-h", "--help"]))
def client():
    """Manage MCP clients.

        Commands for listing, setting the active client, and editing client configurations.

    Examples:

    \b
        mcpm client ls              # List all supported MCP clients and their status
        mcpm client set CLIENT      # Set the active client
        mcpm client edit            # Open active client MCP settings in external editor
    """
    pass


@client.command(name="ls", context_settings=dict(help_option_names=["-h", "--help"]))
def list_clients():
    """List all supported MCP clients and their status."""
    # Get the list of supported clients
    supported_clients = ClientRegistry.get_supported_clients()

    table = Table(title="Supported MCP Clients")
    table.add_column("Client Name", style="cyan")
    table.add_column("Installation", style="yellow")
    table.add_column("Status", style="green")
    table.add_column("Profile", style="magenta")

    active_client = ClientRegistry.get_active_client()
    installed_clients = ClientRegistry.detect_installed_clients()

    for client in sorted(supported_clients):
        # Determine installation status
        installed = installed_clients.get(client, False)
        install_status = "[green]Installed[/]" if installed else "[gray]Not installed[/]"

        # Determine active status
        active_status = "[bold green]ACTIVE[/]" if client == active_client else ""

        # Get client info for more details
        client_info = ClientRegistry.get_client_info(client)
        display_name = client_info.get("name", client)
        # Get Profile activated
        client_manager = ClientRegistry.get_client_manager(client)
        profile = client_manager.get_associated_profile() if client_manager else None
        active_profile = f"[bold magenta]{profile}[/]" if profile else ""

        table.add_row(f"{display_name} ({client})", install_status, active_status, active_profile)

    console.print(table)

    # Add helpful instructions for non-installed clients
    non_installed = [c for c, installed in installed_clients.items() if not installed]
    if non_installed:
        console.print("\n[italic]To use a non-installed client, you need to install it first.[/]")
        for client in non_installed:
            info = ClientRegistry.get_client_info(client)
            if "download_url" in info:
                console.print(f"[yellow]{info.get('name', client)}[/]: {info['download_url']}")


@client.command(name="set", context_settings=dict(help_option_names=["-h", "--help"]))
@click.argument("client_name", required=True)
def set_client(client_name):
    """Set the active MCP client.

    CLIENT is the name of the client to set as active.
    """

    # Get the list of supported clients
    supported_clients = ClientRegistry.get_supported_clients()

    # Set the active client if provided
    if client_name not in supported_clients:
        console.print(f"[bold red]Error:[/] Unknown client: {client_name}")
        console.print(f"Supported clients: {', '.join(sorted(supported_clients))}")
        return

    # Set the active client
    if client_name == ClientRegistry.get_active_client():
        console.print(f"[bold yellow]Note:[/] {client_name} is already the active client")
        return

    # Attempt to set the active client with active profile inner switched
    success = ClientRegistry.set_active_client(client_name)
    if success:
        console.print(f"[bold green]Success:[/] Active client set to {client_name}")
        active_profile = ClientRegistry.get_active_profile()
        if active_profile:
            console.print(f"[bold green]Success:[/] Active profile set to {active_profile}")

        # Provide information about what this means
        panel = Panel(
            f"The active client ({client_name}) will be used for all MCP operations.\n"
            f"Commands like 'mcpm ls', 'mcpm add', 'mcpm rm', 'mcpm stash', and 'mcpm pop' will now operate on {client_name}.",
            title="Active Client Changed",
            border_style="green",
        )
        console.print(panel)
    else:
        console.print(f"[bold red]Error:[/] Failed to set {client_name} as the active client")


@client.command(name="edit", context_settings=dict(help_option_names=["-h", "--help"]))
def edit_client():
    """Open the active client's MCP settings in external editor."""
    # Get the active client manager and related information
    client_manager = ClientRegistry.get_active_client_manager()
    client = ClientRegistry.get_active_client()
    client_info = ClientRegistry.get_client_info(client)
    client_name = client_info.get("name", client)

    # Check if client is supported
    if client_manager is None:
        print_client_error(client_name)
        return

    # Get the client config file path
    config_path = client_manager.config_path

    # Check if the client is installed
    if not client_manager.is_client_installed():
        print_error(f"{client_name} installation not detected.")
        return

    # Check if config file exists
    config_exists = os.path.exists(config_path)

    # Display the config file information
    console.print(f"[bold]{client_name} config file:[/] {config_path}")
    console.print(f"[bold]Status:[/] {'[green]Exists[/]' if config_exists else '[yellow]Does not exist[/]'}\n")

    # Create config file if it doesn't exist and user confirms
    if not config_exists:
        console.print(f"[bold yellow]Creating new {client_name} config file...[/]")

        # Create a basic config template
        basic_config = {
            "mcpServers": {
                "filesystem": {
                    "command": "npx",
                    "args": [
                        "-y",
                        "@modelcontextprotocol/server-filesystem",
                        os.path.expanduser("~/Desktop"),
                        os.path.expanduser("~/Downloads"),
                    ],
                }
            }
        }

        # Create the directory if it doesn't exist
        os.makedirs(os.path.dirname(config_path), exist_ok=True)

        # Write the template to file
        try:
            with open(config_path, "w") as f:
                json.dump(basic_config, f, indent=2)
            console.print("[green]Successfully created config file![/]\n")
            config_exists = True
        except Exception as e:
            print_error("Error creating config file", str(e))
            return

    # Show the current configuration if it exists
    if config_exists:
        try:
            with open(config_path, "r") as f:
                config_content = f.read()

            # Display the content
            console.print("[bold]Current configuration:[/]")
            panel = Panel(config_content, title=f"{client_name} Config", expand=False)
            console.print(panel)

            # Count the configured servers
            try:
                config_json = json.loads(config_content)
                server_count = len(config_json.get("mcpServers", {}))
                console.print(f"[bold]Configured servers:[/] {server_count}")

                # Display detailed information for each server
                if server_count > 0:
                    console.print("\n[bold]MCP Server Details:[/]")
                    for server_name, server_config in config_json.get("mcpServers", {}).items():
                        print_server_config(client_manager.from_client_format(server_name, server_config))

            except json.JSONDecodeError:
                console.print("[yellow]Warning: Config file contains invalid JSON[/]")

        except Exception as e:
            print_error("Error reading config file", str(e))

    # Prompt to edit if file exists
    should_edit = False
    if config_exists:
        should_edit = Confirm.ask("Would you like to open this file in your default editor?")

    # Open in default editor if requested
    if should_edit and config_exists:
        try:
            console.print("[bold green]Opening config file in your default editor...[/]")

            # Use appropriate command based on platform
            if os.name == "nt":  # Windows
                os.startfile(config_path)
            elif os.name == "posix":  # macOS and Linux
                subprocess.run(["open", config_path] if os.uname().sysname == "Darwin" else ["xdg-open", config_path])

            console.print(f"[italic]After editing, {client_name} must be restarted for changes to take effect.[/]")
        except Exception as e:
            print_error("Error opening editor", str(e))
            console.print(f"You can manually edit the file at: {config_path}")
