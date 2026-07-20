

#include <nlohmann/json.hpp>
#include "tinyxml2.h"

int countChildElementsWithName(tinyxml2::XMLElement *parent,
                               const char *targetName)
{
  int count = 0;
  for (tinyxml2::XMLElement *child = parent->FirstChildElement();
       child != nullptr; child = child->NextSiblingElement())
  {
    if (strcmp(child->Name(), targetName) == 0)
    {
      count++;
    }
  }
  return count;
}

std::string get_field_name_without_dup(nlohmann::json const &json,
                                       std::string const &fieldName)
{
  std::string ret = fieldName;

  int i = 2;
  while (json.find(ret) !=
         json.end())
  {                                            // Check if ret exists in the JSON object
    ret = fieldName + "-" + std::to_string(i); // Update ret with a new name
    i++;
  }
  return ret;
}

nlohmann::json xml_to_json(tinyxml2::XMLElement *xml)
{
  nlohmann::json ret;
  for (tinyxml2::XMLElement *child = xml->FirstChildElement(); child != nullptr;
       child = child->NextSiblingElement())
  {
    std::string fieldName = child->Name();

    if (countChildElementsWithName(xml, fieldName.c_str()) == 1)
    {
      if (child->GetText() != nullptr)
      {
        ret[fieldName] = child->GetText();
      }
      else
      {
        ret[fieldName] = xml_to_json(child);
      }
    }
    else
    {
      if (child->GetText() != nullptr)
      {
        ret[fieldName].push_back(child->GetText());
      }
      else
      {
        ret[fieldName].push_back(xml_to_json(child));
      }
    }
  }

  for (const tinyxml2::XMLAttribute *attribute = xml->FirstAttribute();
       attribute != nullptr; attribute = attribute->Next())
  {
    // group[groupname][attribute->Name()] = attribute->Value();
    ret[get_field_name_without_dup(ret, attribute->Name())] =
        attribute->Value();
  }

  return ret;
}

nlohmann::json parse_manifest(std::string xml_str)
{
  char *man = new char[xml_str.length() + 1];
  strcpy(man, xml_str.c_str());

  tinyxml2::XMLDocument xmlDoc;

  tinyxml2::XMLError error = xmlDoc.Parse(man);
  if (error != tinyxml2::XML_SUCCESS)
  {
  }

  // Get the root element
  tinyxml2::XMLElement *rootElement = xmlDoc.RootElement();
  // Check if root element exists
  if (!rootElement)
  {
  }

  int i = 0;
  nlohmann::json ret;
  // parse the manifest and convert it to array of json objects (ret)
  for (tinyxml2::XMLElement *child = rootElement->FirstChildElement();
       child != nullptr; child = child->NextSiblingElement())
  {
    nlohmann::json group;

    const char *groupname = child->Attribute("Comment");

    for (tinyxml2::XMLElement *manifestobj = child->FirstChildElement();
         manifestobj != nullptr;
         manifestobj = manifestobj->NextSiblingElement())
    {

      nlohmann::json manifest_obj_json = xml_to_json(manifestobj);

      const char *typenam = manifestobj->Name();
      manifest_obj_json["DataType"] = typenam;
      manifest_obj_json["ManifestGroup"] = groupname;

      if (manifestobj->Attribute("Name") != NULL)
      {
        manifest_obj_json["NameFromManifest"] =
            manifestobj->Attribute("Name");
      }

      ret[i] = manifest_obj_json;

      i++;
    }
  }

  // Copy info from registers for xiapi params into xiapi param itself, e.g.
  // invalidators
  for (int j = 0; j < ret.size(); j++)
  {
    nlohmann::json obj = ret[j];
    // Check if the object has a field named "pValue" (Name of Register)
    if (obj.contains("pValue"))
    {
      // If "pValue" field exists, find the register info
      auto pValue = obj["pValue"];
      for (int regInd = 0; regInd < ret.size(); regInd++)
      {
        nlohmann::json regObj = ret[regInd];

        if (regObj.contains("Name") && regObj["Name"] == pValue)
        {
          ret[j]["RegisterInfoFromManifest"] = regObj;
          break;
        }
      }
    }
  }

  return ret;
}
