import json
import os
from typing import Dict, Optional

from pydantic import TypeAdapter

from mcpm.schemas.server_config import ServerConfig

DEFAULT_PROFILE_PATH = os.path.expanduser("~/.config/mcpm/profiles.json")


class ProfileConfigManager:
    def __init__(self, profile_path: str = DEFAULT_PROFILE_PATH):
        self.profile_path = os.path.expanduser(profile_path)
        self._profiles = self._load_profiles()

    def _load_profiles(self) -> Dict[str, list[ServerConfig]]:
        if not os.path.exists(self.profile_path):
            return {}
        with open(self.profile_path, "r") as f:
            profiles = json.load(f) or {}
        return {
            name: [TypeAdapter(ServerConfig).validate_python(config) for config in configs]
            for name, configs in profiles.items()
        }

    def _save_profiles(self) -> None:
        profile_info = {name: [config.model_dump() for config in configs] for name, configs in self._profiles.items()}
        with open(self.profile_path, "w") as f:
            json.dump(profile_info, f, indent=2)

    def new_profile(self, profile_name: str) -> bool:
        if profile_name in self._profiles:
            return False
        self._profiles[profile_name] = []
        self._save_profiles()
        return True

    def get_profile(self, profile_name: str) -> Optional[list[ServerConfig]]:
        return self._profiles.get(profile_name)

    def get_profile_server(self, profile_name: str, server_name: str) -> Optional[ServerConfig]:
        if profile_name not in self._profiles:
            return None
        for server_config in self._profiles[profile_name]:
            if server_config.name == server_name:
                return server_config
        return None

    def set_profile(self, profile_name: str, config: ServerConfig) -> bool:
        if profile_name not in self._profiles:
            self._profiles[profile_name] = []
        for idx, server_config in enumerate(self._profiles[profile_name]):
            if server_config.name == config.name:
                self._profiles[profile_name][idx] = config
                break
        else:
            self._profiles[profile_name].append(config)
        self._save_profiles()
        return True

    def delete_profile(self, profile_name: str) -> bool:
        if profile_name in self._profiles:
            del self._profiles[profile_name]
            self._save_profiles()
            return True
        return False

    def list_profiles(self) -> dict[str, list[ServerConfig]]:
        return self._profiles

    def rename_profile(self, old_name: str, new_name: str) -> bool:
        if old_name not in self._profiles:
            return False
        if new_name in self._profiles:
            return False
        self._profiles[new_name] = self._profiles.pop(old_name)
        self._save_profiles()
        return True

    def remove_server(self, profile_name: str, server_name: str) -> bool:
        if profile_name not in self._profiles:
            return False
        for idx, server_config in enumerate(self._profiles[profile_name]):
            if server_config.name == server_name:
                self._profiles[profile_name].pop(idx)
                self._save_profiles()
                return True
        return False

    def reload(self):
        self._profiles = self._load_profiles()
