import json
from typing import Annotated, Union

import typing
from pydantic import create_model
from pydantic.fields import Field

Model = typing.TypeVar("Model", bound="BaseModel")


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
        base_model: type[Model] | tuple[type[Model], ...] | None = None,
        ref_template: str = "#/$defs/",
    ) -> None:
        """
        Creates a dynamic pydantic model from a JSONSchema, dumped from and existing Pydantic model elsewhere.
            JSONSchema dump must be called with ref_template='{model}' like:

            SomeSampleModel.model_json_schema(ref_template='{model}')
            Use:
            >> _factory = DyntamicFactory(schema)
            >> _factory.make()
            >> _model = create_model(_factory.class_name, **_factory.model_fields)
            >> _instance = dynamic_model.model_validate(json_with_data)
            >> validated_data = model_instance.model_dump()
        """
        self.class_name = json_schema.get("title")
        self.class_type = json_schema.get("type")
        self.required = json_schema.get("required", False)
        self.raw_fields = json_schema.get("properties")
        self.ref_template = ref_template
        self.definitions = json_schema.get("$defs", {})
        self.fields = {}
        self.model_fields = {}
        self._base_model = base_model

    def make(self) -> Model:
        """Factory method, dynamically creates a pydantic model from JSON Schema"""
        for field in self.raw_fields:
            if "$ref" in self.raw_fields[field]:
                model_name = self.raw_fields[field].get("$ref")
                self._make_nested(model_name.strip(self.ref_template), field)
            else:
                factory = self.TYPES.get(self.raw_fields[field].get("type"))
                if factory == list:
                    items = self.raw_fields[field].get("items")
                    if self.ref_template in items:
                        self._make_nested(items.get(self.ref_template), field)
                self._make_field(factory, field, self.raw_fields.get("title"))
        return create_model(
            self.class_name, __base__=self._base_model, **self.model_fields
        )

    def _make_nested(self, model_name: str, field) -> None:
        """Create a nested model"""
        level = DyntamicFactory(
            {"$defs": self.definitions} | self.definitions.get(model_name),
            ref_template=self.ref_template,
        )
        level.make()
        model = create_model(model_name, **level.model_fields)
        self._make_field(model, field, field)

    def _make_field(self, field_type, field_name, alias=None) -> None:
        """Create a field, properly handling required and optional fields."""
        if field_name in self.required:
            field_definition = (field_type, ...)
        else:
            # For optional fields, allow None and do not set a default_factory
            field_definition = (Optional[field_type], Field(default=None, alias=alias))

        self.model_fields[field_name] = field_definition


def process_value(key, value):
    """Process individual value to determine its type and potentially nested structure."""
    if isinstance(value, dict):
        nested_key = key.capitalize()
        # Process nested object recursively
        nested_properties, nested_required, nested_defs = process_dict(
            value
        )  # Corrected here
        return (
            {"$ref": f"#/$defs/{nested_key}"},
            {
                nested_key: {
                    "properties": nested_properties,
                    "required": nested_required,
                    "title": nested_key,
                    "type": "object",
                }
            },
            nested_defs,
        )  # Added third return value for definitions
    else:
        return (
            {"title": key.replace("_", " ").title(), "type": value},
            None,
            {},
        )  # Adjusted to return an empty dictionary for defs when not a dict


def process_dict(data):
    properties = {}
    required = []
    defs = {}

    for key, value in data.items():
        prop, def_, additional_defs = process_value(
            key, value
        )  # Corrected to capture all returned values
        properties[key] = prop
        required.append(key)
        if def_:
            defs.update(def_)
        defs.update(
            additional_defs
        )  # Include additional definitions from nested objects

    return (
        properties,
        required,
        defs,
    )  # Ensure this matches with the expected number of values


def create_json_schema_from_raw_json(raw_json, title="DynamicModel"):
    raw_data = json.loads(raw_json)
    properties, required, defs = process_dict(raw_data)

    schema = {
        "$defs": defs,
        "properties": properties,
        "required": required,
        "title": title,
        "type": "object",
    }

    return schema


def json_to_model(raw_json: str, title: str = "DynamicModel"):
    schema = create_json_schema_from_raw_json(raw_json, title)

    return DyntamicFactory(schema).make()


async def test():
    import sys, traceback

    try:
        from pydantic import BaseModel

        raw_json = """
        {
            "first_name": "string",
            "last_name": "string",
            "year_of_birth": { 
                "hello": "integer",
                "world": "string" },
            "num_seasons_in_nba": "integer"
        }
        """
        schema = create_json_schema_from_raw_json(raw_json, "AnswerFormat")

        class Year_of_birth(BaseModel):
            hello: int
            world: str

        class AnswerFormat(BaseModel):
            first_name: str
            last_name: str
            year_of_birth: Year_of_birth
            num_seasons_in_nba: int

        dyn_schema = DyntamicFactory(schema)
        model = dyn_schema.make()
        assert model.schema() == AnswerFormat.schema()

    except Exception as e:
        fr = traceback.extract_tb(sys.exc_info()[2])[-1]
        print(
            f"\x1b[38;5;208m{'/'.join(fr.filename.split('/')[-5:])}:{fr.lineno}:<<{fr.name}>>"
            + f"\n\x1b[36m󱞪 {fr.line}\n\x1b[33m󱞪 {e}\x1b[0m"
        )


if __name__ == "__main__":
    import asyncio

    asyncio.run(test())
