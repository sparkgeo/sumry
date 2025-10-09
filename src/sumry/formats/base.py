
from typing import Final


class BaseFormat:
    format: Final = None

    @property
    def name(self):
        raise NotImplementedError("Method not implemented")
    
    @property
    def size(self):
        raise NotImplementedError("Method not implemented")

    def metadata(self, *args, **kwargs):
        return {}

    def sample_data(self, sample_size: int = 20, *args, **kwargs):
        raise NotImplementedError("Method not implemented")
