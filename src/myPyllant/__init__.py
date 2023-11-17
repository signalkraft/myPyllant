from importlib.metadata import version

from myPyllant.utils import version_tuple

"""
Make sure there is no conflicting version of dacite installed. This especially happens in Home Assistant with
other integrations installed through HACS, such as Govee
"""
if version_tuple(version("dacite")) < version_tuple("1.7.0"):
    raise Exception(
        "Invalid version of dacite library detected. You are probably using another integration like "
        "Govee which is installing a conflicting, older version."
    )
