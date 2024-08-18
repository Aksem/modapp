from modapp.models.pydantic import (
    PydanticModel,
    AliasGenerator,
    to_camel,
    ConfigDict,
)


class UserInfo(PydanticModel):
    name: str
    full_address: dict[str, str]

    __model_config__ = {"camelCase": True}
    model_config = ConfigDict(
        alias_generator=AliasGenerator(
            validation_alias=None,
            serialization_alias=to_camel,
        )
    )
    __dump_options__ = {"by_alias": True}


def test_model_with_dict_data_to_dict_camelcase():
    # only model attributes names should be transformed to camel case, not user data
    user_info = UserInfo(
        name="John White",
        full_address={"postal_code": "80100", "country_name": "Ukraine"},
    )

    user_info_dict = user_info.to_dict()

    assert user_info_dict == {
        "name": "John White",
        "fullAddress": {"postal_code": "80100", "country_name": "Ukraine"},
    }


def test_model_from_camelcase_data():
    user_info = UserInfo.validate_and_construct_from_dict({"name": "John White", "fullAddress": {"postal_code": "80100", "country_name": "Ukraine"}})
    expected_user_info = UserInfo(
        name="John White",
        full_address={"postal_code": "80100", "country_name": "Ukraine"},
    )

    assert user_info == expected_user_info
