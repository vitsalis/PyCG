
from google.protobuf import json_format
import google.protobuf.message
json_format.MessageToJson(google.protobuf.message.Message()).upper()
