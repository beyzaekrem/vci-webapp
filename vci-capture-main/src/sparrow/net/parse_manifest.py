import xml.etree.ElementTree as ET


def count_child_elements_with_name(parent, target_name):
    return sum(1 for child in parent if child.tag == target_name)


def get_field_name_without_dup(json_obj, field_name):
    ret = field_name
    i = 2
    while ret in json_obj:
        ret = f"{field_name}-{i}"
        i += 1
    return ret


def clean_field_name(field_name):
    return field_name.split("}", 1)[-1] if "}" in field_name else field_name


def xml_to_json(xml_element):
    result = {}
    for child in xml_element:
        field_name = child.tag
        field_name_clean = clean_field_name(field_name)
        if count_child_elements_with_name(xml_element, field_name) == 1:
            if child.text and child.text.strip():
                result[field_name_clean] = child.text.strip()
            else:
                result[field_name_clean] = xml_to_json(child)
        elif child.text and child.text.strip():
            result.setdefault(field_name_clean, []).append(child.text.strip())
        else:
            result.setdefault(field_name_clean, []).append(xml_to_json(child))

    for attrib_name, attrib_value in xml_element.attrib.items():
        result[get_field_name_without_dup(result, attrib_name)] = attrib_value

    return result


def parse_manifest(xml_str: str) -> list:
    root = ET.fromstring(xml_str)
    manifest_data = []

    for i, group in enumerate(root):
        group_name = group.attrib.get("Comment", None)

        for manifest_obj in group:
            manifest_obj_json = xml_to_json(manifest_obj)
            manifest_obj_json["DataType"] = clean_field_name(manifest_obj.tag)
            manifest_obj_json["ManifestGroup"] = group_name

            if "Name" in manifest_obj.attrib:
                manifest_obj_json["NameFromManifest"] = manifest_obj.attrib["Name"]

            manifest_data.append(manifest_obj_json)

    # Copy register info for xiapi params, e.g., invalidators
    for obj in manifest_data:
        if "pValue" in obj:
            p_value = obj["pValue"]
            for reg_obj in manifest_data:
                if reg_obj.get("Name") == p_value:
                    obj["RegisterInfoFromManifest"] = reg_obj
                    break

    return manifest_data
