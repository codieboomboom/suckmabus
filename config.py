from dataclasses import dataclass, fields, field, MISSING
from typing import get_type_hints
from os import getenv
from dotenv import load_dotenv

# Load the .env file once when module is imported
load_dotenv()


class BaseConfig:
    """Base config class to provide a load and check env method"""

    @classmethod
    def load_config(cls):
        env_vars = {}
        missing_env_vars = []
        type_hints = get_type_hints(cls)

        for cls_field in fields(cls):
            env_var_key = cls_field.metadata.get("associated_env")
            if not env_var_key:
                continue

            env_var_val = getenv(env_var_key)
            # TODO: this can be a log, on debug mode, but we need to blind out the environment var: let say if it has token/credential, username, password, it needed to be blind out
            # print(f"{env_var_key} : {env_var_val}")

            # Typecast to ideal field type (because all env var are string)
            if env_var_val:
                target_type = type_hints[cls_field.name]
                if target_type is bool:
                    env_vars[cls_field.name] = env_var_val.lower() in ("true", "1", "t")
                elif target_type is int:
                    env_vars[cls_field.name] = int(env_var_val)
                else:
                    env_vars[cls_field.name] = env_var_val
            else:
                # missing env_var detected
                if (
                    cls_field.default is MISSING
                    and cls_field.default_factory is MISSING
                ):
                    missing_env_vars.append(
                        f"{env_var_key} (for field: {cls_field.name})"
                    )

        # Throw error should any environment variable are missing without a default value
        if missing_env_vars:
            raise ValueError(
                f"Configuration loading failed for '{cls.__name__}'. "
                f"The following required environment variables are missing:\n"
                + "\n".join(f" - {var}" for var in missing_env_vars)
            )
        return cls(**env_vars)


@dataclass(frozen=True)
class TelegramBotApiConfig(BaseConfig):
    base_url: str = field(metadata={"associated_env": "TELEGRAM_BOT_BASEURL"})
    token: str = field(metadata={"associated_env": "TELEGRAM_BOT_TOKEN"})
    conn_timeout: int = field(
        metadata={"associated_env": "TIMEOUT_TELEGRAM_CONNECTION"}
    )
    light_write_timeout: int = field(
        metadata={"associated_env": "TIMEOUT_TELEGRAM_LIGHT_UPLOAD"}
    )
    read_timeout: int = field(metadata={"associated_env": "TIMEOUT_TELEGRAM_READ"})


@dataclass(frozen=True)
class LTADatamallApiConfig(BaseConfig):
    base_url: str = field(metadata={"associated_env": "LTA_BASEURL"})
    token: str = field(metadata={"associated_env": "LTA_DATAMALL_TOKEN"})
    conn_timeout: int = field(metadata={"associated_env": "TIMEOUT_LTA_CONNECTION"})
    read_timeout: int = field(metadata={"associated_env": "TIMEOUT_LTA_READ"})
    pagination_size: int = field(
        default=500, metadata={"associated_env": "LTA_API_SKIP_OFFSET"}
    )


@dataclass(frozen=True)
class ApplicationConfig(BaseConfig):
    exp_backoff_min_delay: int = field(metadata={"associated_env": "MIN_DELAY"})
    exp_backoff_max_delay: int = field(metadata={"associated_env": "MAX_DELAY"})
    exp_backoff_max_retry: int = field(metadata={"associated_env": "MAX_RETRY"})


# Loading config into instances
telegram_bot_config = TelegramBotApiConfig.load_config()
lta_datamall_config = LTADatamallApiConfig.load_config()
app_config = ApplicationConfig.load_config()
