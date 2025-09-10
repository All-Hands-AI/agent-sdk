from pydantic import BaseModel


def pydantic_diff(a: BaseModel, b: BaseModel) -> dict:
    a_dict = a.model_dump(exclude_none=True)
    b_dict = b.model_dump(exclude_none=True)

    diff: dict[str, object] = {}
    for key in set(a_dict) | set(b_dict):
        if (a_item := a_dict.get(key)) != (b_item := b_dict.get(key)):
            if isinstance(a_item, BaseModel) and isinstance(b_item, BaseModel):
                nested_diff = pydantic_diff(a_item, b_item)
                if nested_diff:
                    diff[key] = nested_diff
            else:
                diff[key] = (a_item, b_item)
    return diff
