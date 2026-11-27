
import xml
import ext
import xml.etree.ElementTree as ET
from ext.pkg import thing
def load(text):
    return xml.etree.ElementTree.fromstring(text)
def other():
    ext.pkg.sub.helper()
