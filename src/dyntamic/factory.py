import json
from typing import Annotated, Union, TypeVar, get_args
from pydantic import BaseModel, create_model, Field

ModelType = TypeVar("ModelType", bound=BaseModel)


class DyntamicFactory:
    TYPES = {
        "string": str,
        "array": list,
        "boolean": bool,
        "integer": int,
        "float": float,
        "number": float,
    }

    def __init__(
        self,
        json_schema: dict,
        base_model: type[ModelType] | tuple[type[ModelType], ...] | None = None,
        ref_template: str = "#/$defs/",
    ) -> None:
        self.class_name = json_schema.get("title", "DynamicModel")
        self.class_type = json_schema.get("type", "object")
        self.required = json_schema.get("required", [])
        self.raw_fields = json_schema.get("properties", {})
        self.ref_template = ref_template.strip("/")
        self.definitions = json_schema.get("definitions") or json_schema.get(
            "$defs", {}
        )
        self.fields = {}
        self.model_fields = {}
        self._base_model = base_model

    def make(self) -> ModelType:
        for field_name, field_info in self.raw_fields.items():
            if "$ref" in field_info:
                model_name = field_info["$ref"].split("/")[-1]
                self._make_nested(model_name, field_name)
            else:
                field_type = self.TYPES.get(field_info.get("type"))
                if field_type == list:
                    items = field_info.get("items", {})
                    if "$ref" in items:
                        model_name = items["$ref"].split("/")[-1]
                        self._make_nested(model_name, field_name, is_array=True)
                    else:
                        self._make_field(list, field_name)
                else:
                    self._make_field(field_type, field_name)
        return create_model(
            self.class_name, __base__=self._base_model, **self.model_fields
        )

    def _make_nested(
        self, model_name: str, field_name: str, is_array: bool = False
    ) -> None:
        nested_schema = self.definitions[model_name]
        nested_factory = DyntamicFactory(
            {**nested_schema, "title": model_name}, ref_template=self.ref_template
        )
        nested_model = nested_factory.make()
        self._make_field([nested_model] if is_array else nested_model, field_name)

    def _make_field(self, field_type, field_name) -> None:
        is_required = field_name in self.required
        default = (
            ... if is_required else None
        )  # Use ellipsis for required fields, None for optional
        field_alias = field_name  # Alias can be customized as needed

        # Determine the correct annotation based on whether the field is required
        if is_required:
            annotation = field_type  # Direct type if required
        else:
            annotation = Union[field_type, None]  # Allow None if not required

        # Update field definition with correct structure (type, default value)
        self.model_fields[field_name] = (
            annotation,
            Field(default=default, alias=field_alias),
        )


def json_to_model(raw_json: str, title: str = "DynamicModel", type: str = "object"):
    data = json.loads(raw_json)
    schema = {
        "properties": {
            key: {"type": "string"} for key in data.keys()
        },  # Simplification, adjust types as needed
        "required": list(data.keys()),
        "title": title,
        "type": type,
    }
    return DyntamicFactory(schema).make()


if __name__ == "__main__":
    raw_json = """
    {
        "first_name": "string",
        "last_name": "string",
        "year_of_birth": "integer",
        "num_seasons_in_nba": "integer"
    }
    """
    model = json_to_model(raw_json).schema()
    print(model)
