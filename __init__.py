
from .nbt import *
from .world import *
from .region import *
from .chunk import *
from .jnbt import *

__all__ = list()
__all__.extend(nbt.__all__)
__all__.extend(world.__all__)
__all__.extend(region.__all__)
__all__.extend(chunk.__all__)
__all__.extend(jnbt.__all__)

# true author: https://github.com/twoolie
# url: https://github.com/twoolie/NBT
# Documentation only automatically includes functions specified in __all__.
# If you add more functions, please manually include them in doc/index.rst.

VERSION = (1, 6, 0)
"""NBT version as tuple. Note that the major and minor revision number are 
always present, but the patch identifier (the 3rd number) is only used in 1.4."""

def _get_version():
    """Return the NBT version as string."""
    return ".".join([str(v) for v in VERSION])
