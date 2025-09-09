from pydantic import BaseModel


def pydantic_diff(a: BaseModel, b: BaseModel) -> dict:
    a_dict = a.model_dump(exclude_none=True)
    b_dict = b.model_dump(exclude_none=True)

    diff: dict[str, tuple[object, object]] = {}
    for key in set(a_dict) | set(b_dict):
        if a_dict.get(key) != b_dict.get(key):
            diff[key] = (a_dict.get(key), b_dict.get(key))
    return diff
