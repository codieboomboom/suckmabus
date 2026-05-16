from dataclasses import dataclass, fields
from typing import get_type_hints
from os import getenv
from dotenv import load_dotenv

# Load the .env file once when module is imported
load_dotenv()


@dataclass
class BaseConfig:
    """Base config class to provide a load and check env method"""

    @classmethod
    def load_config(cls):
        env_vars = {}
        type_hints = get_type_hints(cls)

        for cls_field in fields(cls):
            env_var_key = cls_field.metadata.get("associated_env")
            if not env_var_key:
                continue

            env_var_val = getenv(env_var_key)

            # Typecast to ideal field type (because all env var are string)
            if env_var_val:
                target_type = type_hints[cls_field.name]
                if target_type.isinstance(bool):
                    env_vars[cls_field.name] = env_var_val.lower() in ("true", "1", "t")
                elif target_type.isinstance(int):
                    env_vars[cls_field.name] = int(env_var_val)
                else:
                    env_vars[cls_field.name] = env_var_val

            return cls(**env_vars)
