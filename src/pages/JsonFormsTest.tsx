import Form from "@rjsf/react-bootstrap";
import { customizeValidator } from "@rjsf/validator-ajv8";
import Ajv2020 from "ajv/dist/2020.js";
import { ImageDisplayWidget } from "../Components/features/VCIAutomation/RJSF-Extras/Widgets/ImageDisplay.tsx";

const currentData = {
    //uri can also be base64 encoded, e.g. "data:image/png;base64,iVBORw0KGgoAA..."
    "monitorImage": "https://www.uni-bonn.de/de/forschung-lehre/forschung-und-lehre-medien/transfercenter-enacom-medien/uni-und-bonn_transfer_header.jpg/images/image/preview",
    "monitorImage2": "https://www.uni-bonn.de/de/forschung-lehre/forschung-und-lehre-medien/transfercenter-enacom-medien/uni-und-bonn_transfer_header.jpg/images/image/preview",
    "performActionXY": null,
    "temperature": "42.5 °C",
    "status": "All systems operational",
    "calibrationStatus": "Not started",
    "servers": [
        {
            "id": "server1",
            "name": "Server 1",
            "status": "Online"
        },
        {
            "id": "server2",
            "name": "Server 2",
            "status": "Offline"
        }
    ]
}

const dataSchema = {
    "type": "object",
    "properties": {
        "temperature": {
            "type": "string",
            "title": "Temperature"
        },
        "monitorImage": {
            "type": "string",
            "title": "Monitoring image",
            "format": "uri"
        },
        "monitorImage2": {
            "type": "string",
            "title": "Monitoring image 2",
            "format": "uri"
        },
        "performActionXY": {
            "title": "Do you want to perform action XY?",
            "type": ["boolean", "null"],
        },
        "status": {
            "type": "string",
            "title": "System status"
        },
        "calibrationStatus": {
            "type": "string",
            "title": "Calibration status",
            "enum": ["Not started", "In progress", "Completed", "Failed"]
        },
        "servers": {
            "type": "array",
            "title": "Servers",
            "items": {
                "type": "object",
                "properties": {
                    "id": {
                        "type": "string",
                        "title": "ID"
                    },
                    "name": {
                        "type": "string",
                        "title": "Name"
                    },
                    "status": {
                        "type": "string",
                        "title": "Status"
                    }
                }
            }
        }
    }
}

const uiSchema = {
    "ui:field": "LayoutGridField",
    "ui:layoutGrid": {
        "ui:row": {
            "children": [
                {
                    "ui:columns": {
                        "xs": 12,
                        "md": 4,
                        "children": ["temperature", "status", "calibrationStatus"]
                    }
                },
                {
                    "ui:columns": {
                        "xs": 12,
                        "md": 6,
                        "children": ["monitorImage", "monitorImage2"]
                    }
                },
                {
                    "ui:col": {
                        "xs": 12,
                        "children": ["performActionXY"]
                    }
                },
                {
                    "ui:col": {
                        "children": ["servers"]
                    }
                }
            ]
        }
    },
    "temperature": {
        "ui:readonly": true
    },
    "monitorImage": {
        "ui:widget": "imageDisplay",
        "ui:readonly": true
    },
    "monitorImage2": {
        "ui:widget": "imageDisplay",
        "ui:readonly": true
    },
    "performActionXY": {
        "ui:widget": "radio",
        "ui:options": {
            "inline": true
        }
    },
    "status": {
        "ui:readonly": true
    },
    "calibrationStatus": {
        "ui:readonly": true
    },
    "servers": {
        "ui:readonly": true,
        "items": {
            "id": {
                "ui:readonly": true
            },
            "name": {
                "ui:readonly": true
            },
            "status": {
                "ui:readonly": true
            }
        }
    }
}


const validator = customizeValidator({ AjvClass: Ajv2020 });
export function JsonFormsTestPage() {
    return (
        <div className="p-4 mx-auto" style={{ maxWidth: 900 }}>
            <h1>JSON Forms Test</h1>
            <Form
                schema={dataSchema as any}
                uiSchema={uiSchema}
                formData={currentData}
                widgets={{ imageDisplay: ImageDisplayWidget }}
                validator={validator}
            />
        </div>
    );
}
