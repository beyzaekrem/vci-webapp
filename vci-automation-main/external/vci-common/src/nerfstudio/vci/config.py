"""vci/config.py"""

from nerfstudio.plugins.registry_dataparser import DataParserSpecification
from vci.vci_dataparser import VCIDataParserConfig

VCIDataparser = DataParserSpecification(config=VCIDataParserConfig())
