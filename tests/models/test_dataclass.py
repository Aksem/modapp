
from dataclasses import dataclass

from modapp.models.dataclass import DataclassModel


@dataclass
class UserInfo(DataclassModel):
    name: str
    full_address: dict[str, str]
    
    __model_config__ = {'camelCase': True}


def test_model_with_dict_data_to_dict_camelcase():
    # only model attributes names should be transformed to camel case, not user data
    user_info = UserInfo(name='John White', full_address={'postal_code': '80100', 'country_name': 'Ukraine' })
    
    user_info_dict = user_info.to_dict()
    
    assert user_info_dict == {
        'name': 'John White',
        'fullAddress': {
            'postal_code': '80100',
            'country_name': 'Ukraine'
        }
    }
