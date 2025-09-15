from dataclasses import dataclass
from fnmatch import fnmatch

import httpx
import litellm
from pydantic import BaseModel, Field, SecretStr
import boto3

from openhands.sdk.logger import get_logger


logger = get_logger(__name__)



def normalize_model_name(model: str) -> str:
    """Normalize a model string to a canonical, comparable name.

    Strategy:
    - Trim whitespace
    - Lowercase
    - If there is a '/', keep only the basename after the last '/'
      (handles prefixes like openrouter/, litellm_proxy/, anthropic/, etc.)
      and treat ':' inside that basename as an Ollama-style variant tag to be removed
    - There is no provider:model form; providers, when present, use 'provider/model'
    - Drop a trailing "-gguf" suffix if present
    - If basename starts with a known vendor prefix followed by '.', drop that prefix
      (e.g., 'anthropic.claude-*' -> 'claude-*')
    """
    raw = (model or "").strip().lower()
    if "/" in raw:
        name = raw.split("/")[-1]
        if ":" in name:
            # Drop Ollama-style variant tag in basename
            name = name.split(":", 1)[0]
    else:
        # No '/', keep the whole raw name (we do not support provider:model)
        name = raw

    # Drop common vendor prefixes embedded in the basename (bedrock style), once.
    # Keep this list small and explicit to avoid accidental over-matching.
    vendor_prefixes = {
        "anthropic",
        "meta",
        "cohere",
        "mistral",
        "ai21",
        "amazon",
    }
    if "." in name:
        vendor, rest = name.split(".", 1)
        if vendor in vendor_prefixes and rest:
            name = rest

    if name.endswith("-gguf"):
        name = name[: -len("-gguf")]
    return name


def model_matches(model: str, patterns: list[str]) -> bool:
    """Return True if the model matches any of the glob patterns.

    If a pattern contains a '/', it is treated as provider-qualified and matched
    against the full, lowercased model string (including provider prefix).
    Otherwise, it is matched against the normalized basename.
    """
    raw = (model or "").strip().lower()
    name = normalize_model_name(model)
    for pat in patterns:
        pat_l = pat.lower()
        if "/" in pat_l:
            if fnmatch(raw, pat_l):
                return True
        else:
            if fnmatch(name, pat_l):
                return True
    return False


@dataclass(frozen=True)
class ModelFeatures:
    supports_function_calling: bool
    supports_reasoning_effort: bool
    supports_prompt_cache: bool
    supports_stop_words: bool


# Pattern tables capturing current behavior. Keep patterns lowercase.
FUNCTION_CALLING_PATTERNS: list[str] = [
    # Anthropic families
    "claude-3-7-sonnet*",
    "claude-3.7-sonnet*",
    "claude-sonnet-3-7-latest",
    "claude-3-5-sonnet*",
    "claude-3.5-haiku*",
    "claude-3-5-haiku*",
    "claude-sonnet-4*",
    "claude-opus-4*",
    # OpenAI families
    "gpt-4o*",
    "gpt-4.1",
    "gpt-5*",
    # o-series (keep exact o1 support per existing list)
    "o1-2024-12-17",
    "o3*",
    "o4-mini*",
    # Google Gemini
    "gemini-2.5-pro*",
    # Others
    "kimi-k2-0711-preview",
    "kimi-k2-instruct",
    "qwen3-coder*",
    "qwen3-coder-480b-a35b-instruct",
]

REASONING_EFFORT_PATTERNS: list[str] = [
    # Mirror main behavior exactly (no unintended expansion)
    "o1-2024-12-17",
    "o1",
    "o3",
    "o3-2025-04-16",
    "o3-mini-2025-01-31",
    "o3-mini",
    "o4-mini",
    "o4-mini-2025-04-16",
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gpt-5",
    "gpt-5-2025-08-07",
]

PROMPT_CACHE_PATTERNS: list[str] = [
    "claude-3-7-sonnet*",
    "claude-3.7-sonnet*",
    "claude-sonnet-3-7-latest",
    "claude-3-5-sonnet*",
    "claude-3-5-haiku*",
    "claude-3.5-haiku*",
    "claude-3-haiku-20240307*",
    "claude-3-opus-20240229*",
    "claude-sonnet-4*",
    "claude-opus-4*",
]

SUPPORTS_STOP_WORDS_FALSE_PATTERNS: list[str] = [
    # o1 family doesn't support stop words
    "o1*",
    # grok-4 specific model name (basename)
    "grok-4-0709",
    "grok-code-fast-1",
    # DeepSeek R1 family
    "deepseek-r1-0528*",
]


def get_features(model: str) -> ModelFeatures:
    return ModelFeatures(
        supports_function_calling=model_matches(model, FUNCTION_CALLING_PATTERNS),
        supports_reasoning_effort=model_matches(model, REASONING_EFFORT_PATTERNS),
        supports_prompt_cache=model_matches(model, PROMPT_CACHE_PATTERNS),
        supports_stop_words=not model_matches(
            model, SUPPORTS_STOP_WORDS_FALSE_PATTERNS
        ),
    )


def list_bedrock_foundation_models(
    aws_region_name: str, aws_access_key_id: str, aws_secret_access_key: str
) -> list[str]:
    try:
        # The AWS bedrock model id is not queried, if no AWS parameters are configured.
        client = boto3.client(
            service_name='bedrock',
            region_name=aws_region_name,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
        )
        foundation_models_list = client.list_foundation_models(
            byOutputModality='TEXT', byInferenceType='ON_DEMAND'
        )
        model_summaries = foundation_models_list['modelSummaries']
        return ['bedrock/' + model['modelId'] for model in model_summaries]
    except Exception as err:
        logger.warning(
            '%s. Please config AWS_REGION_NAME AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY'
            ' if you want use bedrock model.',
            err,
        )
        return []
    

def get_supported_llm_models(
    aws_region_name: str | None = None,
    aws_access_key_id: SecretStr | None = None,
    aws_secret_access_key: SecretStr | None = None,
) -> list[str]:
    """Get all models supported by LiteLLM.

    This function combines models from litellm and Bedrock, removing any
    error-prone Bedrock models.

    Returns:
        list[str]: A sorted list of unique model names.
    """
    litellm_model_list = litellm.model_list + list(litellm.model_cost.keys())
    litellm_model_list_without_bedrock = list(filter(lambda m: not m.startswith('bedrock'), litellm_model_list))
    bedrock_model_list = []
    if (
        aws_region_name and 
        aws_access_key_id and
        aws_secret_access_key
    ):
        bedrock_model_list = list_bedrock_foundation_models(
            aws_region_name,
            aws_access_key_id.get_secret_value(),
            aws_secret_access_key.get_secret_value(),
        )
    model_list = litellm_model_list_without_bedrock + bedrock_model_list
    return model_list



def split_is_actually_version(split: list[str]) -> bool:
    return (
        len(split) > 1
        and bool(split[1])
        and bool(split[1][0])
        and split[1][0].isdigit()
    )

def extract_model_and_provider(model: str) -> tuple[str, str, str]:
    """
    Extract provider and model information from a model identifier.
    """
    separator = '/'
    split = model.split(separator)

    if len(split) == 1:
        # no "/" separator found, try with "."
        separator = '.'
        split = model.split(separator)
        if split_is_actually_version(split):
            split = [separator.join(split)]  # undo the split

    if len(split) == 1:
        matched_provider = ''
        for provider, models in VERIFIED_MODELS.values():
            if split[0] in models:
                matched_provider = provider
                break

        if matched_provider:
            return matched_provider, split[0], '/'
        
        return matched_provider, model, ''


    provider = split[0]
    model_id = separator.join(split[1:])
    return provider, model_id, separator


def get_unverified_models(
    aws_region_name: str | None = None,
    aws_access_key_id: SecretStr | None = None,
    aws_secret_access_key: SecretStr | None = None
) -> dict[str, list[str]]:
    """Organize a list of model identifiers by provider.

    Args:
        models: List of model identifiers

    Returns:
        A mapping of providers to their information and models
    """
    result_dict: dict[str, list[str]] = {}

    models = get_supported_llm_models(aws_region_name, aws_access_key_id, aws_secret_access_key)
    for model in models:
        provider, model_id, separator = extract_model_and_provider(model)

        # Ignore "anthropic" providers with a separator of "."
        # These are outdated and incompatible providers.
        if provider == 'anthropic' and separator == '.':
            continue

        key = provider or 'other'
        if key not in result_dict:
            result_dict[key] = []

        result_dict[key].append(model_id)

    return result_dict


VERIFIED_OPENAI_MODELS = [
    'gpt-5-2025-08-07',
    'gpt-5-mini-2025-08-07',
    'o4-mini',
    'gpt-4o',
    'gpt-4o-mini',
    'gpt-4-32k',
    'gpt-4.1',
    'gpt-4.1-2025-04-14',
    'o1-mini',
    'o3',
    'codex-mini-latest',
]

VERIFIED_ANTHROPIC_MODELS = [
    'claude-sonnet-4-20250514',
    'claude-opus-4-20250514',
    'claude-opus-4-1-20250805',
    'claude-3-7-sonnet-20250219',
    'claude-3-sonnet-20240229',
    'claude-3-opus-20240229',
    'claude-3-haiku-20240307',
    'claude-3-5-haiku-20241022',
    'claude-3-5-sonnet-20241022',
    'claude-3-5-sonnet-20240620',
]

VERIFIED_MISTRAL_MODELS = [
    'devstral-small-2505',
    'devstral-small-2507',
    'devstral-medium-2507',
]

VERIFIED_OPENHANDS_MODELS = [
    'claude-sonnet-4-20250514',
    'gpt-5-2025-08-07',
    'gpt-5-mini-2025-08-07',
    'claude-opus-4-20250514',
    'claude-opus-4-1-20250805',
    'devstral-small-2507',
    'devstral-medium-2507',
    'o3',
    'o4-mini',
    'gemini-2.5-pro',
    'kimi-k2-0711-preview',
    'qwen3-coder-480b',
]


VERIFIED_MODELS = {
    'openhands': set(VERIFIED_OPENHANDS_MODELS),
    'anthropic': set(VERIFIED_ANTHROPIC_MODELS),
    'openai': set(VERIFIED_OPENAI_MODELS),
    'mistral': set(VERIFIED_MISTRAL_MODELS),
}


UNVERIFIED_MODELS = get_unverified_models()
print(UNVERIFIED_MODELS)